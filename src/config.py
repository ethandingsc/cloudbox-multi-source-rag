"""Central configuration for the Multi-Source RAG system (CloudBox).

Every tunable value lives here — no magic numbers hard-coded elsewhere.
"""
from pathlib import Path

# --- Paths ------------------------------------------------------------------
ROOT_DIR = Path(__file__).resolve().parent.parent

# Secrets live in the project-root .env (gitignored) — loaded once here so
# every module (answer, pipeline, scripts, tests) sees them. A real shell
# environment variable always wins: dotenv never overrides existing vars.
try:
    from dotenv import load_dotenv
    load_dotenv(ROOT_DIR / ".env")
except ImportError:  # python-dotenv missing (pinned in requirements.txt)
    pass

DATA_DIR = ROOT_DIR / "data"
DOCS_DIR = DATA_DIR / "docs"
FORUMS_FILE = DATA_DIR / "forums" / "threads.json"
BLOGS_DIR = DATA_DIR / "blogs"
EVAL_QUERIES_FILE = DATA_DIR / "eval_queries.json"

CHROMA_DIR = ROOT_DIR / "chroma_db"
CHROMA_COLLECTION = "cloudbox"
OUTPUTS_DIR = ROOT_DIR / "outputs"
LOGS_DIR = OUTPUTS_DIR / "logs"
EXAMPLES_DIR = OUTPUTS_DIR / "examples"
EVAL_RESULTS_DIR = OUTPUTS_DIR / "eval_results"

# --- CloudBox product version timeline (fictional) ----------------------------
CURRENT_VERSION = "2.1"
CURRENT_VERSION_RELEASE_DATE = "2024-05-12"

SOURCE_TYPES = ("documentation", "forum", "blog")

# --- Source weighting (used from Step 3; the ONLY place weights live) ---------
SOURCE_WEIGHTS = {"documentation": 1.0, "blog": 0.9, "forum": 0.7}

# --- Retrieval / reranking sizes (used from Step 2) ---------------------------
TOP_K_PER_SOURCE = 5
CANDIDATE_POOL_SIZE = 12
# Step 5.2.5: raised 5 -> 6. Trace evidence: multi-clause questions
# regularly have their relevant chunks ranked 6th by the CrossEncoder, only
# marginally below rank 5 (q05: -4.41 vs -4.16; rank 7 was -5.24), so a
# top-5 cutoff starved the answer of clauses that WERE retrieved. One extra
# chunk is the smallest generic coverage fix; the evaluation metric stays
# "top-5 of the kept evidence" (scripts/evaluate.py slices the first 5).
FINAL_EVIDENCE_SIZE = 6

# --- Models -------------------------------------------------------------------
EMBED_MODEL = "all-MiniLM-L6-v2"                      # sentence-transformers (Step 2)
RERANK_MODEL = "cross-encoder/ms-marco-MiniLM-L-6-v2"  # CrossEncoder (Step 3)

# --- LLM (DeepSeek official API is the default; OpenRouter kept as fallback) --
# Both providers expose an OpenAI-compatible API; one thin client
# (src/answer.py LLMClient), no abstraction. Provider auto-detection:
# DEEPSEEK_API_KEY present -> DeepSeek (default), else OPENROUTER_API_KEY ->
# OpenRouter; an explicit `provider` argument overrides the detection.
# Keys come from the shell environment or the project-root .env (auto-loaded
# at the top of this module; see .env.example). Never hardcoded, never
# committed.
#
# DeepSeek (default provider since 2026-09-27 — replaced the OpenRouter free
# model for the Step 5.1 evaluation re-run).
# Model resolution: DEEPSEEK_MODEL env var > DEEPSEEK_MODEL_DEFAULT. The
# legacy "deepseek-chat" id was retired (2026-07); current official ids are
# deepseek-flash and deepseek-v4-pro. v4-pro is the flagship general chat
# model (the deepseek-chat successor); flash is the lower-cost tier.
DEEPSEEK_BASE_URL = "https://api.deepseek.com"
DEEPSEEK_MODEL_ENV = "DEEPSEEK_MODEL"
DEEPSEEK_API_KEY_ENV = "DEEPSEEK_API_KEY"
DEEPSEEK_MODEL_DEFAULT = "deepseek-v4-pro"
LLM_PROVIDER_DEEPSEEK = "deepseek"
LLM_PROVIDER_OPENROUTER = "openrouter"

# OpenRouter (optional fallback — the original Step 4.1 client, unchanged).
# Model resolution: LLM_MODEL env var > LLM_MODEL_DEFAULT. The default is a
# free model on OpenRouter (the free list rotates — check
# openrouter.ai/models?q=free and override via env when it changes).
# Verified live 2026-09-26: deepseek-v4-flash left the free list (404);
# gemma-4-31b/26b and qwen3.8 were upstream rate-limited (429); nemotron
# answered a grounded-Q&A prompt in ~1s with a correct [1] citation.
OPENROUTER_BASE_URL = "https://openrouter.ai/api/v1"
LLM_MODEL_ENV = "LLM_MODEL"
LLM_API_KEY_ENV = "OPENROUTER_API_KEY"
LLM_MODEL_DEFAULT = "nvidia/nemotron-3-super-120b-a12b:free"
LLM_MAX_TOKENS = 512
LLM_TEMPERATURE = 0.2

# --- Chunking targets (Step 2) -------------------------------------------------
TARGET_TOTAL_CHUNKS = (80, 120)
DOC_SECTION_MAX_WORDS = 800
BLOG_PARAGRAPH_WORDS = 200
