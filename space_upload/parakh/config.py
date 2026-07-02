"""
Parakh — configuration: JD-derived knowledge, vocabularies, scoring weights.

Everything the ranker "knows" about the target role lives here, so the logic in
features.py / score.py stays readable and every decision is auditable.

Source of truth for these lists: the released job_description.md (Senior AI
Engineer @ Redrob) + the 100k-pool audit. See README for the reasoning.
"""

import re

# --- paths (overridable via rank.py CLI) ------------------------------------
DEFAULT_CANDIDATES = (
    "../dataset/[PUB] India_runs_data_and_ai_challenge/"
    "India_runs_data_and_ai_challenge/candidates.jsonl"
)

# --- role / title vocabulary -------------------------------------------------
# Titles that indicate a genuine ML/AI/IR/search practitioner (current or past).
ML_TITLE_RX = re.compile(
    r"(machine learning|\bml\b|ai engineer|applied scientist|data scientist|"
    r"\bnlp\b|deep learning|mlops|research engineer|search engineer|"
    r"recommendation|ranking|relevance|information retrieval|ai research)",
    re.I,
)

# Non-technical titles that dominate the pool as distractors (audit: ~68k).
NONTECH_TITLES = {
    "Business Analyst", "HR Manager", "Mechanical Engineer", "Accountant",
    "Project Manager", "Customer Support", "Operations Manager", "Content Writer",
    "Sales Executive", "Civil Engineer", "Graphic Designer", "Marketing Manager",
}

# --- free-text evidence of actually building the systems the JD wants --------
# "A Tier-5 candidate may not say 'RAG' but if their history shows they built a
#  recommendation system at a product company, they're a fit." (JD, verbatim.)
EVIDENCE_RX = re.compile(
    r"(recommendation|recommender|\brecsys\b|learning[- ]to[- ]rank|"
    r"\branking\b|retrieval|semantic search|vector (?:search|database|db|store)|"
    r"embedding|personali[sz]ation|information retrieval|search relevance|"
    r"search engine|matching system|\bre[- ]?rank)",
    re.I,
)

# JD "things you absolutely need" — production embeddings/retrieval, vector DBs,
# and rigorous ranking evaluation.
MUSTHAVE_RX = re.compile(
    r"(embeddings?|sentence[- ]transformers?|\bbge\b|\be5\b|dense retrieval|\brag\b|"
    r"pinecone|weaviate|qdrant|milvus|opensearch|elasticsearch|\bfaiss\b|"
    r"vector (?:database|db|search)|hybrid search|\bbm25\b|"
    r"\bndcg\b|\bmrr\b|\bmap\b|precision@|recall@|a/b test|offline eval|"
    r"ranking metrics|learning to rank|two[- ]tower)",
    re.I,
)

# JD "nice to have but won't reject you for".
NICE_RX = re.compile(
    r"(lora|qlora|peft|fine[- ]tun|xgboost|learning to rank|"
    r"hr[- ]?tech|recruit|marketplace|distributed systems|inference optimi[sz]ation|"
    r"open[- ]source)",
    re.I,
)

# Production / scale signals — JD wants "shipped to real users at meaningful scale".
PROD_RX = re.compile(
    r"(production|deployed|in production|real users|at scale|latency|throughput|"
    r"\bA/B\b|experiment|serving|millions of|high[- ]traffic)",
    re.I,
)

# --- JD hard-negatives -------------------------------------------------------
# Career entirely at IT-services/consulting shops → explicit JD reject.
CONSULTING = {
    "tcs", "tata consultancy", "infosys", "wipro", "accenture", "cognizant",
    "capgemini", "tech mahindra", "hcl", "mindtree", "ltimindtree", "mphasis",
    "igate", "larsen", "dxc", "genpact",
}

# Pure research / academia without production → JD reject.
RESEARCH_RX = re.compile(
    r"(research scientist|\bphd\b|postdoc|academ|university|publications?|"
    r"research lab|paper|thesis|professor)",
    re.I,
)

# CV / speech / robotics primary, without NLP/IR → JD reject.
OTHER_DOMAIN_RX = re.compile(
    r"(computer vision|image classification|object detection|opencv|"
    r"robotics|\bros2?\b|\bslam\b|speech recognition|\basr\b|text[- ]to[- ]speech|\btts\b)",
    re.I,
)
NLP_IR_RX = re.compile(
    r"(\bnlp\b|natural language|retrieval|search|ranking|recommendation|"
    r"embedding|information retrieval|text)",
    re.I,
)

# Framework-tutorial enthusiast (JD: "GitHub full of LangChain tutorials").
FRAMEWORK_RX = re.compile(r"(langchain tutorial|demo app|hello world|toy project)", re.I)

# --- location ----------------------------------------------------------------
# JD: Pune/Noida preferred; Hyderabad, Mumbai, Delhi NCR welcome. Bengaluru is a
# major product hub and reasonable for relocation.
PREF_CITIES = {
    "noida", "pune", "hyderabad", "mumbai", "delhi", "new delhi", "gurgaon",
    "gurugram", "ncr", "bengaluru", "bangalore", "gurgaon/ncr",
}

# --- scoring weights (positives sum to ~1.0 before modifiers) ----------------
W_ROLE = 0.26      # is this person actually in an ML/AI/IR role?
W_EVIDENCE = 0.24  # do they describe building the right systems?
W_MUSTHAVE = 0.18  # embeddings / vector DB / eval-framework evidence
W_EXPERIENCE = 0.10
W_PRODUCT = 0.08   # product company vs services
W_LOCATION = 0.14

# behavioral availability multiplier bounds
AVAIL_MIN, AVAIL_MAX = 0.55, 1.12

# hard-negative multipliers (stack multiplicatively)
MULT_CONSULTING_ONLY = 0.55
MULT_RESEARCH_ONLY = 0.50
MULT_ABROAD_NO_RELOCATE = 0.40
MULT_OTHER_DOMAIN_ONLY = 0.45
MULT_STUFFER = 0.25
MULT_FRAMEWORK = 0.85
MULT_NOTICE_LONG = 0.80   # > 90 days
MULT_NOTICE_MED = 0.93    # > 30 days

HONEYPOT_SCORE = 1e-6     # forced to the bottom; never reaches top-100
