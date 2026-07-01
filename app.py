"""
Parakh — HuggingFace Spaces sandbox.

Upload a small `candidates.jsonl` (<=100 profiles); the ranker runs fully offline
on CPU and returns a ranked CSV. This is the low-stakes reproducibility check the
challenge asks for (Section 10.5). Uses the exact same code path as rank.py.
"""
import csv
import gradio as gr

from rank import load_and_score, rank as rank_top, _load_labels
from parakh import score as scoremod

LABELS = _load_labels("artifacts/teacher_labels.jsonl")
LABELS2 = _load_labels("artifacts/teacher2_labels.jsonl")


def rank_upload(fileobj):
    if fileobj is None:
        return None, [["—", "upload a .jsonl of candidates (≤100)", "", ""]]
    recs = load_and_score(fileobj.name, LABELS, LABELS2)
    top = rank_top(recs)
    out = "parakh_ranked.csv"
    with open(out, "w", encoding="utf-8", newline="") as f:
        w = csv.writer(f)
        w.writerow(["candidate_id", "rank", "score", "reasoning"])
        for i, r in enumerate(top, 1):
            reason = r.get("teacher_reason") or scoremod.reason(r)
            w.writerow([r["candidate_id"], i, f"{r['score']:.6f}", reason])
    preview = [[i, r["candidate_id"], round(r["score"], 4),
                (r.get("teacher_reason") or scoremod.reason(r))[:100]]
               for i, r in enumerate(top[:25], 1)]
    return out, preview


with gr.Blocks(title="Parakh — trap-aware candidate ranker", theme=gr.themes.Soft()) as demo:
    gr.Markdown(
        "# Parakh — trap-aware candidate ranker\n"
        "Assay, don't match. Upload a small `candidates.jsonl` (≤100 profiles); "
        "the ranker runs **fully offline on CPU** and returns a ranked CSV with reasons."
    )
    with gr.Row():
        inp = gr.File(label="candidates.jsonl", file_types=[".jsonl"])
        out_file = gr.File(label="ranked CSV (download)")
    btn = gr.Button("Rank candidates", variant="primary")
    out_tbl = gr.Dataframe(headers=["rank", "candidate_id", "score", "why"],
                           label="Top 25", wrap=True)
    btn.click(rank_upload, inp, [out_file, out_tbl])


if __name__ == "__main__":
    demo.launch()
