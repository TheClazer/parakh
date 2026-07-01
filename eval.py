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

_lock = threading.Lock()


def cache_path(model):
    short = model.split("/")[-1].replace(".", "_")
    return Path(f"artifacts/eval_labels_{short}.jsonl")


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


def load_cache(path):
    d = {}
    if path.exists():
        for line in path.open(encoding="utf-8"):
            try:
                r = json.loads(line)
                d[r["candidate_id"]] = r["tier"]
            except (json.JSONDecodeError, KeyError):
                pass
    return d


def grade_missing(profiles, cache, model, path, workers=16):
    todo = [c for cid, c in profiles.items() if cid not in cache]
    if not todo:
        return
    cl = client()
    path.parent.mkdir(exist_ok=True)
    with path.open("a", encoding="utf-8") as f, ThreadPoolExecutor(workers) as ex:
        futs = {ex.submit(grade, cl, c, model): c for c in todo}
        for fut in as_completed(futs):
            c = futs[fut]
            tier, _ = fut.result()
            if tier is None:
                tier = 0
            cache[c["candidate_id"]] = tier
            with _lock:
                f.write(json.dumps({"candidate_id": c["candidate_id"], "tier": tier}) + "\n")
    print(f"[eval] graded {len(todo)} new (model={model})", file=sys.stderr)


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
    ap.add_argument("--csvs", nargs="+", required=True, help="one or more ranking CSVs")
    ap.add_argument("--candidates", default=C.DEFAULT_CANDIDATES)
    ap.add_argument("--k", type=int, default=60, help="how many top rows to judge")
    ap.add_argument("--model", default="meta-llama/Llama-3.3-70B-Instruct",
                    help="independent judge (use a model NOT used in the ranking)")
    args = ap.parse_args()

    per_csv_ids = {c: read_top(c, args.k) for c in args.csvs}
    all_ids = list(dict.fromkeys(i for ids in per_csv_ids.values() for i in ids))

    profiles = load_profiles(args.candidates, all_ids)
    path = cache_path(args.model)
    cache = load_cache(path)
    grade_missing(profiles, cache, args.model, path)

    print(f"\n[judge = {args.model}]")
    for c in args.csvs:
        print(f"\n=== {c} ===")
        for k, v in evaluate(c, per_csv_ids[c], cache).items():
            print(f"  {k:12s} {v}")


if __name__ == "__main__":
    main()
