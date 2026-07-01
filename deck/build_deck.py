#!/usr/bin/env python3
"""Builds parakh_deck.pptx — Parakh approach deck for India Runs Track 1.

Design language: an assayer's hallmark. Deep-ink title/close slides, light
content slides, brass as the single sharp accent, teal = genuine, clay = fake.
Motif: a small brass "hallmark punch" ring, repeated as section markers.
"""
from pptx import Presentation
from pptx.util import Inches, Pt
from pptx.dml.color import RGBColor
from pptx.enum.text import PP_ALIGN, MSO_ANCHOR
from pptx.enum.shapes import MSO_SHAPE

# ---- palette ---------------------------------------------------------------
INK      = RGBColor(0x1B, 0x2A, 0x41)
INK_SOFT = RGBColor(0x33, 0x45, 0x5F)
PAPER    = RGBColor(0xFF, 0xFF, 0xFF)
BRASS    = RGBColor(0xB0, 0x89, 0x4A)
BRASS_D  = RGBColor(0x8A, 0x69, 0x33)
TEAL     = RGBColor(0x0E, 0x7C, 0x66)
CLAY     = RGBColor(0xB4, 0x47, 0x2E)
SLATE    = RGBColor(0x5A, 0x64, 0x72)
PANEL    = RGBColor(0xF4, 0xF5, 0xF7)
TEAL_LT  = RGBColor(0xE4, 0xF0, 0xEB)
CLAY_LT  = RGBColor(0xF7, 0xE9, 0xE3)
BRASS_LT = RGBColor(0xF3, 0xEC, 0xDC)
MIST     = RGBColor(0xCF, 0xD6, 0xDE)

HEAD = "Cambria"      # safe serif, editorial personality
BODY = "Calibri"      # safe sans
MONO = "Consolas"

prs = Presentation()
prs.slide_width = Inches(13.333)
prs.slide_height = Inches(7.5)
BLANK = prs.slide_layouts[6]
SW, SH = 13.333, 7.5


def slide(bg=PAPER):
    s = prs.slides.add_slide(BLANK)
    r = s.shapes.add_shape(MSO_SHAPE.RECTANGLE, 0, 0, prs.slide_width, prs.slide_height)
    r.fill.solid(); r.fill.fore_color.rgb = bg
    r.line.fill.background(); r.shadow.inherit = False
    return s


def shape(s, kind, x, y, w, h, fill=None, line=None, lw=1.0, radius=None):
    shp = s.shapes.add_shape(kind, Inches(x), Inches(y), Inches(w), Inches(h))
    if fill is None:
        shp.fill.background()
    else:
        shp.fill.solid(); shp.fill.fore_color.rgb = fill
    if line is None:
        shp.line.fill.background()
    else:
        shp.line.color.rgb = line; shp.line.width = Pt(lw)
    shp.shadow.inherit = False
    if radius is not None and kind == MSO_SHAPE.ROUNDED_RECTANGLE:
        try: shp.adjustments[0] = radius
        except Exception: pass
    return shp


def card(s, x, y, w, h, fill=PANEL, radius=0.06):
    return shape(s, MSO_SHAPE.ROUNDED_RECTANGLE, x, y, w, h, fill=fill, radius=radius)


def text(s, x, y, w, h, paras, anchor=MSO_ANCHOR.TOP):
    tb = s.shapes.add_textbox(Inches(x), Inches(y), Inches(w), Inches(h))
    tf = tb.text_frame; tf.word_wrap = True
    tf.margin_left = 0; tf.margin_right = 0; tf.margin_top = 0; tf.margin_bottom = 0
    tf.vertical_anchor = anchor
    for i, para in enumerate(paras):
        p = tf.paragraphs[0] if i == 0 else tf.add_paragraph()
        p.alignment = para.get("align", PP_ALIGN.LEFT)
        if "before" in para: p.space_before = Pt(para["before"])
        p.space_after = Pt(para.get("after", 0))
        if "line" in para: p.line_spacing = para["line"]
        for run in para["runs"]:
            r = p.add_run(); r.text = run[0]
            f = r.font
            f.size = Pt(run[1]); f.color.rgb = run[2]
            f.bold = run[3] if len(run) > 3 else False
            f.italic = run[4] if len(run) > 4 else False
            f.name = run[5] if len(run) > 5 else BODY
    return tb


