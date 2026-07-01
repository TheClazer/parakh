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


def load_and_score(path: str):
    recs = []
    n = 0
    honeypots = stuffers = 0
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
            rec["score"] = score.score(rec)
            if rec["honeypot"]:
                honeypots += 1
            if rec["stuffer"]:
                stuffers += 1
            # keep memory lean: only retain plausible candidates + a margin
            recs.append(rec)
    dt = time.time() - t0
    print(f"[parakh] scored {n} candidates in {dt:.1f}s "
          f"({honeypots} honeypots, {stuffers} stuffers flagged)", file=sys.stderr)
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
            w.writerow([r["candidate_id"], i, f"{r['score']:.6f}", score.reason(r)])
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
        ws.append([r["candidate_id"], i, round(r["score"], 6), score.reason(r)])
    wb.save(out_path)
    print(f"[parakh] wrote {out_path}", file=sys.stderr)


def main():
    ap = argparse.ArgumentParser(description="Parakh candidate ranker (offline).")
    ap.add_argument("--candidates", default=C.DEFAULT_CANDIDATES,
                    help="path to candidates.jsonl")
    ap.add_argument("--out", default="submission.csv", help="output CSV path")
    ap.add_argument("--xlsx", default=None, help="optional XLSX output path")
    args = ap.parse_args()

    if not Path(args.candidates).exists():
        sys.exit(f"[parakh] candidates file not found: {args.candidates}")

    recs = load_and_score(args.candidates)
    top = rank(recs)

    # quick top-10 preview for a human sanity check
    print("[parakh] top 10 preview:", file=sys.stderr)
    for i, r in enumerate(top[:10], start=1):
        print(f"  {i:2d}. {r['candidate_id']} {r['score']:.4f} "
              f"{r['current_title']} ({r['years']}y) {r['location']}", file=sys.stderr)

    write_csv(top, args.out)
    if args.xlsx:
        write_xlsx(top, args.xlsx)


if __name__ == "__main__":
    main()
