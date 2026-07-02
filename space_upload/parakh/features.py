"""
Parakh — per-candidate feature extraction.

Turns a raw candidate record into a compact `rec` dict holding everything the
scorer and the reasoning generator need. Raw text is scanned here and then
dropped, so we keep memory modest across the 100k pool.
"""

from __future__ import annotations
import datetime
from . import config as C
from . import integrity


def _date(s):
    try:
        return datetime.date.fromisoformat(s) if s else None
    except (ValueError, TypeError):
        return None


def build_narrative(cand: dict) -> str:
    """The candidate's *story*: headline, summary, job titles + descriptions.
    Deliberately EXCLUDES the skills list — skills are cheap to stuff, so real
    evidence of building systems must come from the narrative, not a keyword tag.
    """
    p = cand.get("profile", {})
    parts = [p.get("headline", ""), p.get("summary", "")]
    for j in cand.get("career_history", []) or []:
        parts.append(j.get("title", ""))
        parts.append(j.get("description", ""))
    return "  ".join(x for x in parts if x)


def build_skills_text(cand: dict) -> str:
    return "  ".join(s.get("name", "") for s in cand.get("skills", []) or [])


def _clip01(x):
    return 0.0 if x < 0 else 1.0 if x > 1 else x


def extract(cand: dict, ref_date: datetime.date) -> dict:
    """Return a compact feature record for one candidate."""
    p = cand.get("profile", {})
    sig = cand.get("redrob_signals", {}) or {}
    ch = cand.get("career_history", []) or []
    narrative = build_narrative(cand)          # the story (no skills)
    skills_text = build_skills_text(cand)      # the tags (stuffable)
    combined = narrative + "  " + skills_text

    # --- role: current + any past ML/AI/IR title ---
    titles = [p.get("current_title", "")] + [j.get("title", "") for j in ch]
    role_hit_current = bool(C.ML_TITLE_RX.search(p.get("current_title", "") or ""))
    role_hit_any = any(C.ML_TITLE_RX.search(t or "") for t in titles)
    role = 1.0 if role_hit_current else (0.6 if role_hit_any else 0.0)

    # --- evidence: gem work must be DESCRIBED (narrative only) ---
    evidence_hits = len(set(m.group(0).lower() for m in C.EVIDENCE_RX.finditer(narrative)))
    # must-have tech can come from narrative OR skills (FAISS/Pinecone as a skill counts)
    musthave_hits = len(set(m.group(0).lower() for m in C.MUSTHAVE_RX.finditer(combined)))
    nice_hits = len(set(m.group(0).lower() for m in C.NICE_RX.finditer(combined)))
    prod_hit = bool(C.PROD_RX.search(narrative))

    evidence = _clip01(evidence_hits / 3.0) * (1.0 if prod_hit else 0.75)
    musthave = _clip01(musthave_hits / 3.0)

    # --- experience: JD ideal 6-8, band 5-9 ---
    yoe = p.get("years_of_experience", 0) or 0
    if 6 <= yoe <= 8:
        exp = 1.0
    elif 5 <= yoe <= 9:
        exp = 0.85
    elif 3 <= yoe < 5 or 9 < yoe <= 11:
        exp = 0.6
    elif yoe < 3:
        exp = 0.3
    else:
        exp = 0.45  # very senior; JD "hasn't coded in 18 months" risk

    # --- product vs services ---
    companies = [(j.get("company", "") or "").lower() for j in ch]
    consulting_only = bool(companies) and all(
        any(c in comp for c in C.CONSULTING) for comp in companies
    )
    any_consulting = any(any(c in comp for c in C.CONSULTING) for comp in companies)
    product = 0.2 if any_consulting else 1.0
    if consulting_only:
        product = 0.0

    # --- location ---
    country = (p.get("country", "") or "").lower()
    loc = (p.get("location", "") or "").lower()
    relocate = bool(sig.get("willing_to_relocate"))
    in_india = country == "india"
    pref_city = any(city in loc for city in C.PREF_CITIES)
    if in_india and pref_city:
        location = 1.0
    elif in_india:
        location = 0.7
    elif relocate:
        location = 0.5
    else:
        location = 0.1

    # --- behavioral availability (multiplier) ---
    rr = sig.get("recruiter_response_rate", 0) or 0
    la = _date(sig.get("last_active_date"))
    days_inactive = (ref_date - la).days if la else 365
    recency = 1.0 if days_inactive <= 14 else 0.7 if days_inactive <= 45 else \
        0.4 if days_inactive <= 120 else 0.15
    open_flag = 1.0 if sig.get("open_to_work_flag") else 0.6
    interview = sig.get("interview_completion_rate", 0.5) or 0.5
    saved = min((sig.get("saved_by_recruiters_30d", 0) or 0) / 40.0, 1.0)
    verified = (1.0 if sig.get("verified_email") else 0.0) + \
               (1.0 if sig.get("verified_phone") else 0.0)
    avail_raw = (0.35 * rr + 0.25 * recency + 0.15 * open_flag +
                 0.10 * interview + 0.10 * saved + 0.05 * (verified / 2.0))
    availability = C.AVAIL_MIN + (C.AVAIL_MAX - C.AVAIL_MIN) * _clip01(avail_raw)

    # --- hard negatives ---
    research_only = bool(C.RESEARCH_RX.search(narrative)) and not prod_hit and evidence_hits == 0
    other_domain_only = bool(C.OTHER_DOMAIN_RX.search(narrative)) and not C.NLP_IR_RX.search(combined)
    framework = bool(C.FRAMEWORK_RX.search(narrative)) and musthave_hits == 0
    notice = sig.get("notice_period_days", 0) or 0

    # --- integrity gate ---
    hp_flags = integrity.honeypot_flags(cand)
    stuffer = integrity.is_keyword_stuffer(cand, narrative, evidence_hits)

    # top relevant skill for reasoning (prefer an AI-core / must-have skill)
    skills = cand.get("skills", []) or []
    top_skill = None
    for s in sorted(skills, key=lambda s: -(s.get("endorsements", 0) or 0)):
        if C.MUSTHAVE_RX.search(s.get("name", "")) or C.EVIDENCE_RX.search(s.get("name", "")):
            top_skill = s.get("name")
            break
    if not top_skill and skills:
        top_skill = max(skills, key=lambda s: s.get("endorsements", 0) or 0).get("name")

    return {
        "candidate_id": cand.get("candidate_id"),
        "current_title": p.get("current_title", ""),
        "years": round(yoe, 1),
        "location": p.get("location", ""),
        "country": p.get("country", ""),
        "top_skill": top_skill,
        "evidence_phrase": _first_evidence(narrative),
        # scoring components
        "role": role, "evidence": evidence, "musthave": musthave, "exp": exp,
        "product": product, "location_s": location, "availability": availability,
        "nice_hits": nice_hits, "musthave_hits": musthave_hits,
        "evidence_hits": evidence_hits, "prod_hit": prod_hit,
        "response_rate": round(rr, 2), "days_inactive": days_inactive,
        "open_to_work": bool(sig.get("open_to_work_flag")), "notice": notice,
        "relocate": relocate,
        # negatives / flags
        "consulting_only": consulting_only, "any_consulting": any_consulting,
        "research_only": research_only, "other_domain_only": other_domain_only,
        "framework": framework, "stuffer": stuffer,
        "honeypot": bool(hp_flags), "honeypot_flags": hp_flags[:3],
    }


