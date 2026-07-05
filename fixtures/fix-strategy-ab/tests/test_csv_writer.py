"""Tests for csv_writer — the critical test targets repeated header emission."""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from src.csv_writer import CSVWriter


def test_single_row(tmp_path):
    p = tmp_path / "out.csv"
    w = CSVWriter(p, ["name", "age"])
    w.write_row({"name": "Alice", "age": "30"})
    lines = p.read_text().splitlines()
    assert lines == ["name,age", "Alice,30"]


def test_multiple_rows_one_header(tmp_path):
    """Header must appear exactly once, even after multiple write_row calls."""
    p = tmp_path / "out.csv"
    w = CSVWriter(p, ["x", "y"])
    w.write_row({"x": "1", "y": "2"})
    w.write_row({"x": "3", "y": "4"})
    text = p.read_text()
    header_count = text.count("x,y\n")
    assert header_count == 1, f"Header appeared {header_count} times:\n{text}"


def test_read_all(tmp_path):
    p = tmp_path / "out.csv"
    w = CSVWriter(p, ["k", "v"])
    w.write_row({"k": "a", "v": "b"})
    rows = w.read_all()
    assert rows == [{"k": "a", "v": "b"}]