def hallmark(s, cx, cy, d=0.30, color=BRASS):
    ring = s.shapes.add_shape(MSO_SHAPE.OVAL, Inches(cx - d / 2), Inches(cy - d / 2), Inches(d), Inches(d))
    ring.fill.background(); ring.line.color.rgb = color; ring.line.width = Pt(1.5)
    ring.shadow.inherit = False
    dd = d * 0.34
    dot = s.shapes.add_shape(MSO_SHAPE.OVAL, Inches(cx - dd / 2), Inches(cy - dd / 2), Inches(dd), Inches(dd))
    dot.fill.solid(); dot.fill.fore_color.rgb = color; dot.line.fill.background()
    dot.shadow.inherit = False


def kicker(s, x, y, label, color=BRASS):
    hallmark(s, x + 0.13, y + 0.12, 0.26, color)
    text(s, x + 0.42, y - 0.03, 6.0, 0.4,
         [{"runs": [(label.upper(), 13, color, True)]}])


# ============================================================ SLIDE 1 — title
s = slide(INK)
# faint hallmark constellation, right side
for (cx, cy, d) in [(11.7, 1.5, 2.9), (12.7, 4.6, 1.7), (10.9, 5.9, 1.1)]:
    ring = s.shapes.add_shape(MSO_SHAPE.OVAL, Inches(cx - d/2), Inches(cy - d/2), Inches(d), Inches(d))
    ring.fill.background(); ring.line.color.rgb = INK_SOFT; ring.line.width = Pt(1.5)
    ring.shadow.inherit = False
hallmark(s, 0.95, 1.35, 0.4, BRASS)
text(s, 1.35, 1.15, 6, 0.5, [{"runs": [("THE DATA & AI CHALLENGE  ·  REDROB × INDIA RUNS", 13, MIST, True)]}])
text(s, 0.9, 2.15, 9.5, 1.5, [{"runs": [("Parakh", 78, PAPER, True, False, HEAD)]}])
text(s, 0.95, 3.55, 9.2, 0.6,
     [{"runs": [("/ pə-rəkh /  —  to assay; to test whether gold is genuine.", 20, BRASS, False, True, HEAD)]}])
text(s, 0.95, 4.5, 8.7, 1.0,
     [{"runs": [("A candidate ranker that ", 22, MIST), ("verifies", 22, PAPER, True, True),
                (" each profile before it trusts it —", 22, MIST)]},
      {"runs": [("telling genuine engineers from convincing fakes.", 22, MIST)]}])
line = s.shapes.add_shape(MSO_SHAPE.RECTANGLE, Inches(0.95), Inches(6.15), Inches(3.2), Inches(0.02))
line.fill.solid(); line.fill.fore_color.rgb = BRASS; line.line.fill.background(); line.shadow.inherit = False
text(s, 0.95, 6.4, 9, 0.6,
     [{"runs": [("Rayyan Ahmed Shaikh", 15, PAPER, True), ("     ·     Team Parakh", 15, MIST)]}])

# ============================================================ SLIDE 2 — problem
s = slide(PAPER)
kicker(s, 0.7, 0.6, "The problem")
text(s, 0.7, 1.05, 7.4, 1.4,
     [{"runs": [("Great candidates are missed —", 34, INK, True, False, HEAD)]},
      {"runs": [("not absent, just unseen.", 34, INK, True, False, HEAD)]}])
text(s, 0.7, 2.9, 6.7, 2.6,
     [{"line": 1.15, "after": 10, "runs": [("Recruiters scan hundreds of profiles and still miss the right person — because ", 16, SLATE), ("keyword filters can't see fit.", 16, INK, True)]},
      {"line": 1.15, "after": 10, "runs": [("They reward whoever lists the most buzzwords, and overlook the engineer who ", 16, SLATE), ("built the exact system", 16, INK, True), (" but described it in plain words.", 16, SLATE)]},
      {"line": 1.15, "runs": [("In a pool of 100,000, the real fits are a needle in a haystack — and half the score rides on the top ten.", 16, SLATE)]}])
# stat stack (right)
sx = 8.15
for (i, (num, lab, col)) in enumerate([("100,000", "profiles in the pool", INK),
                                       ("~few hundred", "genuinely fit the role", BRASS_D),
                                       ("Top 10", "carry 50% of the score", TEAL)]):
    yy = 1.15 + i * 1.72
    card(s, sx, yy, 4.45, 1.5, PANEL)
    text(s, sx + 0.35, yy + 0.2, 3.9, 0.85, [{"runs": [(num, 40, col, True, False, HEAD)]}], anchor=MSO_ANCHOR.MIDDLE)
    text(s, sx + 0.37, yy + 1.0, 3.9, 0.4, [{"runs": [(lab, 14, SLATE)]}])

