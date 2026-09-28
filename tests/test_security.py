"""Security tests for PDF Classifier."""

import os
import tempfile
from pathlib import Path

import pytest

from pdf_classifier.analyzer import (
    ClassificationResult,
    _build_filename,
    get_allowed_base_paths,
    sanitize_filename_component,
    validate_ai_response,
    validate_destination,
)
from pdf_classifier.cli import is_valid_pdf


# Sample rules for testing
SAMPLE_RULES = {
    "categories": {
        "business": {
            "base": "~/Documents/Business",
            "subcategories": {
                "accounting": {"path": "Accounting/{year}"},
            },
        },
        "personal": {
            "base": "~/Documents/Personal",
            "subcategories": {
                "insurance": {"path": "Insurance"},
            },
        },
    },
    "companies": {},
}


class TestSanitizeFilenameComponent:
    """Tests for filename component sanitization."""

    def test_removes_path_separators(self):
        """Path separators should be replaced with underscores."""
        assert "/" not in sanitize_filename_component("foo/bar")
        assert "\\" not in sanitize_filename_component("foo\\bar")
        assert sanitize_filename_component("foo/bar") == "foo_bar"
        assert sanitize_filename_component("foo\\bar") == "foo_bar"

    def test_removes_null_bytes(self):
        """Null bytes should be removed."""
        assert "\x00" not in sanitize_filename_component("foo\x00bar")
        assert sanitize_filename_component("foo\x00bar") == "foobar"

    def test_removes_special_characters(self):
        """Special characters should be replaced."""
        dangerous_chars = '<>:"|?*'
        for char in dangerous_chars:
            result = sanitize_filename_component(f"test{char}file")
            assert char not in result

    def test_handles_empty_input(self):
        """Empty input should return 'Unknown'."""
        assert sanitize_filename_component("") == "Unknown"
        assert sanitize_filename_component(None) == "Unknown"

    def test_strips_dots_and_spaces(self):
        """Leading/trailing dots and spaces should be removed."""
        assert sanitize_filename_component("...test...") == "test"
        assert sanitize_filename_component("  test  ") == "test"
        assert sanitize_filename_component(".. test ..") == "test"

    def test_collapses_multiple_underscores(self):
        """Multiple underscores should be collapsed to one."""
        assert sanitize_filename_component("foo___bar") == "foo_bar"
        assert sanitize_filename_component("foo//bar") == "foo_bar"

    def test_limits_length(self):
        """Long strings should be truncated to 100 chars."""
        long_string = "a" * 200
        result = sanitize_filename_component(long_string)
        assert len(result) <= 100

    def test_path_traversal_attack(self):
        """Path traversal attempts should be neutralized."""
        assert ".." not in sanitize_filename_component("../../../etc/passwd")
        result = sanitize_filename_component("../../../etc/passwd")
        assert "/" not in result


class TestValidateDestination:
    """Tests for destination path validation."""

    def test_valid_destination_under_allowed_base(self):
        """Paths under allowed bases should be valid."""
        # Expand ~ for comparison
        home = os.path.expanduser("~")
        assert validate_destination(f"{home}/Documents/Business/test", SAMPLE_RULES)
        assert validate_destination("~/Documents/Business/test", SAMPLE_RULES)
        assert validate_destination("~/Documents/Personal/Insurance", SAMPLE_RULES)

    def test_rejects_path_outside_allowed_bases(self):
        """Paths outside allowed bases should be rejected."""
        assert not validate_destination("/tmp/malicious", SAMPLE_RULES)
        assert not validate_destination("/etc/passwd", SAMPLE_RULES)
        assert not validate_destination("~/Downloads/test", SAMPLE_RULES)

    def test_rejects_path_traversal(self):
        """Path traversal attempts should be rejected."""
        assert not validate_destination("~/Documents/Business/../../../etc/passwd", SAMPLE_RULES)
        assert not validate_destination("~/Documents/Personal/../../tmp", SAMPLE_RULES)

    def test_empty_rules_rejects_all(self):
        """Empty rules should reject all destinations."""
        empty_rules = {"categories": {}}
        assert not validate_destination("~/Documents/test", empty_rules)

    def test_base_path_exact_match(self):
        """Exact base path should be valid."""
        assert validate_destination("~/Documents/Business", SAMPLE_RULES)
        assert validate_destination("~/Documents/Personal", SAMPLE_RULES)


class TestValidateAiResponse:
    """Tests for AI response validation."""

    def test_valid_response(self):
        """Valid responses should pass validation."""
        valid = {
            "category": "business",
            "subcategory": "accounting",
            "company": "Test Co",
            "doc_type": "Invoice",
            "doc_date": "2024-01-15",
            "confidence": "high",
        }
        is_valid, error = validate_ai_response(valid)
        assert is_valid
        assert error == ""

    def test_missing_required_fields(self):
        """Missing required fields should fail validation."""
        incomplete = {"category": "business"}
        is_valid, error = validate_ai_response(incomplete)
        assert not is_valid
        assert "Missing required field" in error

    def test_invalid_date_format(self):
        """Invalid date formats should fail validation."""
        invalid_date = {
            "category": "business",
            "subcategory": "accounting",
            "company": "Test",
            "doc_type": "Invoice",
            "doc_date": "01-15-2024",  # Wrong format
        }
        is_valid, error = validate_ai_response(invalid_date)
        assert not is_valid
        assert "Invalid date format" in error

    def test_invalid_date_values(self):
        """Invalid date values should fail validation."""
        invalid_date = {
            "category": "business",
            "subcategory": "accounting",
            "company": "Test",
            "doc_type": "Invoice",
            "doc_date": "2024-13-45",  # Invalid month/day
        }
        is_valid, error = validate_ai_response(invalid_date)
        assert not is_valid
        assert "Invalid date values" in error

    def test_invalid_confidence_defaults_to_medium(self):
        """Invalid confidence should be defaulted to medium."""
        response = {
            "category": "business",
            "subcategory": "accounting",
            "company": "Test",
            "doc_type": "Invoice",
            "confidence": "very_high",  # Invalid
        }
        is_valid, _ = validate_ai_response(response)
        assert is_valid
        assert response["confidence"] == "medium"


