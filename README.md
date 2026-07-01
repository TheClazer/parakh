# Parakh — trap-aware candidate ranking

> **Parakh (परख)** — *to assay; to test whether gold is genuine.*
> We don't match keywords. We **assay** each profile — verify it's real and
> consistent — then rank the ones we can trust.

Built for the **Redrob / India Runs — Data & AI Challenge**: rank the top-100
best-fit candidates for a Senior AI Engineer role out of a 100,000-profile pool.

## Why the obvious approach loses

The dataset is engineered to punish "embed the JD + embed candidates + cosine +
sort." A full audit of the 100k pool showed:

- **Skills are a trap.** Real ML people average 3.78 AI-core skills; non-tech
  people 0.62 — but the worst keyword-stuffers carry up to **12**. Counting
  keywords ranks fakes at the top.
- **The signal is in the narrative.** 7,334 people describe retrieval/ranking/
  recommendation work under a *non-ML job title* — the "plain-language gems" the
  JD says to reward. Title/keyword filters miss them.
- **~80 honeypots are detectable by logic:** `expert` proficiency + `0 months`
  used (≈84 hits ≈ the ~80). >10% honeypots in the top-100 is an auto-DQ.

## How Parakh works

1. **Integrity Gate** (`parakh/integrity.py`) — rejects impossible profiles
   (honeypots) and keyword-stuffers (AI skills with **no supporting narrative**).
2. **Transparent rubric** (`parakh/features.py`, `parakh/score.py`) — scores role
   fit, *described* evidence of building retrieval/ranking/recommendation systems,
   must-have signals (embeddings, vector DBs, ranking eval), experience band,
   product-vs-services, and location; then modulates by **behavioral availability**
   (the 23 Redrob signals) and applies the JD's explicit hard-negatives.
3. **Grounded reasoning** — every row cites real facts and honest concerns; no
   hallucinated skills or employers.

> A learned LightGBM ranker distilled from an **offline** LLM teacher (Nebius) is
> layered on top in later stages. The **ranking step below stays CPU-only and
> offline** per `submission_spec` §3 — all LLM/GPU work happens in pre-compute.

## Reproduce

```bash
pip install -r requirements.txt
python rank.py --candidates ./candidates.jsonl --out ./submission.csv --xlsx ./submission.xlsx
```

Runs offline on CPU. Validate the output with the organizer's checker:

```bash
python validate_submission.py submission.csv     # -> "Submission is valid."
```

## Layout

```
rank.py                 # offline ranking step (entry point)
parakh/config.py        # JD-derived vocab + scoring weights (auditable)
parakh/integrity.py     # Integrity Gate: honeypot + stuffer detection
parakh/features.py      # per-candidate feature extraction
parakh/score.py         # rubric scoring + grounded reasoning
precompute.py           # (offline) Nebius embeddings + LLM teacher — added next
submission_metadata.yaml
```

## Compute profile (spec §3)

Ranking step: CPU-only · no network · no GPU · well under the 5 min / 16 GB limit.
Pre-computation (embeddings, LLM teacher labels, any fine-tuning) is a separate
offline job whose artifacts are shipped for the ranking step to load.
