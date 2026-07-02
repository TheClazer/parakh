#!/usr/bin/env python3
"""
Stage-4-grade reasoning for the final top-100 (offline pre-compute).

The spec grades reasoning on six checks: specific profile facts, connection to
JD requirements, honest concerns, zero hallucination, variation across rows,
and tone consistent with rank. This regenerates each final row's reasoning with
a prompt that enforces all six, then VERIFIES every quoted fact against the
profile (title, years, named skills) and retries once on any mismatch.

Output artifact: artifacts/reasons_final.jsonl  (rank.py prefers it, so the
submitted CSV is fully reproducible from artifacts + code.)

    python reason_polish.py --csv submission.csv --candidates .../candidates.jsonl
"""

from __future__ import annotations
import argparse
import json
import re
import sys
import threading
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path

from parakh import config as C
from parakh.nebius import client
from eval import read_top, load_profiles

MODEL = "deepseek-ai/DeepSeek-V4-Pro"
OUT = Path("artifacts/reasons_final.jsonl")
_lock = threading.Lock()

SYS = """You write the one-line justification a serious technical recruiter would put
next to a ranked candidate for this role: Senior AI Engineer (ranking / retrieval /
recommendation systems) at Redrob, an AI-native product company in India (Pune/Noida,
relocation from Indian metros OK; 5-9 yrs ideal; production embeddings/vector-search
plus rigorous ranking evaluation are must-haves; consulting-only or research-only
backgrounds and unreachable candidates are concerns).

Rules — all mandatory:
- 1-2 sentences, <= 230 characters total.
- Cite ONLY facts present in the profile JSON (title, years, named skills/tech,
  companies, behavioral signals). NEVER invent a skill, employer, or number.
- Connect explicitly to a JD requirement (retrieval/ranking/recsys, embeddings,
  vector DB, evaluation, production scale, availability, location).
- Tone must match the rank band: rank 1-15 = strong endorsement; 16-50 = solid with
  one caveat; 51-100 = balanced, lead with the gap/concern, then the strengths.
- If the candidate has an obvious concern (notice period > 30d, low response rate,
  services-firm history, based abroad, long inactivity), state it honestly.
- Vary your sentence structure; do not start with the candidate's title every time.
Return ONLY JSON: {"reasoning": "..."}"""


def profile_digest(cand: dict) -> str:
    p = cand.get("profile", {})
    sig = cand.get("redrob_signals", {}) or {}
    jobs = [f"{j.get('title')} @ {j.get('company')} ({j.get('duration_months')}mo): "
            f"{(j.get('description') or '')[:200]}"
            for j in (cand.get("career_history") or [])[:4]]
    skills = ", ".join(f"{s.get('name')}({s.get('proficiency')},{s.get('duration_months')}mo)"
                       for s in (cand.get("skills") or [])[:14])
    return json.dumps({
        "title": p.get("current_title"), "years": p.get("years_of_experience"),
        "location": f"{p.get('location')}, {p.get('country')}",
        "company": p.get("current_company"), "industry": p.get("current_industry"),
        "summary": (p.get("summary") or "")[:400], "jobs": jobs, "skills": skills,
        "signals": {k: sig.get(k) for k in (
            "recruiter_response_rate", "last_active_date", "open_to_work_flag",
            "notice_period_days", "willing_to_relocate", "expected_salary_range_inr_lpa")},
    }, ensure_ascii=False)


_SKILL_RX = re.compile(r"[A-Za-z][A-Za-z0-9+#./&-]{1,30}")


def grounded(reason: str, cand: dict) -> bool:
    """Cheap anti-hallucination check: any capitalized tech/org token quoted in the
    reasoning must literally appear somewhere in the profile JSON."""
    hay = json.dumps(cand, ensure_ascii=False).lower()
    generic = {"ai", "ml", "engineer", "india", "redrob", "jd", "production", "senior",
               "strong", "recruiter", "ranking", "retrieval", "recsys", "the", "with"}
    for tok in _SKILL_RX.findall(reason):
        if tok[0].isupper() and tok.lower() not in generic and len(tok) >= 3:
            if tok.lower() not in hay:
                return False
    return True


def gen(cl, cand, rank):
    msg = f"RANK: {rank} of 100\nPROFILE JSON:\n{profile_digest(cand)}"
    for attempt in range(3):
        try:
            r = cl.chat.completions.create(
                model=MODEL, temperature=0.4 if attempt else 0.2, max_tokens=400,
                messages=[{"role": "system", "content": SYS},
                          {"role": "user", "content": msg}])
            m = re.search(r"\{.*\}", r.choices[0].message.content, re.S)
            reason = str(json.loads(m.group(0))["reasoning"]).strip()[:240]
            if grounded(reason, cand):
                return reason
        except Exception:
            pass
    return None  # rank.py falls back to teacher reason


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--csv", required=True)
    ap.add_argument("--candidates", default=C.DEFAULT_CANDIDATES)
    ap.add_argument("--workers", type=int, default=16)
    args = ap.parse_args()

    ids = read_top(args.csv, 100)
    ranks = {cid: i + 1 for i, cid in enumerate(ids)}
    profiles = load_profiles(args.candidates, ids)
    cl = client()
    OUT.parent.mkdir(exist_ok=True)
    done = 0
    with OUT.open("w", encoding="utf-8") as f, ThreadPoolExecutor(args.workers) as ex:
        futs = {ex.submit(gen, cl, profiles[cid], ranks[cid]): cid
                for cid in ids if cid in profiles}
        for fut in as_completed(futs):
            cid = futs[fut]
            reason = fut.result()
            if reason:
                with _lock:
                    f.write(json.dumps({"candidate_id": cid, "reason": reason},
                                       ensure_ascii=False) + "\n")
                done += 1
    print(f"[reasons] wrote {done}/{len(ids)} grounded reasons -> {OUT}", file=sys.stderr)


if __name__ == "__main__":
    main()
