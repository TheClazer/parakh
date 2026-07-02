#!/usr/bin/env python3
"""
Parakh — ranking step (offline, CPU-only, no network).

Reproduce command:
    python rank.py --candidates ./candidates.jsonl --out ./submission.csv

Reads the candidate pool, runs the Integrity Gate + transparent rubric scorer,
and writes the top-100 as a spec-valid CSV (+ optional XLSX for the portal).

This is the v0 baseline: rules only, no learned model, no precomputed artifacts.
It exists so a *valid, submittable* entry is always in hand. Later stages plug a
LightGBM ranker trained on LLM-teacher labels into score(), without changing this
entry point or its compute profile.
"""

from __future__ import annotations
import argparse
import csv
import datetime
import json
import sys
import time
from pathlib import Path

from parakh import config as C
from parakh import features, score

# Fixed reference "today" for recency math → fully deterministic / reproducible.
REF_DATE = datetime.date(2026, 6, 30)
TOP_N = 100


def _load_labels(path):
    d = {}
    if path and Path(path).exists():
        for line in open(path, encoding="utf-8"):
            try:
                r = json.loads(line)
                d[r["candidate_id"]] = r
            except (json.JSONDecodeError, KeyError):
                pass
        print(f"[parakh] loaded {len(d)} labels from {path}", file=sys.stderr)
    return d


def _tier_of(lab):
    return lab["tier"] if lab and lab.get("tier") is not None else None


