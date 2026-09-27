"""LLM answer module — thin chat client (Step 4.1) + grounded prompt
builder (Step 4.2).

DeepSeek (official API, default) and OpenRouter (optional fallback) both
expose an OpenAI-compatible REST API, so the `openai` SDK is simply
pointed at the provider's base_url. One thin client, two providers — no
multi-provider abstraction.

- Provider: DEEPSEEK_API_KEY present -> DeepSeek (default), else
  OPENROUTER_API_KEY -> OpenRouter. Pass `provider` explicitly to force
  one. Keys come from the shell environment or the project-root .env
  (auto-loaded by config.py; see .env.example); never hardcoded.
- Model: provider model env var > provider default (centralized in
  config.py — no model names anywhere else): DEEPSEEK_MODEL /
  DEEPSEEK_MODEL_DEFAULT for DeepSeek, LLM_MODEL / LLM_MODEL_DEFAULT
  for OpenRouter.
- Missing key / API failures raise OpenRouterError with a clear message.

Step 4.2 adds build_grounded_prompt() below — the LLM prompt built from
question + Step 3.3 final evidence. Step 4.3 adds generate_answer(), which
runs that prompt through the client and returns verified citations ([n] →
chunk ids) that can only ever point at kept evidence. The client itself
stays this simple.
"""

import os
import re

from openai import OpenAI

from . import config


class OpenRouterError(RuntimeError):
    """Raised when the LLM call cannot be completed (config or API error).

    Name kept from the original OpenRouter-only client for compatibility;
    covers any provider.
    """


class LLMClient:
    """Minimal chat client: DeepSeek (default) or OpenRouter (optional).

    complete(prompt) -> answer text. Provider auto-detection:
    DEEPSEEK_API_KEY present -> DeepSeek, else OPENROUTER_API_KEY ->
    OpenRouter. Pass `provider` (config.LLM_PROVIDER_DEEPSEEK /
    config.LLM_PROVIDER_OPENROUTER) explicitly to force one regardless of
    the environment.
    """

    def __init__(self, model: str | None = None, api_key: str | None = None,
                 base_url: str | None = None,
                 provider: str | None = None):
        provider_explicit = provider
        provider = provider or (
            config.LLM_PROVIDER_DEEPSEEK
            if os.environ.get(config.DEEPSEEK_API_KEY_ENV)
            else config.LLM_PROVIDER_OPENROUTER)
        self.provider = provider
        if provider == config.LLM_PROVIDER_DEEPSEEK:
            model_env, model_default = (config.DEEPSEEK_MODEL_ENV,
                                        config.DEEPSEEK_MODEL_DEFAULT)
            key_env, base_default = (config.DEEPSEEK_API_KEY_ENV,
                                     config.DEEPSEEK_BASE_URL)
        else:  # openrouter — the original Step 4.1 behavior, unchanged
            model_env, model_default = (config.LLM_MODEL_ENV,
                                        config.LLM_MODEL_DEFAULT)
            key_env, base_default = (config.LLM_API_KEY_ENV,
                                     config.OPENROUTER_BASE_URL)
        self.model = model or os.environ.get(model_env) or model_default
        api_key = api_key or os.environ.get(key_env, "")
        if not api_key:
            if provider_explicit is None:  # auto-detect found no key at all
                raise OpenRouterError(
                    "No LLM API key found. Set "
                    f"{config.DEEPSEEK_API_KEY_ENV} (DeepSeek — default) or "
                    f"{config.LLM_API_KEY_ENV} (OpenRouter — fallback): copy "
                    ".env.example to .env and fill it in, or export it in "
                    "your shell.")
            raise OpenRouterError(
                f"LLM API key not found for provider '{provider}'. Set the "
                f"{key_env} environment variable (copy .env.example to .env "
                f"and fill it in, or export it in your shell).")
        self.client = OpenAI(
            base_url=base_url or base_default,
            api_key=api_key,
        )

    def complete(self, prompt: str, max_tokens: int | None = None,
                 temperature: float | None = None) -> str:
        """Send one user prompt, return the model's reply text (stripped)."""
        try:
            kwargs = {}
            if self.provider == config.LLM_PROVIDER_DEEPSEEK:
                # DeepSeek defaults to thinking mode; its hidden reasoning
                # tokens count against max_tokens and starve the visible
                # answer (probed 2026-09-27: 512/512 reasoning tokens,
                # finish_reason=length, content=''). Disable thinking for
                # DeepSeek so the budget goes to the answer. OpenRouter
                # behavior is unchanged.
                kwargs["extra_body"] = {"thinking": {"type": "disabled"}}
            response = self.client.chat.completions.create(
                model=self.model,
                messages=[{"role": "user", "content": prompt}],
                max_tokens=(config.LLM_MAX_TOKENS if max_tokens is None
                            else max_tokens),
                temperature=(config.LLM_TEMPERATURE if temperature is None
                             else temperature),
                **kwargs,
            )
            content = response.choices[0].message.content or ""
        except Exception as exc:
            # extraction stays inside the try: an unexpected response shape
            # (e.g. choices=None on an upstream hiccup) must become a clean
            # OpenRouterError, not a bare TypeError. The provider name in
            # the message shows which API the call went to.
            raise OpenRouterError(
                f"{self.provider} call failed for model '{self.model}': {exc}"
            ) from exc
        return content.strip()


