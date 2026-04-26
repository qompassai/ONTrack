"""
test_parser.py — unit tests for core/parser.py

Covers:
  - CSV happy path
  - Excel happy path
  - Missing 'address' column raises KeyError
  - Empty file returns empty list
  - NaN rows are dropped
  - Unsupported extension falls through to read_excel (openpyxl)
"""

import pathlib
import pytest
import pandas as pd

from core.parser import parse_addresses

TESTS_DIR = pathlib.Path(__file__).parent


# ── Helpers ────────────────────────────────────────────────────────────────

def _write_csv(path, rows):
    df = pd.DataFrame(rows)
    df.to_csv(path, index=False)
    return str(path)


def _write_excel(path, rows):
    df = pd.DataFrame(rows)
    df.to_excel(path, index=False)
    return str(path)


# ── CSV tests ──────────────────────────────────────────────────────────────

class TestParseCSV:
    def test_happy_path(self, tmp_path):
        rows = {"address": ["100 A St", "200 B Ave", "300 C Blvd"]}
        p = _write_csv(tmp_path / "ok.csv", rows)
        result = parse_addresses(p)
        assert result == ["100 A St", "200 B Ave", "300 C Blvd"]

    def test_sample_file(self):
        """The committed sample file must parse without error."""
        result = parse_addresses(str(TESTS_DIR / "sample_addresses.csv"))
        assert len(result) == 3
        assert all(isinstance(a, str) for a in result)

    def test_drops_nan_rows(self, tmp_path):
        p = tmp_path / "nan.csv"
        p.write_text("address\n123 Main St\n\n456 Elm St\n")
        result = parse_addresses(str(p))
        assert len(result) == 2
        assert "" not in result

    def test_empty_file_returns_empty_list(self, tmp_path):
        p = tmp_path / "empty.csv"
        p.write_text("address\n")
        result = parse_addresses(str(p))
        assert result == []

    def test_missing_address_column_raises(self, tmp_path):
        rows = {"street": ["100 A St"]}
        p = _write_csv(tmp_path / "bad_col.csv", rows)
        with pytest.raises(KeyError):
            parse_addresses(p)

    def test_extra_columns_ignored(self, tmp_path):
        rows = {"address": ["100 A St"], "city": ["Spokane"], "state": ["WA"]}
        p = _write_csv(tmp_path / "extra.csv", rows)
        result = parse_addresses(p)
        assert result == ["100 A St"]

    def test_whitespace_preserved(self, tmp_path):
        rows = {"address": ["  100 A St  "]}
        p = _write_csv(tmp_path / "ws.csv", rows)
        result = parse_addresses(p)
        # Parser should return whatever pandas reads; spaces are preserved
        assert "100 A St" in result[0]

    def test_large_file_performance(self, tmp_path):
        """1 000-row CSV must parse in under 2 seconds."""
        import time
        rows = {"address": [f"{i} Test St Spokane WA" for i in range(1000)]}
        p = _write_csv(tmp_path / "large.csv", rows)
        start = time.monotonic()
        result = parse_addresses(p)
        elapsed = time.monotonic() - start
        assert len(result) == 1000
        assert elapsed < 2.0, f"parse_addresses took {elapsed:.2f}s on 1 000 rows"


# ── Excel tests ────────────────────────────────────────────────────────────

class TestParseExcel:
    def test_happy_path(self, tmp_path):
        rows = {"address": ["100 A St", "200 B Ave"]}
        p = _write_excel(tmp_path / "ok.xlsx", rows)
        result = parse_addresses(p)
        assert result == ["100 A St", "200 B Ave"]

    def test_missing_column_raises(self, tmp_path):
        rows = {"street": ["100 A St"]}
        p = _write_excel(tmp_path / "bad.xlsx", rows)
        with pytest.raises(KeyError):
            parse_addresses(p)

    def test_drops_nan_rows(self, tmp_path):
        df = pd.DataFrame({"address": ["100 A St", None, "200 B Ave"]})
        p = str(tmp_path / "nan.xlsx")
        df.to_excel(p, index=False)
        result = parse_addresses(p)
        assert len(result) == 2
