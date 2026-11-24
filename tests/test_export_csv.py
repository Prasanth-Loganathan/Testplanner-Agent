"""Tests for the Markdown -> CSV export. No network or LLM needed."""

import csv

import config
from export_csv import export_csv, get_test_cases

PLAN = """# Test Plan: Demo

## 2. Pages analyzed
| Page | Purpose |
|------|---------|
| / | Home |

## 3. Functional test cases
| ID | Page | Scenario | Steps | Expected result | Priority | Type |
|----|------|----------|-------|-----------------|----------|------|
| TC-001 | /login | Valid login | 1. Open, 2. Log in | Dashboard shown | High | Positive |
| TC-002 | /login | Empty password | Leave password empty | Error shown | High |

## 4. Non-functional checks
- HTTPS is used
"""


def test_picks_the_table_with_an_id_column():
    rows = get_test_cases(PLAN)
    assert rows[0] == ["ID", "Page", "Scenario", "Steps", "Expected result", "Priority", "Type"]
    assert [r[0] for r in rows[1:]] == ["TC-001", "TC-002"]


def test_short_rows_are_padded_to_header_width():
    rows = get_test_cases(PLAN)
    assert rows[2] == ["TC-002", "/login", "Empty password", "Leave password empty",
                       "Error shown", "High", ""]


def test_export_writes_csv_that_reads_back(tmp_path, monkeypatch):
    monkeypatch.setattr(config, "CSV_DELIMITER", ";")
    md = tmp_path / "plan.md"
    md.write_text(PLAN, encoding="utf-8")

    out = export_csv(md)

    assert out == tmp_path / "plan.csv"
    with out.open(encoding="utf-8-sig", newline="") as f:
        rows = list(csv.reader(f, delimiter=";"))
    assert len(rows) == 3
    assert rows[1][3] == "1. Open, 2. Log in"   # commas inside a cell stay in one cell


def test_no_table_returns_none(tmp_path):
    md = tmp_path / "empty.md"
    md.write_text("# Nothing here", encoding="utf-8")
    assert export_csv(md) is None
