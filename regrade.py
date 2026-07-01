#!/usr/bin/env python3
"""
Parakh — finalist re-grade (offline pre-compute).

Grade the top-N candidates of an existing ranking with a SECOND independent
teacher model, so the ranker can require cross-model agreement for the very top
(the "quorum" idea). Writes a separate labels file that rank.py ensembles.

    python regrade.py --csv submission_teacher.csv --top 250 \
        --model deepseek-ai/DeepSeek-V4-Pro --out artifacts/teacher2_labels.jsonl
"""

from __future__ import annotations
import argparse
import json
import sys
import threading
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path

from parakh import config as C
from parakh.nebius import client
from precompute import grade
from eval import read_top, load_profiles

_lock = threading.Lock()


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--csv", required=True)
    ap.add_argument("--candidates", default=C.DEFAULT_CANDIDATES)
    ap.add_argument("--top", type=int, default=250)
    ap.add_argument("--model", default="deepseek-ai/DeepSeek-V4-Pro")
    ap.add_argument("--out", default="artifacts/teacher2_labels.jsonl")
    ap.add_argument("--workers", type=int, default=20)
    args = ap.parse_args()

    out = Path(args.out)
    out.parent.mkdir(exist_ok=True)
    done = set()
    if out.exists():
        for line in out.open(encoding="utf-8"):
            try:
                done.add(json.loads(line)["candidate_id"])
            except (json.JSONDecodeError, KeyError):
                pass

    ids = read_top(args.csv, args.top)
    profiles = load_profiles(args.candidates, ids)
    todo = [profiles[i] for i in ids if i in profiles and i not in done]
    print(f"[regrade] {len(done)} cached, {len(todo)} to grade "
          f"(model={args.model})", file=sys.stderr)
    if not todo:
        return

    cl = client()
    tier_hist = {}
    with out.open("a", encoding="utf-8") as f, ThreadPoolExecutor(args.workers) as ex:
        futs = {ex.submit(grade, cl, c, args.model): c for c in todo}
        for fut in as_completed(futs):
            c = futs[fut]
            tier, reason = fut.result()
            with _lock:
                f.write(json.dumps({"candidate_id": c["candidate_id"],
                                    "tier": tier, "reason": reason}) + "\n")
            tier_hist[tier] = tier_hist.get(tier, 0) + 1
    print(f"[regrade] done; tiers={dict(sorted(tier_hist.items(), key=lambda x: str(x[0])))}",
          file=sys.stderr)


if __name__ == "__main__":
    main()
