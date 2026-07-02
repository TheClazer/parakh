#!/usr/bin/env python3
"""
Recall-rescue sweep (offline pre-compute).

The teacher shortlist was chosen by rule score — if the rules under-rank a
plain-language gem, no LLM ever graded it. This sweep scans ALL 100k for
candidates with genuine narrative evidence (retrieval / ranking / recsys /
embeddings work described in their career text) or ML titles that did NOT make
the graded set, and emits them for teacher grading.

    python sweep.py --candidates ../.../candidates.jsonl \
        --graded artifacts/teacher_ds.jsonl artifacts/teacher_labels.jsonl \
        --out artifacts/sweep_ids.txt --cap 2500
"""

from __future__ import annotations
import argparse
import datetime
import json
import sys

from parakh import config as C
from parakh import features

REF_DATE = datetime.date(2026, 6, 30)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--candidates", default=C.DEFAULT_CANDIDATES)
    ap.add_argument("--graded", nargs="+", default=["artifacts/teacher_ds.jsonl",
                                                    "artifacts/teacher_labels.jsonl"])
    ap.add_argument("--out", default="artifacts/sweep_ids.txt")
    ap.add_argument("--cap", type=int, default=2500)
    args = ap.parse_args()

    graded = set()
    for path in args.graded:
        try:
            for line in open(path, encoding="utf-8"):
                try:
                    graded.add(json.loads(line)["candidate_id"])
                except (json.JSONDecodeError, KeyError):
                    pass
        except FileNotFoundError:
            pass
    print(f"[sweep] already graded: {len(graded)}", file=sys.stderr)

    picks = []
    n = 0
    for line in open(args.candidates, encoding="utf-8"):
        line = line.strip()
        if not line:
            continue
        try:
            cand = json.loads(line)
        except json.JSONDecodeError:
            continue
        n += 1
        cid = cand.get("candidate_id")
        if cid in graded:
            continue
        rec = features.extract(cand, REF_DATE)
        if rec["honeypot"] or rec["stuffer"]:
            continue
        # a missed gem: real narrative evidence of the JD's core systems,
        # or an ML/AI title anywhere in their history
        interesting = rec["evidence_hits"] >= 1 or rec["role"] > 0
        if not interesting:
            continue
        # priority: how much signal the narrative carries + JD must-haves
        prio = (rec["evidence_hits"] * 2.0 + rec["musthave_hits"] * 1.5
                + rec["role"] * 2.0 + rec["prod_hit"] * 1.0
                + rec["location_s"] * 0.5 + rec["exp"] * 0.5)
        picks.append((prio, cid))

    picks.sort(reverse=True)
    picks = picks[: args.cap]
    with open(args.out, "w", encoding="utf-8") as f:
        for _, cid in picks:
            f.write(cid + "\n")
    print(f"[sweep] scanned {n}; ungraded-with-signal kept: {len(picks)} -> {args.out}",
          file=sys.stderr)


if __name__ == "__main__":
    main()