# ============================================================ SLIDE 3 — traps
s = slide(PAPER)
kicker(s, 0.7, 0.6, "Why naïve matching loses")
text(s, 0.7, 1.05, 11.9, 0.9, [{"runs": [("The dataset is engineered to punish keyword search", 33, INK, True, False, HEAD)]}])
traps = [
    ("Keyword stuffers", CLAY, CLAY_LT,
     "Lists every AI skill; the actual job is Marketing or Ops. Counting keywords ranks the fake at the top."),
    ("Plain-language gems", TEAL, TEAL_LT,
     "7,334 people describe real retrieval / ranking work under a non-ML title. Title filters miss them entirely."),
    ("Behavioural twins", BRASS_D, BRASS_LT,
     "Near-identical on paper; they differ only in engagement signals — who actually responds and shows up."),
    ("Honeypots (~80)", CLAY, CLAY_LT,
     "Impossible profiles (expert skills, 0 months' use). Rank >10% of them in the top 100 and you're disqualified."),
]
gx, gy, gw, gh, gap = 0.7, 2.1, 5.83, 2.15, 0.24
for i, (title, ac, tint, desc) in enumerate(traps):
    x = gx + (i % 2) * (gw + gap); y = gy + (i // 2) * (gh + 0.24)
    card(s, x, y, gw, gh, tint)
    hallmark(s, x + 0.5, y + 0.55, 0.34, ac)
    text(s, x + 0.95, y + 0.32, gw - 1.2, 0.5, [{"runs": [(title, 20, INK, True, False, HEAD)]}])
    text(s, x + 0.5, y + 1.05, gw - 0.9, 1.0, [{"line": 1.12, "runs": [(desc, 14.5, SLATE)]}])

# ============================================================ SLIDE 4 — thesis + pipeline
s = slide(PAPER)
kicker(s, 0.7, 0.6, "The approach")
text(s, 0.7, 1.05, 11.9, 0.9, [{"runs": [("Assay, don't match.", 34, INK, True, False, HEAD)]}])
text(s, 0.7, 1.95, 11.9, 0.5, [{"runs": [("Do all the heavy AI thinking offline; bake it into artifacts a fast, offline ranker reads.", 16, SLATE)]}])
# two lanes
def lane(y, label, sub, color, boxes):
    card(s, 0.7, y, 11.93, 1.72, PANEL)
    text(s, 1.0, y + 0.22, 3.0, 1.3, [{"runs": [(label, 16, color, True, False, HEAD)]},
                                      {"before": 4, "line": 1.05, "runs": [(sub, 11.5, SLATE)]}], anchor=MSO_ANCHOR.MIDDLE)
    bx = 4.05; bw = 2.5; bgap = 0.28
    for i, b in enumerate(boxes):
        x = bx + i * (bw + bgap)
        shape(s, MSO_SHAPE.ROUNDED_RECTANGLE, x, y + 0.42, bw, 0.88, fill=PAPER, line=color, lw=1.25, radius=0.12)
        text(s, x + 0.14, y + 0.42, bw - 0.28, 0.88, [{"align": PP_ALIGN.CENTER, "line": 1.0, "runs": [(b, 13, INK, True)]}], anchor=MSO_ANCHOR.MIDDLE)
        if i < len(boxes) - 1:
            text(s, x + bw - 0.02, y + 0.42, bgap + 0.04, 0.88, [{"align": PP_ALIGN.CENTER, "runs": [("→", 18, color, True)]}], anchor=MSO_ANCHOR.MIDDLE)
lane(2.55, "Pre-compute", "offline · LLM + GPU allowed", BRASS_D,
     ["Embed + features", "Qwen-235B teacher\ngrades fit 0–5", "DeepSeek\n2nd judge"])
lane(4.5, "Ranking step", "offline · CPU · no network · < 5 min", TEAL,
     ["Integrity Gate", "Score all\n100,000", "Top 100\n+ reasons"])
text(s, 0.7, 6.45, 11.93, 0.7,
     [{"runs": [("Spec §3 compliance:  ", 14, INK, True),
                ("no LLM, GPU or network during ranking — every model call lives in pre-compute and ships as a cached artifact.", 14, SLATE)]}])

# ============================================================ SLIDE 5 — integrity gate
s = slide(PAPER)
kicker(s, 0.7, 0.6, "Layer 1 — the Integrity Gate")
text(s, 0.7, 1.05, 11.9, 0.9, [{"runs": [("Reject the impossible and the fake — first", 32, INK, True, False, HEAD)]}])
det = [("Honeypot check", "‘Expert’ in a skill used 0 months · tenure longer than the whole career · contradictory dates. ~84 hits ≈ the ~80 planted honeypots."),
       ("Stuffer check", "Many AI skills, but the career narrative shows none of the work, and the title is wrong. Keywords without evidence don't count.")]
for i, (t, d) in enumerate(det):
    y = 2.15 + i * 1.5
    card(s, 0.7, y, 7.4, 1.32, PANEL)
    hallmark(s, 1.15, y + 0.66, 0.34, CLAY)
    text(s, 1.6, y + 0.24, 6.3, 0.5, [{"runs": [(t, 19, INK, True, False, HEAD)]}])
    text(s, 1.6, y + 0.72, 6.35, 0.55, [{"line": 1.08, "runs": [(d, 13.5, SLATE)]}])
# right: verdict block
card(s, 8.35, 2.15, 4.28, 2.82, INK)
text(s, 8.7, 2.45, 3.6, 0.5, [{"runs": [("VERDICT AT RUNTIME", 12, MIST, True)]}])
text(s, 8.7, 2.95, 3.6, 1.0, [{"runs": [("Flagged profiles are forced to the bottom — they can never reach the top 100.", 15, PAPER)]}])
text(s, 8.7, 3.72, 3.6, 1.1, [{"runs": [("0", 44, BRASS, True, False, HEAD)]},
                              {"before": 2, "runs": [("honeypots in our top 100", 13.5, MIST)]}])

# ============================================================ SLIDE 6 — teacher
s = slide(PAPER)
kicker(s, 0.7, 0.6, "Layer 2 — the distilled teacher")
text(s, 0.7, 1.05, 11.9, 0.9, [{"runs": [("A senior recruiter's judgment — that runs offline", 31, INK, True, False, HEAD)]}])
steps = [("Grade offline", "Qwen3-235B scores the 3,000 most plausible candidates on the JD rubric — fit tier 0–5 with a written reason.", BRASS_D),
         ("Bake in", "Those labels are saved as a cached artifact in the repo — a precomputed feature, not a live call.", INK_SOFT),
         ("Read at runtime", "The offline ranker reads the labels; no LLM, GPU or network is touched while ranking.", TEAL)]
for i, (t, d, c) in enumerate(steps):
    x = 0.7 + i * 4.05
    card(s, x, 2.2, 3.78, 2.9, PANEL)
    text(s, x + 0.35, 2.5, 1.0, 0.7, [{"runs": [(f"0{i+1}", 30, c, True, False, HEAD)]}])
    text(s, x + 0.35, 3.25, 3.1, 0.5, [{"runs": [(t, 18, INK, True, False, HEAD)]}])
    text(s, x + 0.35, 3.8, 3.15, 1.1, [{"line": 1.14, "runs": [(d, 14, SLATE)]}])
text(s, 0.7, 5.5, 11.9, 0.7,
     [{"runs": [("Why it matters:  ", 14, INK, True),
                ("an LLM call per candidate can't scale or meet the 5-minute CPU budget. Distillation keeps the intelligence, drops the cost.", 14, SLATE)]}])

# ============================================================ SLIDE 7 — quorum
s = slide(PAPER)
kicker(s, 0.7, 0.6, "Layer 3 — agreement, not one opinion")
text(s, 0.7, 1.05, 11.9, 0.9, [{"runs": [("Two independent judges — the top is where they agree", 30, INK, True, False, HEAD)]}])
# two judge cards -> merge
card(s, 0.7, 2.35, 3.5, 1.5, BRASS_LT)
text(s, 1.0, 2.6, 2.9, 1.0, [{"runs": [("Qwen-235B", 18, INK, True, False, HEAD)]}, {"before": 3, "runs": [("primary teacher", 13, SLATE)]}])
card(s, 0.7, 4.05, 3.5, 1.5, TEAL_LT)
text(s, 1.0, 4.3, 2.9, 1.0, [{"runs": [("DeepSeek-V4", 18, INK, True, False, HEAD)]}, {"before": 3, "runs": [("second judge (harsher)", 13, SLATE)]}])
text(s, 4.35, 2.9, 0.9, 2.0, [{"align": PP_ALIGN.CENTER, "runs": [("→", 30, BRASS, True)]},
                              {"align": PP_ALIGN.CENTER, "before": 30, "runs": [("→", 30, BRASS, True)]}], anchor=MSO_ANCHOR.MIDDLE)
card(s, 5.35, 2.9, 3.3, 2.05, INK)
text(s, 5.65, 3.2, 2.7, 1.6, [{"runs": [("Average the tiers", 17, PAPER, True, False, HEAD)]},
                              {"before": 8, "line": 1.12, "runs": [("Only candidates ", 13.5, MIST), ("both", 13.5, BRASS, True), (" rate tier-5 rise to the very top.", 13.5, MIST)]}], anchor=MSO_ANCHOR.MIDDLE)
card(s, 9.0, 2.9, 3.63, 2.05, PANEL)
text(s, 9.3, 3.15, 3.1, 1.7,
     [{"runs": [("The check that pays off", 14, INK, True, False, HEAD)]},
      {"before": 6, "line": 1.12, "runs": [("DeepSeek rated only ", 13, SLATE), ("40 of our 100", 13, INK, True), (" as tier-5. Requiring agreement filters out one model's overconfidence.", 13, SLATE)]}], anchor=MSO_ANCHOR.MIDDLE)
text(s, 0.7, 5.85, 11.9, 0.5, [{"runs": [("An echo of my ", 13.5, SLATE), ("Quorum", 13.5, INK, True, True), (" project: five models debating — trust rises where independent judges converge.", 13.5, SLATE)]}])

# ============================================================ SLIDE 8 — behavioral + rules
s = slide(PAPER)
kicker(s, 0.7, 0.6, "Layer 4 — availability & red flags")
text(s, 0.7, 1.05, 11.9, 0.9, [{"runs": [("Beyond the résumé", 33, INK, True, False, HEAD)]}])
card(s, 0.7, 2.15, 5.83, 3.2, TEAL_LT)
text(s, 1.05, 2.45, 5.2, 0.5, [{"runs": [("Availability signals", 20, INK, True, False, HEAD)]}])
for i, t in enumerate(["Recruiter response rate — will they reply?",
                       "Last active — a 6-month ghost isn't hireable",
                       "Open-to-work + notice period",
                       "Interview completion, saved-by-recruiters"]):
    text(s, 1.35, 3.05 + i * 0.53, 5.0, 0.5, [{"runs": [("·  ", 15, TEAL, True), (t, 14, INK_SOFT)]}])
card(s, 6.8, 2.15, 5.83, 3.2, CLAY_LT)
text(s, 7.15, 2.45, 5.2, 0.5, [{"runs": [("JD hard-negatives", 20, INK, True, False, HEAD)]}])
for i, t in enumerate(["Whole career at IT-services / consulting",
                       "Pure research, no production deployment",
                       "Based abroad and won't relocate",
                       "‘Architect’ who hasn't coded in 18 months"]):
    text(s, 7.45, 3.05 + i * 0.53, 5.0, 0.5, [{"runs": [("·  ", 15, CLAY, True), (t, 14, INK_SOFT)]}])
text(s, 0.7, 5.65, 11.9, 0.5, [{"runs": [("These sharpen precision at the very top, where the score is decided.", 14, SLATE)]}])

# ============================================================ SLIDE 9 — results
s = slide(PAPER)
kicker(s, 0.7, 0.6, "Results")
text(s, 0.7, 1.05, 11.9, 0.9, [{"runs": [("Every layer earned its place", 34, INK, True, False, HEAD)]}])
text(s, 0.7, 1.95, 8.0, 0.5, [{"runs": [("NDCG@10, scored by an independent third model (Llama-3.3-70B)", 14.5, SLATE)]}])
# bar chart
base_y = 5.75; max_h = 3.1
bars = [("Rule-only", 0.64, MIST), ("+ Teacher", 0.88, BRASS), ("+ Ensemble", 1.00, TEAL)]
bx0, bw, bgap = 1.2, 1.8, 1.05
for i, (lab, val, col) in enumerate(bars):
    x = bx0 + i * (bw + bgap)
    h = max_h * val
    shape(s, MSO_SHAPE.ROUNDED_RECTANGLE, x, base_y - h, bw, h, fill=col, radius=0.04)
    text(s, x - 0.2, base_y - h - 0.55, bw + 0.4, 0.5, [{"align": PP_ALIGN.CENTER, "runs": [(f"{val:.2f}", 26, INK, True, False, HEAD)]}])
    text(s, x - 0.2, base_y + 0.1, bw + 0.4, 0.4, [{"align": PP_ALIGN.CENTER, "runs": [(lab, 14, INK_SOFT, True)]}])
base = s.shapes.add_shape(MSO_SHAPE.RECTANGLE, Inches(1.0), Inches(base_y), Inches(8.4), Inches(0.018))
base.fill.solid(); base.fill.fore_color.rgb = SLATE; base.line.fill.background(); base.shadow.inherit = False
# right callouts
card(s, 9.7, 2.35, 2.95, 1.35, INK)
text(s, 9.95, 2.55, 2.5, 1.0, [{"runs": [("10 / 10", 30, BRASS, True, False, HEAD)]}, {"runs": [("top-10 are tier-5 by both judges", 12.5, MIST)]}])
card(s, 9.7, 3.85, 2.95, 1.35, PANEL)
text(s, 9.95, 4.05, 2.5, 1.0, [{"runs": [("0.98", 30, TEAL, True, False, HEAD)]}, {"runs": [("NDCG@50 (ensemble)", 12.5, SLATE)]}])
text(s, 0.7, 6.55, 11.9, 0.6, [{"runs": [("Honest read: ", 12.5, INK, True), ("three different models agree the top-10 is excellent — a strong proxy, not the organisers' hidden ground truth.", 12.5, SLATE, False, True)]}])

# ============================================================ SLIDE 10 — why it holds up
s = slide(PAPER)
kicker(s, 0.7, 0.6, "Why it holds up")
text(s, 0.7, 1.05, 11.9, 0.9, [{"runs": [("Built to survive every stage of judging", 32, INK, True, False, HEAD)]}])
items = [("Reproducible & offline", "The ranking step runs CPU-only, no network, under 5 minutes — it passes Stage-3 reproduction unchanged."),
         ("It reads profiles", "Zero honeypots and zero stuffers in the top 100 — the system understands, it doesn't pattern-match."),
         ("Measured, not guessed", "A three-model eval harness gated every upgrade; nothing shipped without a proven gain."),
         ("Defensible", "Every layer is explainable in plain words — ready to walk through in the finalist interview.")]
for i, (t, d) in enumerate(items):
    x = 0.7 + (i % 2) * 6.0; y = 2.15 + (i // 2) * 1.6
    hallmark(s, x + 0.28, y + 0.28, 0.36, BRASS)
    text(s, x + 0.78, y + 0.02, 5.0, 0.5, [{"runs": [(t, 19, INK, True, False, HEAD)]}])
    text(s, x + 0.78, y + 0.55, 5.05, 0.9, [{"line": 1.12, "runs": [(d, 14, SLATE)]}])

# ============================================================ SLIDE 11 — close
s = slide(INK)
for (cx, cy, d) in [(1.7, 6.0, 2.6), (0.8, 1.4, 1.6)]:
    ring = s.shapes.add_shape(MSO_SHAPE.OVAL, Inches(cx - d/2), Inches(cy - d/2), Inches(d), Inches(d))
    ring.fill.background(); ring.line.color.rgb = INK_SOFT; ring.line.width = Pt(1.5); ring.shadow.inherit = False
hallmark(s, 6.67, 2.35, 0.5, BRASS)
text(s, 0, 2.75, SW, 1.0, [{"align": PP_ALIGN.CENTER, "runs": [("Parakh", 60, PAPER, True, False, HEAD)]}])
text(s, 0, 3.95, SW, 0.6, [{"align": PP_ALIGN.CENTER, "runs": [("Assaying talent — genuine fits, surfaced and trusted.", 19, BRASS, False, True, HEAD)]}])
box = shape(s, MSO_SHAPE.ROUNDED_RECTANGLE, 3.97, 4.95, 5.4, 0.72, fill=INK_SOFT, radius=0.2)
text(s, 3.97, 4.95, 5.4, 0.72, [{"align": PP_ALIGN.CENTER, "runs": [("python rank.py --candidates candidates.jsonl", 14, MIST, False, False, MONO)]}], anchor=MSO_ANCHOR.MIDDLE)
text(s, 0, 6.35, SW, 0.5, [{"align": PP_ALIGN.CENTER, "runs": [("Rayyan Ahmed Shaikh   ·   Team Parakh   ·   India Runs — Data & AI Challenge", 13.5, MIST)]}])

prs.save("parakh_deck.pptx")
print("saved parakh_deck.pptx —", len(prs.slides.__iter__.__self__._sldIdLst), "slides")