def complete(prompt: str, model: str | None = None, api_key: str | None = None,
             client: LLMClient | None = None) -> str:
    """One-shot convenience; pass a shared LLMClient to reuse the connection."""
    return (client or LLMClient(model=model, api_key=api_key)).complete(prompt)


# --- Grounded prompt builder (Step 4.2) ---------------------------------------


def kept_evidence(evidence: list[dict]) -> list[dict]:
    """Step 3.3 final evidence -> the entries the LLM is allowed to see.

    Entries marked conflict_status "suppressed" are excluded — suppressed
    content must never reach the prompt. Every other entry (kept,
    conflict_candidate) is valid evidence and keeps its Step 3.2 rerank
    order, so the [n] numbering is stable. Entries without the marker
    (e.g. single-source runs that skipped conflict rules) are all kept.
    Step 4.3 reuses this exact selection to map [n] back to chunk ids.
    """
    return [h for h in evidence if h.get("conflict_status") != "suppressed"]


def _evidence_meta_line(hit: dict) -> str:
    """One metadata line for an evidence entry (its [n] is added by caller)."""
    meta = hit["metadata"]
    parts = [f"source: {hit['source_type']}"]
    if meta.get("title"):
        parts.append(f"title: {meta['title']}")
    parts.append(f"chunk: {hit['chunk_id']}")
    if meta.get("version"):
        parts.append(f"version: {meta['version']}")
    if meta.get("date"):
        parts.append(f"date: {meta['date']}")
    if hit.get("authority"):  # Step 3.3 sets this on flagged community chunks
        parts.append(f"authority: {hit['authority']}")
    return " | ".join(parts)


# The LLM is told the deterministic decisions in advance so it can neither
# re-judge source authority nor re-resolve contradictions (PLAN §3.3).
_PROMPT_RULES = (
    "Answer only with facts found in the evidence. Do not use outside "
    "knowledge and do not add CloudBox facts that are not in the evidence.",
    "If the evidence is not enough to answer, say clearly that the "
    "information is insufficient. Never guess.",
    "Cite each fact with its evidence number in brackets, like [1] or [2].",
    "Source authority and contradictions have already been resolved before "
    "this prompt: official documentation is authoritative over community "
    "sources (forums, blogs). Do not re-judge authority and do not "
    "re-resolve conflicts; use the evidence exactly as given.",
    "Keep the answer concise, but cover every important condition or "
    "limitation in the evidence that is directly relevant to the question "
    "— do not omit relevant constraints just to stay short.",
)