def _first_evidence(blob: str):
    m = C.EVIDENCE_RX.search(blob)
    return m.group(0).lower() if m else None


# --- numeric feature vector (for the LightGBM ranker) -----------------------
FEATURE_NAMES = [
    "role", "evidence", "musthave", "exp", "product", "location_s", "availability",
    "rule_score", "evidence_hits", "musthave_hits", "nice_hits", "prod_hit",
    "response_rate", "days_inactive_n", "notice_n", "open_to_work", "relocate",
    "any_consulting", "consulting_only", "research_only", "other_domain_only",
    "framework", "years", "in_india",
]


def vector(rec: dict) -> list[float]:
    """Turn a feature record into a fixed numeric vector for the learned ranker."""
    return [
        rec["role"], rec["evidence"], rec["musthave"], rec["exp"], rec["product"],
        rec["location_s"], rec["availability"], rec.get("rule_score", 0.0),
        float(rec["evidence_hits"]), float(rec["musthave_hits"]), float(rec["nice_hits"]),
        float(rec["prod_hit"]), rec["response_rate"], min(rec["days_inactive"], 365) / 365.0,
        min(rec["notice"], 180) / 180.0, float(rec["open_to_work"]), float(rec["relocate"]),
        float(rec["any_consulting"]), float(rec["consulting_only"]), float(rec["research_only"]),
        float(rec["other_domain_only"]), float(rec["framework"]), rec["years"],
        float((rec["country"] or "").lower() == "india"),
    ]
