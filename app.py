"""CloudBox Support Assistant — Streamlit demo UI (Step 5.3, PLAN §5.4).

A thin presentation layer over the finished pipeline. It imports and calls
the same functions as main.py — pipeline.answer_question() and
pipeline.trace_text() — so no RAG logic is duplicated here: retrieval,
weighting, reranking, contradiction handling, prompt building, answer
generation and citation mapping all run inside the existing pipeline.

Single page, five blocks: header → source filter → question → answer →
sources, plus a collapsed RAG trace expander.

Run (cloudbox-rag env, project root — or double-click run_demo.bat):
    python -m streamlit run app.py
"""

import streamlit as st

from src import pipeline
from src.answer import OpenRouterError, kept_evidence

# Source filter (radio label -> the pipeline's `sources` argument, which
# accepts None for all three or a list of source_type strings; single-source
# modes skip the cross-source conflict rules inside retrieve_final itself).
SOURCE_OPTIONS = {
    "All Sources": None,
    "Documentation": ["documentation"],
    "Forums": ["forum"],
    "Blogs": ["blog"],
}

SNIPPET_CHARS = 220


@st.cache_resource
def get_store():
    """Embedding model + ChromaDB store — loaded once per Streamlit session."""
    from src.embed_store import EmbedStore
    return EmbedStore()


@st.cache_resource
def get_reranker():
    """CrossEncoder model — loaded once per Streamlit session."""
    from src.rerank import Reranker
    return Reranker()


def run_query(question: str, sources):
    """The whole RAG chain — exactly what main.py calls. The LLM client is
    created inside the pipeline (cheap); the heavy models come from the
    cached resources above."""
    return pipeline.answer_question(question, sources=sources,
                                    store=get_store(), reranker=get_reranker())


def _snippet(text: str) -> str:
    text = (text or "").replace("\n", " ")
    return f"{text[:SNIPPET_CHARS]}{'...' if len(text) > SNIPPET_CHARS else ''}"


def _sources_block(result: dict) -> None:
    st.subheader("Sources")
    citations = result["citations"]
    if not citations:
        st.caption("No sources were cited in this answer.")
        return
    # citations are computed by Step 4.3 against kept_evidence() only, so
    # every entry maps onto a kept chunk — suppressed chunks can never
    # appear here. Same numbering as the [n] markers in the answer.
    by_id = {h["chunk_id"]: h for h in kept_evidence(result["evidence"])}
    for c in citations:
        chunk = by_id[c["chunk_id"]]
        with st.container(border=True):
            st.markdown(f"**[{c['n']}] {c['source_type'].title()}** — "
                        f"{c['title']}")
            st.caption(_snippet(chunk["text"]))


def _trace_block(result: dict) -> None:
    with st.expander("View RAG Trace"):
        st.caption("Multi-Source Retrieval → Source Weighting → "
                   "CrossEncoder Reranking → Contradiction Handling → "
                   "Final Evidence → DeepSeek Answer")
        # Per-chunk stage scores carried by the pipeline result — the same
        # data trace_text() uses; no re-retrieval, no re-computation.
        rows = []
        for h in result["evidence"]:
            status = h["conflict_status"]
            detail = ""
            if status == "suppressed":
                detail = f"suppressed ({h['suppressed_reason']})"
            elif status == "conflict_candidate":
                detail = "conflict candidate (community authority)"
            else:
                detail = "kept"
            rows.append({
                "Chunk": h["chunk_id"],
                "Source": h["source_type"],
                "Raw sim": f"{h['similarity']:.4f}",
                "Weight": f"{h['weight']:.1f}",
                "Weighted": f"{h['weighted_score']:.4f}",
                "Rerank": f"{h['rerank_score']:.4f}",
                "Status": detail,
            })
        st.table(rows)
        st.text(pipeline.trace_text(result))


st.set_page_config(page_title="CloudBox Support Assistant",
                   page_icon=None, layout="centered")
st.markdown("""
<style>
  #MainMenu {visibility: hidden;}
  footer {visibility: hidden;}
  .block-container {padding-top: 2.5rem;}
</style>
""", unsafe_allow_html=True)

st.title("CloudBox Support Assistant")
st.subheader("Multi-Source RAG · Documentation + Forums + Technical Blogs")
st.write("Grounded technical support answers from multiple CloudBox "
         "knowledge sources.")
st.divider()

source_label = st.radio("Knowledge base", list(SOURCE_OPTIONS), index=0,
                        horizontal=True)
question = st.text_input("Ask a CloudBox question",
                         placeholder="What is the maximum file upload size?")

if st.button("Ask", type="primary"):
    if not question.strip():
        st.warning("Please enter a question first.")
    else:
        with st.spinner("Searching CloudBox knowledge..."):
            try:
                result = run_query(question.strip(),
                                   SOURCE_OPTIONS[source_label])
            except OpenRouterError as exc:
                st.session_state.pop("demo_result", None)
                st.session_state["demo_error"] = str(exc)
            except Exception as exc:  # never let the page crash on an error
                st.session_state.pop("demo_result", None)
                st.session_state["demo_error"] = f"Pipeline error: {exc}"
            else:
                st.session_state["demo_result"] = result
                st.session_state.pop("demo_error", None)

if st.session_state.get("demo_error"):
    st.error(st.session_state["demo_error"])

if "demo_result" in st.session_state:
    result = st.session_state["demo_result"]
    st.subheader("Answer")
    st.markdown(result["answer"])  # [n] markers are preserved verbatim
    st.divider()
    _sources_block(result)
    st.divider()
    _trace_block(result)