def build_grounded_prompt(question: str, evidence: list[dict]) -> str:
    """Step 4.2: question + Step 3.3 final evidence -> one grounded prompt.

    `evidence` is the "evidence" list of retrieve_final() /
    conflict.handle_contradictions() — each entry carrying conflict_status
    from Step 3.3. Suppressed entries never enter the evidence context;
    the kept ones are numbered [1], [2], ... in their rerank order with
    source / title / chunk id / date / version metadata, ready for the
    Step 4.3 citation mapping. With no valid evidence the prompt tells the
    LLM to answer "insufficient information" instead of guessing.

    The returned string is the single user message for
    LLMClient.complete(). Pure function: no I/O, no mutation,
    deterministic output.
    """
    kept = kept_evidence(evidence)
    lines = [
        "You are CloudBox support. Answer the user's question using ONLY "
        "the evidence below.",
        "",
        "Rules:",
    ]
    lines += [f"- {rule}" for rule in _PROMPT_RULES]
    lines += ["", "Evidence:"]
    for i, hit in enumerate(kept, 1):
        lines.append(f"[{i}] {_evidence_meta_line(hit)}")
        lines.append(hit["text"].strip())
        lines.append("")
    if not kept:
        lines.append("(none — no evidence is available. Reply that the "
                     "information is insufficient; do not guess.)")
        lines.append("")
    lines.append(f"Question: {question}")
    lines.append("Answer:")
    return "\n".join(lines)


# --- Answer generation + citations (Step 4.3) ---------------------------------

_CITATION_RE = re.compile(r"\[(\d+)\]")

INSUFFICIENT_EVIDENCE_ANSWER = (
    "The provided evidence is insufficient to answer this question.")


def _parse_citations(text: str, kept: list[dict]) -> tuple[list[dict], list[int]]:
    """Map the [n] markers in an LLM answer to the kept evidence.

    Returns (citations, invalid_numbers). `citations` are deduped in order
    of first appearance in the answer text; each entry carries n,
    chunk_id, source_type and title — all taken from the actual kept
    evidence, never from LLM text. Markers that don't point at a kept
    entry (out of range) are invalid: returned as plain numbers, dropped
    as sources.
    """
    citations, invalid, seen, invalid_seen = [], [], set(), set()
    for raw in _CITATION_RE.findall(text):
        n = int(raw)
        if not 1 <= n <= len(kept):
            if n not in invalid_seen:
                invalid_seen.add(n)
                invalid.append(n)
            continue
        if n in seen:
            continue
        seen.add(n)
        hit = kept[n - 1]
        citations.append({
            "n": n,
            "chunk_id": hit["chunk_id"],
            "source_type": hit["source_type"],
            "title": hit["metadata"].get("title", ""),
        })
    return citations, invalid


def generate_answer(question: str, evidence: list[dict],
                    client: LLMClient | None = None,
                    model: str | None = None,
                    api_key: str | None = None) -> dict:
    """Step 4.3: grounded prompt -> LLM -> answer + verified citations.

    `evidence` is the "evidence" list of retrieve_final() — the same input
    build_grounded_prompt() takes. The prompt is built with the Step 4.2
    builder and sent to answer.LLMClient.complete(); the citations are
    then computed HERE by mapping the [n] markers found in the answer text
    onto kept_evidence() (Step 4.2 numbering), so the LLM can never
    promote an invented source: unknown markers land in
    `invalid_citations` and are not sources.

    With no kept evidence the LLM is not called at all — the answer is the
    fixed honest INSUFFICIENT_EVIDENCE_ANSWER, making the Step 4.2
    no-guessing rule unconditional (a model cannot be prompted into
    hallucinating when it is never prompted).

    Returns {"answer": str, "citations": [{"n", "chunk_id", "source_type",
    "title"}, ...], "invalid_citations": [n, ...]}. LLM/API errors raise
    OpenRouterError unchanged.
    """
    kept = kept_evidence(evidence)
    if not kept:
        return {"answer": INSUFFICIENT_EVIDENCE_ANSWER,
                "citations": [], "invalid_citations": []}
    prompt = build_grounded_prompt(question, evidence)
    text = (client or LLMClient(model=model, api_key=api_key)).complete(prompt)
    citations, invalid = _parse_citations(text, kept)
    return {"answer": text, "citations": citations,
            "invalid_citations": invalid}
