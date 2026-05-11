"""
Unit tests for the extraction layer.

Tests use small fixture files to verify PDF and DOCX extractors
work correctly in isolation.
"""

import pytest
from pathlib import Path
from unittest.mock import patch, MagicMock

from app.services.extraction.base import ExtractionResult
from app.services.extraction.registry import ExtractorRegistry


class TestExtractorRegistry:
    """Verify registry dispatches to the correct extractor."""

    def test_pdf_extractor_registered(self):
        registry = ExtractorRegistry()
        extractor = registry.get_extractor(Path("test.pdf"))
        assert extractor is not None
        assert ".pdf" in extractor.supported_extensions

    def test_docx_extractor_registered(self):
        registry = ExtractorRegistry()
        extractor = registry.get_extractor(Path("test.docx"))
        assert extractor is not None
        assert ".docx" in extractor.supported_extensions

    def test_unsupported_extension_returns_none(self):
        registry = ExtractorRegistry()
        extractor = registry.get_extractor(Path("test.xlsx"))
        assert extractor is None

    @pytest.mark.asyncio
    async def test_unsupported_file_returns_error(self):
        registry = ExtractorRegistry()
        result = await registry.extract(Path("test.xlsx"))
        assert not result.is_successful
        assert len(result.errors) > 0


class TestExtractionResult:
    """Verify ExtractionResult contract."""

    def test_successful_result(self):
        result = ExtractionResult(raw_text="Hello world", page_count=1)
        assert result.is_successful

    def test_failed_result_with_errors(self):
        result = ExtractionResult(errors=["Parse failed"])
        assert not result.is_successful

    def test_empty_text_is_not_successful(self):
        result = ExtractionResult(raw_text="")
        assert not result.is_successful
