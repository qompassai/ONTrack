"""
test_exporter.py — unit tests for core/exporter.py

Covers:
  - export_csv writes correct header + rows
  - stop numbers are 1-based
  - empty list writes only the header
  - addresses with commas are escaped correctly (CSV quoting)
  - build_maps_url: correct base, all addresses present, spaces replaced
  - build_maps_url: single address
  - build_maps_url: empty list returns bare base URL
"""

import csv
import pathlib
import pytest

from core.exporter import export_csv, build_maps_url

MAPS_BASE = "https://www.google.com/maps/dir/"


# ── export_csv ─────────────────────────────────────────────────────────────

class TestExportCSV:
    def test_header_and_rows(self, tmp_path, three_addresses):
        out = str(tmp_path / "route.csv")
        export_csv(three_addresses, out)
        with open(out, newline="") as f:
            rows = list(csv.reader(f))
        assert rows[0] == ["stop", "address"]
        assert rows[1] == ["1", three_addresses[0]]
        assert rows[2] == ["2", three_addresses[1]]
        assert rows[3] == ["3", three_addresses[2]]

    def test_stop_numbers_one_based(self, tmp_path, three_addresses):
        out = str(tmp_path / "route.csv")
        export_csv(three_addresses, out)
        with open(out, newline="") as f:
            rows = list(csv.reader(f))
        stops = [int(r[0]) for r in rows[1:]]
        assert stops == [1, 2, 3]

    def test_empty_list(self, tmp_path):
        out = str(tmp_path / "empty.csv")
        export_csv([], out)
        with open(out, newline="") as f:
            rows = list(csv.reader(f))
        assert rows == [["stop", "address"]]

    def test_address_with_comma(self, tmp_path):
        addrs = ["100 A St, Suite 5, Spokane WA"]
        out = str(tmp_path / "comma.csv")
        export_csv(addrs, out)
        with open(out, newline="") as f:
            rows = list(csv.reader(f))
        assert rows[1][1] == addrs[0]

    def test_file_created(self, tmp_path, three_addresses):
        out = str(tmp_path / "new_file.csv")
        assert not pathlib.Path(out).exists()
        export_csv(three_addresses, out)
        assert pathlib.Path(out).exists()

    def test_single_address(self, tmp_path):
        out = str(tmp_path / "single.csv")
        export_csv(["Only Stop"], out)
        with open(out, newline="") as f:
            rows = list(csv.reader(f))
        assert len(rows) == 2
        assert rows[1] == ["1", "Only Stop"]


# ── build_maps_url ─────────────────────────────────────────────────────────

class TestBuildMapsURL:
    def test_starts_with_base(self, three_addresses):
        url = build_maps_url(three_addresses)
        assert url.startswith(MAPS_BASE)

    def test_all_addresses_present(self, three_addresses):
        url = build_maps_url(three_addresses)
        for addr in three_addresses:
            encoded = addr.replace(" ", "+")
            assert encoded in url

    def test_spaces_replaced_with_plus(self):
        url = build_maps_url(["123 Main St"])
        assert " " not in url
        assert "123+Main+St" in url

    def test_single_address(self):
        url = build_maps_url(["456 Elm St Spokane WA"])
        assert url == MAPS_BASE + "456+Elm+St+Spokane+WA"

    def test_empty_list(self):
        url = build_maps_url([])
        assert url == MAPS_BASE

    def test_two_stops_separator(self):
        url = build_maps_url(["A St", "B Ave"])
        assert url == MAPS_BASE + "A+St/B+Ave"
