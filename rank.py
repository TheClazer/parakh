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


def load_and_score(path, labels=None):
    """Score every candidate. When an offline teacher label exists, the teacher
    tier (0-5) is the dominant signal and the rule score orders within a tier:
        blended = (tier + min(rule, 0.999)) / 6      -> in [0, 1]
    Unlabeled candidates (e.g. a fresh sandbox sample) fall back to the rule
    score alone, mapped into the tier-0 band so they never outrank a graded fit.
    """
    labels = labels or {}
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
            lab = labels.get(rec["candidate_id"])
            if lab and lab.get("tier") is not None and not rec["honeypot"]:
                rec["tier"] = lab["tier"]
                rec["teacher_reason"] = (lab.get("reason") or "").strip()
                rec["score"] = (lab["tier"] + min(rule, 0.999)) / 6.0
                teacher_used += 1
            else:
                rec["tier"] = None
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
                    help="offline teacher labels (skipped if missing)")
    args = ap.parse_args()

    if not Path(args.candidates).exists():
        sys.exit(f"[parakh] candidates file not found: {args.candidates}")

    labels = {}
    if args.labels and Path(args.labels).exists():
        for line in open(args.labels, encoding="utf-8"):
            try:
                d = json.loads(line)
                labels[d["candidate_id"]] = d
            except (json.JSONDecodeError, KeyError):
                pass
        print(f"[parakh] loaded {len(labels)} teacher labels from {args.labels}",
              file=sys.stderr)

    recs = load_and_score(args.candidates, labels)
    top = rank(recs)

    # quick top-10 preview for a human sanity check
    print("[parakh] top 10 preview:", file=sys.stderr)
    for i, r in enumerate(top[:10], start=1):
        tier = r.get("tier")
        tier_s = f"T{tier}" if tier is not None else "T-"
        print(f"  {i:2d}. {r['candidate_id']} {r['score']:.4f} {tier_s} "
              f"{r['current_title']} ({r['years']}y) {r['location']}", file=sys.stderr)

    write_csv(top, args.out)
    if args.xlsx:
        write_xlsx(top, args.xlsx)


if __name__ == "__main__":
    main()
