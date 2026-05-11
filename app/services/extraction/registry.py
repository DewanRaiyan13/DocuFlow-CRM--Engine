"""
Extractor Registry – maps file extensions to the correct extractor.

Adding support for a new file type requires:
  1. Create a new BaseExtractor subclass.
  2. Register it here.

No other module needs to change (Open/Closed Principle).
"""

from __future__ import annotations

from pathlib import Path

from app.services.extraction.base import BaseExtractor, ExtractionResult
from app.services.extraction.pdf_extractor import PDFExtractor
from app.services.extraction.docx_extractor import DocxExtractor


class ExtractorRegistry:
    """
    Central registry of all available file extractors.

    Usage::

        registry = ExtractorRegistry()
        result = await registry.extract(Path("contract.pdf"))
    """

    def __init__(self) -> None:
        self._extractors: list[BaseExtractor] = [
            PDFExtractor(),
            DocxExtractor(),
        ]

    def register(self, extractor: BaseExtractor) -> None:
        """Register a new extractor at runtime."""
        self._extractors.append(extractor)

    def get_extractor(self, file_path: Path) -> BaseExtractor | None:
        """Find the first extractor that can handle the given file."""
        for extractor in self._extractors:
            if extractor.can_handle(file_path):
                return extractor
        return None

    async def extract(self, file_path: Path) -> ExtractionResult:
        """
        Dispatch to the correct extractor based on file extension.

        Returns an ExtractionResult with an error if no extractor matches.
        """
        extractor = self.get_extractor(file_path)
        if extractor is None:
            return ExtractionResult(
                errors=[f"No extractor registered for '{file_path.suffix}'"],
            )
        return await extractor.extract(file_path)


# Module-level singleton
extractor_registry = ExtractorRegistry()
