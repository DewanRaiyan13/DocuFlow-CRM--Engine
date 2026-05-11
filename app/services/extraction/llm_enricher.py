"""
LLM Enrichment Service.

Takes raw extracted text and asks an LLM to derive "soft" data points
that regex alone cannot reliably capture:

  - Document classification (proposal / contract / invoice / case file)
  - Project sentiment (positive / neutral / negative)
  - Total budget / contract value
  - Key deadlines and next steps
  - One-paragraph executive summary

The service is provider-agnostic: switch between Claude, Gemini, or
OpenAI by changing a single env var.
"""

from __future__ import annotations

import json
import logging
from dataclasses import dataclass, field

import httpx

from app.config import get_settings

logger = logging.getLogger(__name__)
settings = get_settings()


# ── Structured prompt for reliable JSON output ────────────────────
_SYSTEM_PROMPT = """\
You are a document analysis assistant for a CRM system used by freelancers.
Analyze the provided document text and extract structured metadata.
Respond ONLY with valid JSON matching this exact schema:

{
  "document_type": "proposal" | "contract" | "invoice" | "case_file" | "correspondence" | "other",
  "sentiment": "positive" | "neutral" | "negative",
  "total_budget": <number or null>,
  "currency": <string or null>,
  "deadlines": [{"description": "<string>", "date": "<YYYY-MM-DD or null>"}],
  "key_parties": [{"name": "<string>", "role": "<string>"}],
  "summary": "<one paragraph executive summary>",
  "next_steps": "<concise next-action items>"
}

Rules:
- Extract budget/monetary values if present. Set null if not found.
- Dates should be in YYYY-MM-DD format where possible.
- Sentiment reflects the overall tone toward the business relationship.
- Be precise and factual. Do not hallucinate information not in the text.
"""


@dataclass
class LLMEnrichmentResult:
    """Parsed output from the LLM enrichment call."""

    document_type: str = "other"
    sentiment: str = "unknown"
    total_budget: float | None = None
    currency: str | None = None
    deadlines: list[dict] = field(default_factory=list)
    key_parties: list[dict] = field(default_factory=list)
    summary: str = ""
    next_steps: str = ""
    raw_response: str = ""
    success: bool = False
    error: str | None = None


class LLMEnricher:
    """
    Provider-agnostic LLM enrichment service.

    Supports Claude (Anthropic), Gemini (Google), and OpenAI.
    Selection is driven by ``settings.LLM_PROVIDER``.
    """

    # ── Max characters sent to the LLM (cost control) ─────────────
    MAX_TEXT_LENGTH = 12_000

    def __init__(self) -> None:
        self._provider = settings.LLM_PROVIDER
        self._api_key = settings.LLM_API_KEY
        self._model = settings.LLM_MODEL
        self._max_tokens = settings.LLM_MAX_TOKENS
        self._temperature = settings.LLM_TEMPERATURE

    async def enrich(self, raw_text: str) -> LLMEnrichmentResult:
        """
        Send document text to the configured LLM and parse the response.

        Returns an LLMEnrichmentResult – always safe to access, even on failure.
        """
        if not self._api_key:
            return LLMEnrichmentResult(
                error="LLM_API_KEY not configured. Skipping enrichment.",
            )

        truncated = raw_text[: self.MAX_TEXT_LENGTH]

        try:
            raw = await self._call_llm(truncated)
            return self._parse_response(raw)
        except Exception as exc:
            logger.exception("LLM enrichment failed")
            return LLMEnrichmentResult(error=str(exc))

    async def _call_llm(self, text: str) -> str:
        """Dispatch to the correct provider."""
        dispatch = {
            "claude": self._call_claude,
            "gemini": self._call_gemini,
            "openai": self._call_openai,
        }
        handler = dispatch.get(self._provider)
        if not handler:
            raise ValueError(f"Unsupported LLM provider: {self._provider}")
        return await handler(text)

    async def _call_claude(self, text: str) -> str:
        async with httpx.AsyncClient(timeout=60) as client:
            resp = await client.post(
                "https://api.anthropic.com/v1/messages",
                headers={
                    "x-api-key": self._api_key,
                    "anthropic-version": "2023-06-01",
                    "content-type": "application/json",
                },
                json={
                    "model": self._model,
                    "max_tokens": self._max_tokens,
                    "temperature": self._temperature,
                    "system": _SYSTEM_PROMPT,
                    "messages": [
                        {"role": "user", "content": f"Analyze this document:\n\n{text}"}
                    ],
                },
            )
            resp.raise_for_status()
            data = resp.json()
            return data["content"][0]["text"]

    async def _call_gemini(self, text: str) -> str:
        url = (
            f"https://generativelanguage.googleapis.com/v1beta/"
            f"models/{self._model}:generateContent"
        )
        async with httpx.AsyncClient(timeout=60) as client:
            resp = await client.post(
                url,
                params={"key": self._api_key},
                json={
                    "contents": [
                        {
                            "parts": [
                                {"text": f"{_SYSTEM_PROMPT}\n\nDocument:\n{text}"}
                            ]
                        }
                    ],
                    "generationConfig": {
                        "temperature": self._temperature,
                        "maxOutputTokens": self._max_tokens,
                    },
                },
            )
            resp.raise_for_status()
            data = resp.json()
            return data["candidates"][0]["content"]["parts"][0]["text"]

    async def _call_openai(self, text: str) -> str:
        async with httpx.AsyncClient(timeout=60) as client:
            resp = await client.post(
                "https://api.openai.com/v1/chat/completions",
                headers={
                    "Authorization": f"Bearer {self._api_key}",
                    "Content-Type": "application/json",
                },
                json={
                    "model": self._model,
                    "temperature": self._temperature,
                    "max_tokens": self._max_tokens,
                    "messages": [
                        {"role": "system", "content": _SYSTEM_PROMPT},
                        {"role": "user", "content": f"Analyze this document:\n\n{text}"},
                    ],
                },
            )
            resp.raise_for_status()
            data = resp.json()
            return data["choices"][0]["message"]["content"]

    @staticmethod
    def _parse_response(raw: str) -> LLMEnrichmentResult:
        """Extract JSON from LLM response (handles markdown fences)."""
        result = LLMEnrichmentResult(raw_response=raw)

        # Strip markdown code fences if present
        cleaned = raw.strip()
        if cleaned.startswith("```"):
            lines = cleaned.split("\n")
            # Remove first and last fence lines
            lines = [line for line in lines if not line.strip().startswith("```")]
            cleaned = "\n".join(lines)

        try:
            data = json.loads(cleaned)
        except json.JSONDecodeError as exc:
            result.error = f"Failed to parse LLM JSON: {exc}"
            return result

        result.document_type = data.get("document_type", "other")
        result.sentiment = data.get("sentiment", "unknown")
        result.total_budget = data.get("total_budget")
        result.currency = data.get("currency")
        result.deadlines = data.get("deadlines", [])
        result.key_parties = data.get("key_parties", [])
        result.summary = data.get("summary", "")
        result.next_steps = data.get("next_steps", "")
        result.success = True

        return result
