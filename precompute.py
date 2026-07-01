#!/usr/bin/env python3
"""
Parakh — PRE-COMPUTE (offline, network allowed; NOT the ranking step).

Uses the Nebius LLM as a "teacher": shortlist the plausible candidates by the
rule score, then have the teacher grade each on a 0-5 fit tier + short reason.
Results are cached to artifacts/teacher_labels.jsonl and later (a) blended into
the ranking and (b) used as labels to train the LightGBM ranker.

    python precompute.py --candidates ./candidates.jsonl --shortlist 3000 --workers 24

Re-runnable: already-labelled candidate_ids are skipped.
"""

from __future__ import annotations
import argparse
import datetime
import heapq
import json
import re
import sys
import threading
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path

from parakh import config as C
from parakh import features, score
from parakh.nebius import client, TEACHER_MODEL

REF_DATE = datetime.date(2026, 6, 30)
OUT_PATH = Path("artifacts/teacher_labels.jsonl")

RUBRIC = """\
ROLE: Senior AI Engineer at a Series A, AI-native PRODUCT company (Redrob). Owns the
ranking / retrieval / matching intelligence layer. Ships fast; writes production code.

TIER 5 (excellent hire):
- 5-9 yrs (ideal 6-8), most in applied ML/AI at PRODUCT companies (not services).
- Has SHIPPED an end-to-end search / ranking / recommendation / retrieval system to
  real users at meaningful scale.
- Production embeddings-based retrieval (sentence-transformers/BGE/E5/etc.) AND
  vector DB / hybrid search (Pinecone/Weaviate/Qdrant/Milvus/FAISS/Elasticsearch).
- Rigorous ranking evaluation (NDCG/MRR/MAP, A/B testing). Hands-on IC.
- In India or willing to relocate (Noida/Pune/Hyderabad/Mumbai/Delhi-NCR/Bengaluru).
NICE: LoRA/QLoRA/PEFT, learning-to-rank, HR-tech, distributed systems, open-source.

Grade DOWN toward tier 0-1 for:
- Keyword-stuffer: lists AI skills but the career NARRATIVE shows no real ML/retrieval
  work, or the role is wrong (Marketing/HR/Ops/Sales/Design/Accounting/etc.).
- Honeypot / impossible profile (inconsistent dates; "expert" skills with 0 experience).
- Pure research / academia with no production deployment.
- "AI experience" only recent (<12mo) LangChain-calling-an-LLM with no real ML depth.
- Whole career at IT-services/consulting (TCS/Infosys/Wipro/Accenture/Cognizant/etc.).
- Primarily computer-vision / speech / robotics without NLP/IR.
- Title-chaser (job-hops <1.5y for title) or hasn't written code in 18+ months.
- Based abroad and NOT willing to relocate.

Behavioral availability (recruiter response rate, recent activity, open-to-work, notice
period) is a modifier, not the main signal.

TIERS: 5=excellent, 4=strong, 3=relevant/worth-a-look, 2=weak/adjacent, 1=poor, 0=not a fit/trap."""

SYS_PROMPT = ("You are a senior technical recruiter grading candidate fit for the role "
              "below. Judge the actual described work, not keywords. Return ONLY a JSON "
              'object: {"tier": <int 0-5>, "reason": "<=180 chars, specific and honest"}.\n\n'
              + RUBRIC)

_write_lock = threading.Lock()


def serialize(cand: dict) -> str:
    p = cand.get("profile", {})
    sig = cand.get("redrob_signals", {}) or {}
    out = [f"Title: {p.get('current_title')} | Exp: {p.get('years_of_experience')}y | "
           f"{p.get('location')}, {p.get('country')} | current_company: "
           f"{p.get('current_company')} ({p.get('current_company_size')}, {p.get('current_industry')})"]
    if p.get("summary"):
        out.append("Summary: " + p["summary"][:500])
    out.append("Career:")
    for j in (cand.get("career_history") or [])[:5]:
        out.append(f"- {j.get('title')} @ {j.get('company')} "
                   f"({j.get('company_size')}, {j.get('industry')}), "
                   f"{j.get('duration_months')}mo: {(j.get('description') or '')[:300]}")
    sk = cand.get("skills") or []
    out.append("Skills: " + ", ".join(
        f"{s.get('name')}[{(s.get('proficiency') or '')[:3]},{s.get('duration_months','?')}mo]"
        for s in sk[:16]))
    out.append(f"Signals: response_rate={sig.get('recruiter_response_rate')} "
               f"last_active={sig.get('last_active_date')} open_to_work={sig.get('open_to_work_flag')} "
               f"notice_days={sig.get('notice_period_days')} willing_relocate={sig.get('willing_to_relocate')} "
               f"github={sig.get('github_activity_score')} saved_by_recruiters={sig.get('saved_by_recruiters_30d')}")
    return "\n".join(out)


