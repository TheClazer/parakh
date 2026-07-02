"""
Parakh — baseline scoring + grounded reasoning.

Transparent weighted rubric derived straight from the JD. Every candidate's
score is explainable, which also lets us generate honest, specific reasoning
(no hallucination) for the submission's reasoning column.
"""

from __future__ import annotations
from . import config as C


def score(rec: dict) -> float:
    if rec["honeypot"]:
        return C.HONEYPOT_SCORE

    base = (
        C.W_ROLE * rec["role"]
        + C.W_EVIDENCE * rec["evidence"]
        + C.W_MUSTHAVE * rec["musthave"]
        + C.W_EXPERIENCE * rec["exp"]
        + C.W_PRODUCT * rec["product"]
        + C.W_LOCATION * rec["location_s"]
    )
    # small bonus for JD "nice to haves"
    base += 0.03 * min(rec["nice_hits"], 3) / 3.0

    s = base * rec["availability"]

    if rec["stuffer"]:
        s *= C.MULT_STUFFER
    if rec["consulting_only"]:
        s *= C.MULT_CONSULTING_ONLY
    if rec["research_only"]:
        s *= C.MULT_RESEARCH_ONLY
    if rec["other_domain_only"]:
        s *= C.MULT_OTHER_DOMAIN_ONLY
    if rec["framework"]:
        s *= C.MULT_FRAMEWORK
    if not rec["relocate"] and rec["country"].lower() != "india":
        s *= C.MULT_ABROAD_NO_RELOCATE
    if rec["notice"] > 90:
        s *= C.MULT_NOTICE_LONG
    elif rec["notice"] > 30:
        s *= C.MULT_NOTICE_MED

    return max(min(s, 1.0), C.HONEYPOT_SCORE)


# ---------------------------------------------------------------------------
# Reasoning: specific facts + JD connection + honest concern, varied by what
# actually drives each candidate's score. Only cites fields present in the rec.
# ---------------------------------------------------------------------------

def _strength_clause(rec: dict) -> str:
    yrs = rec["years"]
    title = rec["current_title"] or "candidate"
    if rec["role"] >= 1.0 and rec["evidence_hits"] > 0:
        ev = rec["evidence_phrase"] or "retrieval/ranking work"
        return f"{title} with {yrs} yrs; profile shows hands-on {ev}"
    if rec["role"] >= 1.0:
        return f"{title} with {yrs} yrs in an ML/AI role"
    if rec["evidence_hits"] > 0:
        ev = rec["evidence_phrase"] or "relevant systems"
        return (f"{title} ({yrs} yrs) — non-ML title but describes building {ev}, "
                f"a plain-language fit the JD explicitly wants")
    return f"{title} with {yrs} yrs; adjacent skills only"


def _signal_clause(rec: dict) -> str:
    bits = []
    if rec["musthave_hits"] > 0:
        bits.append("has embeddings/retrieval/eval evidence")
    if rec["top_skill"]:
        bits.append(f"key skill {rec['top_skill']}")
    if rec["response_rate"] >= 0.5:
        bits.append(f"responsive (recruiter response {rec['response_rate']})")
    if rec["open_to_work"]:
        bits.append("open to work")
    return "; ".join(bits)


def _concern_clause(rec: dict) -> str:
    concerns = []
    if rec["consulting_only"]:
        concerns.append("services-only background (JD flags this)")
    elif rec["any_consulting"]:
        concerns.append("some services-firm history")
    if rec["country"].lower() != "india":
        concerns.append("based abroad" + (", open to relocate" if rec["relocate"] else ", relocation unclear"))
    if rec["notice"] > 30:
        concerns.append(f"{rec['notice']}-day notice")
    if rec["days_inactive"] > 120:
        concerns.append(f"inactive ~{rec['days_inactive']}d")
    if rec["response_rate"] < 0.2:
        concerns.append(f"low recruiter response ({rec['response_rate']})")
    if rec["evidence_hits"] == 0 and rec["role"] < 1.0:
        concerns.append("thin direct evidence of ranking/retrieval work")
    return "; ".join(concerns[:2])


def reason(rec: dict) -> str:
    strength = _strength_clause(rec)
    signal = _signal_clause(rec)
    concern = _concern_clause(rec)
    out = strength
    if signal:
        out += f". {signal[0].upper()}{signal[1:]}"
    if concern:
        out += f". Concern: {concern}"
    return (out + ".").replace("..", ".")