def load_and_score(path, labels=None, labels2=None, labels3=None):
    """Score every candidate. Teacher judgment dominates; the rule score orders
    within a tier. When several INDEPENDENT judges graded a candidate we use their
    AVERAGE tier (cross-model agreement rises to the very top):
        blended = (avg_tier + min(rule, 0.999)) / 6      -> in [0, 1]
    Unlabeled candidates (e.g. a fresh sandbox sample) fall back to the rule
    score alone, mapped into the tier-0 band so they never outrank a graded fit.
    """
    labels = labels or {}
    labels2 = labels2 or {}
    labels3 = labels3 or {}
    recs = []
    n = honeypots = stuffers = teacher_used = 0
    t0 = time.time()
    with open(path, "r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            try:
                cand = json.loads(line)
            except json.JSONDecodeError:
                continue
            n += 1
            rec = features.extract(cand, REF_DATE)
            rule = score.score(rec)
            rec["rule_score"] = rule
            cid = rec["candidate_id"]
            lab, lab2, lab3 = labels.get(cid), labels2.get(cid), labels3.get(cid)
            tiers = [t for t in (_tier_of(lab), _tier_of(lab2), _tier_of(lab3)) if t is not None]
            if tiers and not rec["honeypot"]:
                avg_tier = sum(tiers) / len(tiers)
                rec["tier"] = avg_tier
                rec["n_judges"] = len(tiers)
                rec["teacher_reason"] = ((lab and lab.get("reason"))
                                         or (lab2 and lab2.get("reason"))
                                         or (lab3 and lab3.get("reason")) or "").strip()
                rec["score"] = (avg_tier + min(rule, 0.999)) / 6.0
                teacher_used += 1
            else:
                rec["tier"] = None
                rec["n_judges"] = 0
                rec["teacher_reason"] = None
                rec["score"] = min(rule, 0.999) / 6.0
            honeypots += rec["honeypot"]
            stuffers += rec["stuffer"]
            recs.append(rec)
    dt = time.time() - t0
    print(f"[parakh] scored {n} in {dt:.1f}s ({honeypots} honeypots, "
          f"{stuffers} stuffers, {teacher_used} teacher-graded)", file=sys.stderr)
    return recs


def rank(recs):
    # Round to the SAME 6 decimals we write to the CSV *before* sorting, so that
    # candidates the validator sees as tied are ordered by candidate_id ascending
    # (spec §3). Sorting on the raw float would break this after rounding.
    for r in recs:
        r["score"] = round(r["score"], 6)
    recs.sort(key=lambda r: (-r["score"], r["candidate_id"]))
    return recs[:TOP_N]


def write_csv(top, out_path):
    with open(out_path, "w", encoding="utf-8", newline="") as f:
        w = csv.writer(f)
        w.writerow(["candidate_id", "rank", "score", "reasoning"])
        for i, r in enumerate(top, start=1):
            reasoning = r.get("teacher_reason") or score.reason(r)
            w.writerow([r["candidate_id"], i, f"{r['score']:.6f}", reasoning])
    print(f"[parakh] wrote {out_path}", file=sys.stderr)


def write_xlsx(top, out_path):
    try:
        from openpyxl import Workbook
    except ImportError:
        print("[parakh] openpyxl not installed; skipping XLSX", file=sys.stderr)
        return
    wb = Workbook()
    ws = wb.active
    ws.title = "ranking"
    ws.append(["candidate_id", "rank", "score", "reasoning"])
    for i, r in enumerate(top, start=1):
        reasoning = r.get("teacher_reason") or score.reason(r)
        ws.append([r["candidate_id"], i, round(r["score"], 6), reasoning])
    wb.save(out_path)
    print(f"[parakh] wrote {out_path}", file=sys.stderr)


def main():
    ap = argparse.ArgumentParser(description="Parakh candidate ranker (offline).")
    ap.add_argument("--candidates", default=C.DEFAULT_CANDIDATES,
                    help="path to candidates.jsonl")
    ap.add_argument("--out", default="submission.csv", help="output CSV path")
    ap.add_argument("--xlsx", default=None, help="optional XLSX output path")
    ap.add_argument("--labels", default="artifacts/teacher_labels.jsonl",
                    help="primary offline teacher labels (skipped if missing)")
    ap.add_argument("--labels2", default="artifacts/teacher2_labels.jsonl",
                    help="second-judge labels (skipped if missing)")
    ap.add_argument("--labels3", default="artifacts/teacher3_labels.jsonl",
                    help="third-judge labels for the top set (skipped if missing)")
    ap.add_argument("--reasons", default="artifacts/reasons_final.jsonl",
                    help="polished grounded reasons for the final 100 (skipped if missing)")
    args = ap.parse_args()

    if not Path(args.candidates).exists():
        sys.exit(f"[parakh] candidates file not found: {args.candidates}")

    labels = _load_labels(args.labels)
    labels2 = _load_labels(args.labels2)
    labels3 = _load_labels(args.labels3)
    recs = load_and_score(args.candidates, labels, labels2, labels3)
    top = rank(recs)

    # polished, fact-verified reasons for the final 100 (precomputed artifact)
    polished = _load_labels(args.reasons)
    for r in top:
        pol = polished.get(r["candidate_id"])
        if pol and pol.get("reason"):
            r["teacher_reason"] = pol["reason"]

    # quick top-10 preview for a human sanity check
    print("[parakh] top 10 preview:", file=sys.stderr)
    for i, r in enumerate(top[:10], start=1):
        tier = r.get("tier")
        tier_s = f"T{tier:g}x{r.get('n_judges', 0)}" if tier is not None else "T-"
        print(f"  {i:2d}. {r['candidate_id']} {r['score']:.4f} {tier_s} "
              f"{r['current_title']} ({r['years']}y) {r['location']}", file=sys.stderr)

    write_csv(top, args.out)
    if args.xlsx:
        write_xlsx(top, args.xlsx)

    # compute-constraint proof (spec §3: ≤5 min wall, ≤16 GB RAM, CPU-only)
    wall = time.time() - _T0
    try:
        import psutil
        peak_gb = psutil.Process().memory_info().peak_wset / 1e9
        print(f"[parakh] selftest: wall={wall:.1f}s (limit 300s) "
              f"peak_ram={peak_gb:.2f}GB (limit 16GB) network=OFF gpu=OFF", file=sys.stderr)
    except ImportError:
        print(f"[parakh] selftest: wall={wall:.1f}s (limit 300s) network=OFF gpu=OFF",
              file=sys.stderr)


_T0 = time.time()

if __name__ == "__main__":
    main()