class TestBuildFilename:
    """Tests for filename building with sanitization."""

    def test_basic_filename(self):
        """Basic filename generation should work."""
        parsed = {
            "doc_date": "2024-01-15",
            "category": "business",
            "subcategory": "accounting",
            "company": "Test Co",
            "title": "Invoice",
        }
        filename = _build_filename(parsed)
        assert filename.endswith(".pdf")
        assert "2024-01-15" in filename

    def test_sanitizes_malicious_components(self):
        """Malicious filename components should be sanitized."""
        parsed = {
            "doc_date": "2024-01-15",
            "category": "../../etc",
            "subcategory": "passwd",
            "company": "malicious/path",
            "title": "attack<script>",
        }
        filename = _build_filename(parsed)
        assert "/" not in filename
        assert "\\" not in filename
        assert ".." not in filename
        assert "<" not in filename

    def test_invalid_date_uses_today(self):
        """Invalid date format should fall back to today's date."""
        parsed = {
            "doc_date": "invalid-date",
            "category": "business",
            "subcategory": "test",
            "company": "Test",
            "title": "Doc",
        }
        filename = _build_filename(parsed)
        # Should contain a valid date format
        import re
        assert re.search(r"\d{4}-\d{2}-\d{2}", filename)


class TestGetAllowedBasePaths:
    """Tests for extracting allowed base paths from rules."""

    def test_extracts_all_bases(self):
        """Should extract all base paths from rules."""
        paths = get_allowed_base_paths(SAMPLE_RULES)
        home = os.path.expanduser("~")
        assert f"{home}/Documents/Business" in paths
        assert f"{home}/Documents/Personal" in paths

    def test_empty_rules(self):
        """Empty rules should return empty set."""
        paths = get_allowed_base_paths({"categories": {}})
        assert len(paths) == 0

    def test_handles_missing_base(self):
        """Categories without base should be skipped."""
        rules = {
            "categories": {
                "nobase": {"subcategories": {}},
                "withbase": {"base": "~/Documents/Test"},
            }
        }
        paths = get_allowed_base_paths(rules)
        assert len(paths) == 1


class TestIsValidPdf:
    """Tests for PDF magic byte validation."""

    def test_valid_pdf(self):
        """Valid PDF should pass validation."""
        with tempfile.NamedTemporaryFile(suffix=".pdf", delete=False) as f:
            f.write(b"%PDF-1.4\n")
            f.flush()
            try:
                assert is_valid_pdf(Path(f.name))
            finally:
                os.unlink(f.name)

    def test_invalid_pdf_wrong_header(self):
        """File with wrong header should fail."""
        with tempfile.NamedTemporaryFile(suffix=".pdf", delete=False) as f:
            f.write(b"Not a PDF file")
            f.flush()
            try:
                assert not is_valid_pdf(Path(f.name))
            finally:
                os.unlink(f.name)

    def test_text_file_with_pdf_extension(self):
        """Text file with .pdf extension should fail."""
        with tempfile.NamedTemporaryFile(suffix=".pdf", delete=False) as f:
            f.write(b"This is just text, not a PDF")
            f.flush()
            try:
                assert not is_valid_pdf(Path(f.name))
            finally:
                os.unlink(f.name)

    def test_nonexistent_file(self):
        """Nonexistent file should fail gracefully."""
        assert not is_valid_pdf(Path("/nonexistent/file.pdf"))

    def test_empty_file(self):
        """Empty file should fail."""
        with tempfile.NamedTemporaryFile(suffix=".pdf", delete=False) as f:
            try:
                assert not is_valid_pdf(Path(f.name))
            finally:
                os.unlink(f.name)


class TestPathTraversalIntegration:
    """Integration tests for path traversal prevention."""

    def test_full_path_traversal_attempt(self):
        """Full path traversal attack should be blocked at multiple levels."""
        malicious_response = {
            "category": "../../../etc",
            "subcategory": "passwd",
            "company": "../root",
            "doc_type": "../../shadow",
            "doc_date": "2024-01-15",
            "title": "attack",
        }

        # Sanitization should clean the components
        sanitized_cat = sanitize_filename_component(malicious_response["category"])
        assert "/" not in sanitized_cat
        assert ".." not in sanitized_cat

        # Even if sanitization fails somehow, destination validation should block
        assert not validate_destination("/etc/passwd", SAMPLE_RULES)
        assert not validate_destination("../../../etc", SAMPLE_RULES)
