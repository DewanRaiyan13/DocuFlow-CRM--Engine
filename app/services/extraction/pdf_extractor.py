"""
PDF extractor using PyMuPDF (fitz).

Handles structured text extraction, title heuristics, date parsing,
and case-number regex matching from PDF documents.
"""

from __future__ import annotations

import re
from datetime import datetime
from pathlib import Path

import fitz  # PyMuPDF

from app.services.extraction.base import BaseExtractor, ExtractionResult

# ── Regex patterns for metadata extraction ─────────────────────────
_CASE_NUMBER_PATTERN = re.compile(
    r"(?:case|file|ref(?:erence)?|docket|matter)\s*(?:#|no\.?|number)?\s*[:.]?\s*"
    r"([A-Z0-9][\w\-/.]{2,20})",
    re.IGNORECASE,
)

_DATE_PATTERNS = [
    re.compile(r"\b(\d{1,2}[/-]\d{1,2}[/-]\d{2,4})\b"),
    re.compile(r"\b(\w+ \d{1,2},? \d{4})\b"),
    re.compile(r"\b(\d{4}-\d{2}-\d{2})\b"),
]

_DATE_FORMATS = [
    "%m/%d/%Y", "%m-%d-%Y", "%d/%m/%Y", "%d-%m-%Y",
    "%B %d, %Y", "%B %d %Y", "%b %d, %Y", "%b %d %Y",
    "%Y-%m-%d",
]


class PDFExtractor(BaseExtractor):
    """Extract text and metadata from PDF files via PyMuPDF."""

    @property
    def supported_extensions(self) -> set[str]:
        return {".pdf"}

    async def extract(self, file_path: Path) -> ExtractionResult:
        result = ExtractionResult()

        try:
            doc = fitz.open(str(file_path))
        except Exception as exc:
            result.errors.append(f"Failed to open PDF: {exc}")
            return result

        try:
            result.page_count = len(doc)

            # ── Full text extraction ───────────────────────────────
            pages_text: list[str] = []
            for page in doc:
                text = page.get_text("text")
                if text:
                    pages_text.append(text)

            result.raw_text = "\n\n".join(pages_text)

            # ── Title heuristic: first non-blank line of page 1 ───
            if pages_text:
                for line in pages_text[0].split("\n"):
                    stripped = line.strip()
                    if stripped and len(stripped) > 3:
                        result.title = stripped[:500]
                        break

            # ── Case number detection ──────────────────────────────
            match = _CASE_NUMBER_PATTERN.search(result.raw_text[:5000])
            if match:
                result.case_number = match.group(1).strip()

            # ── Date detection ─────────────────────────────────────
            result.date = self._extract_earliest_date(
                result.raw_text[:3000]
            )

            # ── PDF metadata (author, producer, etc.) ──────────────
            pdf_meta = doc.metadata or {}
            result.metadata = {
                k: v for k, v in pdf_meta.items() if v
            }

        except Exception as exc:
            result.errors.append(f"Extraction error: {exc}")
        finally:
            doc.close()

        return result

    @staticmethod
    def _extract_earliest_date(text: str) -> datetime | None:
        """
        Scan text for date-like strings, parse them, and return the
        earliest valid date found.
        """
        candidates: list[datetime] = []

        for pattern in _DATE_PATTERNS:
            for raw_match in pattern.findall(text):
                for fmt in _DATE_FORMATS:
                    try:
                        parsed = datetime.strptime(raw_match, fmt)
                        # Sanity: year between 1990 and 2040
                        if 1990 <= parsed.year <= 2040:
                            candidates.append(parsed)
                            break
                    except ValueError:
                        continue

        return min(candidates) if candidates else None
