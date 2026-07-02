"""
Parakh — the Integrity Gate.

Assay each profile for internal consistency BEFORE trusting its content.
This is what keeps honeypots (~80 impossible profiles, ground-truth tier 0) and
blatant keyword-stuffers out of the top-100 — the >10% honeypot rule is an
automatic disqualifier, so this module is load-bearing.

Signatures were confirmed empirically on the full 100k pool (see README audit):
  - `expert` proficiency + 0 months used  → ~84 hits ≈ the ~80 honeypots.
  - single job / skill tenure exceeding the whole career length.
  - date impossibilities (end before start; is_current vs end_date mismatch).
"""

from __future__ import annotations
import datetime


def _date(s):
    if not s:
        return None
    try:
        return datetime.date.fromisoformat(s)
    except (ValueError, TypeError):
        return None


def _months_between(a, b):
    if not a or not b:
        return None
    return (b.year - a.year) * 12 + (b.month - a.month)


def honeypot_flags(cand: dict) -> list[str]:
    """Return a list of impossibility reasons; non-empty => treat as honeypot."""
    flags: list[str] = []
    yoe = cand.get("profile", {}).get("years_of_experience", 0) or 0
    budget_months = yoe * 12 + 6  # small slack for rounding

    # 1) expert proficiency in a skill used for 0 months (the signature honeypot).
    #    NOTE: we deliberately do NOT flag "skill duration > career length" — the
    #    audit showed that fires on ~30% of the pool (generator noise), not
    #    honeypots. Only the expert+0-months signature is reliable (~84 ≈ the ~80).
    for s in cand.get("skills", []) or []:
        if s.get("proficiency") == "expert" and s.get("duration_months") == 0:
            flags.append(f"expert_but_0_months:{s.get('name')}")

    # 2) career-history logic
    n_current = 0
    for j in cand.get("career_history", []) or []:
        sd, ed = _date(j.get("start_date")), _date(j.get("end_date"))
        dm = j.get("duration_months", 0) or 0
        if j.get("is_current"):
            n_current += 1
            if j.get("end_date"):
                flags.append("current_job_has_end_date")
        if dm > budget_months:
            flags.append("job_tenure_exceeds_career")
        if sd and ed and ed < sd:
            flags.append("job_end_before_start")
        mb = _months_between(sd, ed)
        if mb is not None and abs(mb - dm) > 3:
            flags.append("duration_contradicts_dates")
    if n_current > 1:
        flags.append("multiple_current_jobs")

    # 3) education logic
    for e in cand.get("education", []) or []:
        sy, ey = e.get("start_year"), e.get("end_year")
        if isinstance(sy, int) and isinstance(ey, int) and ey < sy:
            flags.append("edu_end_before_start")

    # 4) platform-signal logic — active before they ever signed up is impossible
    sig = cand.get("redrob_signals", {}) or {}
    su, la = _date(sig.get("signup_date")), _date(sig.get("last_active_date"))
    if su and la and la < su:
        flags.append("active_before_signup")

    # 5) the README's own example: "expert proficiency in 10 skills with 0 years used"
    #    — generalized: implausibly many expert claims for a very short career
    yoe_short = yoe < 3
    n_expert = sum(1 for s in cand.get("skills", []) or [] if s.get("proficiency") == "expert")
    if yoe_short and n_expert >= 8:
        flags.append("expert_stack_vs_career_length")

    return flags


# skills the audit flags as "AI-core" (used only to spot keyword-stuffing)
_AICORE = {
    "NLP", "Embeddings", "RAG", "Retrieval", "Vector Search", "Semantic Search",
    "Fine-tuning LLMs", "LLMs", "Transformers", "Recommendation Systems",
    "Information Retrieval", "Ranking", "Sentence Transformers", "Machine Learning",
    "Deep Learning", "PyTorch", "TensorFlow", "Learning to Rank", "FAISS",
}


def is_keyword_stuffer(cand: dict, text_blob: str, evidence_hits: int) -> bool:
    """
    A stuffer wears the keywords but the work doesn't back them up:
    a non-technical current title, many AI-core skills, yet ZERO supporting
    evidence in the actual career narrative.
    """
    title = cand.get("profile", {}).get("current_title", "")
    from .config import NONTECH_TITLES  # local import to avoid cycle at import time

    skill_names = {s.get("name") for s in cand.get("skills", []) or []}
    ai_skills = len(skill_names & _AICORE)
    return title in NONTECH_TITLES and ai_skills >= 4 and evidence_hits == 0
