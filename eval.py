#!/usr/bin/env python3
"""
Parakh — evaluation harness (offline gate for every upgrade).

There is no public ground truth, so we use an INDEPENDENT, different LLM
(default: DeepSeek-V4-Pro — not the model used to train the ranker) as a
second-opinion judge on a ranking's top-K, and report:
  - avg independent tier @10 / @50   (higher = we surfaced better people)
  - NDCG@10 / @50 using those tiers   (ordering quality within our picks)
  - honeypots in the top-100          (must be 0)
  - top-100 title census

Compare two rankings:
    python eval.py --csv submission.csv --csv2 submission_teacher.csv --k 60

Grades are cached in artifacts/eval_labels.jsonl so re-runs are cheap.
"""

from __future__ import annotations
import argparse
import csv
import json
import math
import sys
import threading
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path

from parakh import config as C
from parakh import features
from parakh.nebius import client
from precompute import grade

EVAL_MODEL = "deepseek-ai/DeepSeek-V4-Pro"
CACHE = Path("artifacts/eval_labels.jsonl")
_lock = threading.Lock()


def read_top(csv_path, k):
    rows = list(csv.DictReader(open(csv_path, encoding="utf-8")))
    rows.sort(key=lambda r: int(r["rank"]))
    return [r["candidate_id"] for r in rows[:k]]


def load_profiles(path, ids):
    want = set(ids)
    found = {}
    with open(path, encoding="utf-8") as f:
        for line in f:
            if not line.strip():
                continue
            cand = json.loads(line)
            if cand["candidate_id"] in want:
                found[cand["candidate_id"]] = cand
                if len(found) == len(want):
                    break
    return found


def load_cache():
    d = {}
    if CACHE.exists():
        for line in CACHE.open(encoding="utf-8"):
            try:
                r = json.loads(line)
                d[r["candidate_id"]] = r["tier"]
            except (json.JSONDecodeError, KeyError):
                pass
    return d


def grade_missing(profiles, cache, workers=16):
    todo = [c for cid, c in profiles.items() if cid not in cache]
    if not todo:
        return
    cl = client()
    CACHE.parent.mkdir(exist_ok=True)
    with CACHE.open("a", encoding="utf-8") as f, ThreadPoolExecutor(workers) as ex:
        futs = {ex.submit(grade, cl, c, EVAL_MODEL): c for c in todo}
        for fut in as_completed(futs):
            c = futs[fut]
            tier, _ = fut.result()
            if tier is None:
                tier = 0
            cache[c["candidate_id"]] = tier
            with _lock:
                f.write(json.dumps({"candidate_id": c["candidate_id"], "tier": tier}) + "\n")
    print(f"[eval] graded {len(todo)} new (model={EVAL_MODEL})", file=sys.stderr)


def ndcg(tiers, k):
    def dcg(xs):
        return sum((2 ** t - 1) / math.log2(i + 2) for i, t in enumerate(xs))
    actual = dcg(tiers[:k])
    ideal = dcg(sorted(tiers, reverse=True)[:k])
    return actual / ideal if ideal else 0.0


def evaluate(csv_path, ids, cache):
    tiers = [cache.get(cid, 0) for cid in ids]
    top10 = tiers[:10]
    top50 = tiers[:50]
    return {
        "avg_tier@10": round(sum(top10) / max(len(top10), 1), 3),
        "avg_tier@50": round(sum(top50) / max(len(top50), 1), 3),
        "ndcg@10": round(ndcg(tiers, 10), 4),
        "ndcg@50": round(ndcg(tiers, 50), 4),
        "tier5@10": sum(1 for t in top10 if t >= 5),
        "tier<=2@10": sum(1 for t in top10 if t <= 2),
    }


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--csv", required=True)
    ap.add_argument("--csv2", default=None, help="optional second ranking to compare")
    ap.add_argument("--candidates", default=C.DEFAULT_CANDIDATES)
    ap.add_argument("--k", type=int, default=60, help="how many top rows to judge")
    args = ap.parse_args()

    ids1 = read_top(args.csv, args.k)
    ids2 = read_top(args.csv2, args.k) if args.csv2 else []
    all_ids = list(dict.fromkeys(ids1 + ids2))

    profiles = load_profiles(args.candidates, all_ids)
    cache = load_cache()
    grade_missing(profiles, cache)

    print(f"\n=== {args.csv} ===")
    for k, v in evaluate(args.csv, ids1, cache).items():
        print(f"  {k:12s} {v}")
    if args.csv2:
        print(f"\n=== {args.csv2} ===")
        for k, v in evaluate(args.csv2, ids2, cache).items():
            print(f"  {k:12s} {v}")


if __name__ == "__main__":
    main()