def grade(cl, cand, model=TEACHER_MODEL):
    txt = serialize(cand)
    for attempt in range(4):
        try:
            r = cl.chat.completions.create(
                model=model, temperature=0, max_tokens=200,
                messages=[{"role": "system", "content": SYS_PROMPT},
                          {"role": "user", "content": txt}])
            raw = r.choices[0].message.content.strip()
            m = re.search(r"\{.*\}", raw, re.S)
            d = json.loads(m.group(0))
            tier = int(d["tier"])
            return max(0, min(5, tier)), str(d.get("reason", ""))[:200]
        except Exception as e:  # noqa: BLE001
            if attempt == 3:
                return None, f"ERR:{type(e).__name__}:{str(e)[:80]}"
            time.sleep(1.5 * (attempt + 1))


def shortlist(path, n):
    """Single streaming pass; keep the top-n non-honeypot candidates by rule score."""
    heap = []  # (score, counter, cand)
    counter = 0
    total = 0
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
            total += 1
            rec = features.extract(cand, REF_DATE)
            if rec["honeypot"]:
                continue
            s = score.score(rec)
            counter += 1
            if len(heap) < n:
                heapq.heappush(heap, (s, counter, cand))
            elif s > heap[0][0]:
                heapq.heapreplace(heap, (s, counter, cand))
    print(f"[precompute] scanned {total} in {time.time()-t0:.0f}s; "
          f"shortlisted {len(heap)}", file=sys.stderr)
    return [c for _, _, c in sorted(heap, key=lambda x: -x[0])]


def load_done():
    done = {}
    if OUT_PATH.exists():
        for line in OUT_PATH.open(encoding="utf-8"):
            try:
                d = json.loads(line)
                done[d["candidate_id"]] = d
            except (json.JSONDecodeError, KeyError):
                pass
    return done


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--candidates", default=C.DEFAULT_CANDIDATES)
    ap.add_argument("--shortlist", type=int, default=3000)
    ap.add_argument("--workers", type=int, default=24)
    ap.add_argument("--limit", type=int, default=0, help="grade only first N (testing)")
    args = ap.parse_args()

    OUT_PATH.parent.mkdir(exist_ok=True)
    cands = shortlist(args.candidates, args.shortlist)
    if args.limit:
        cands = cands[:args.limit]

    done = load_done()
    todo = [c for c in cands if c["candidate_id"] not in done]
    print(f"[precompute] {len(done)} cached, {len(todo)} to grade "
          f"(model={TEACHER_MODEL}, workers={args.workers})", file=sys.stderr)
    if not todo:
        return

    cl = client()
    t0 = time.time()
    n_done = 0
    tier_hist = {}
    with OUT_PATH.open("a", encoding="utf-8") as fout, \
            ThreadPoolExecutor(max_workers=args.workers) as ex:
        futs = {ex.submit(grade, cl, c): c for c in todo}
        for fut in as_completed(futs):
            c = futs[fut]
            tier, reason = fut.result()
            rec = {"candidate_id": c["candidate_id"], "tier": tier, "reason": reason}
            with _write_lock:
                fout.write(json.dumps(rec) + "\n")
                fout.flush()
            n_done += 1
            tier_hist[tier] = tier_hist.get(tier, 0) + 1
            if n_done % 100 == 0:
                rate = n_done / (time.time() - t0)
                eta = (len(todo) - n_done) / rate
                print(f"[precompute] {n_done}/{len(todo)}  {rate:.1f}/s  "
                      f"ETA {eta/60:.1f}m  tiers={dict(sorted(tier_hist.items(), key=lambda x:str(x[0])))}",
                      file=sys.stderr)
    print(f"[precompute] done {n_done} in {(time.time()-t0)/60:.1f}m  "
          f"tiers={dict(sorted(tier_hist.items(), key=lambda x:str(x[0])))}", file=sys.stderr)


if __name__ == "__main__":
    main()
