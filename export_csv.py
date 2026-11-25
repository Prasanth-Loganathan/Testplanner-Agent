"""
Export the test-case table from a Markdown test plan to a CSV file.

The agent writes its test cases as a Markdown table:

    | ID | Page | Scenario | Steps | Expected result | Priority | Type |
    |----|------|----------|-------|-----------------|----------|------|
    | TC-001 | ... | ... | ... | ... | High | Positive |

This file finds that table and saves it as CSV, which opens in Excel or
Google Sheets and can be imported into Jira / Xray / TestRail.

Use it on its own for plans you already have:
    python export_csv.py                          # every .md file in output/
    python export_csv.py output/test_plan_x.md    # one file
"""

import csv
import io
import sys
from pathlib import Path

import config


def _split_row(line: str) -> list[str]:
    """'| a | b |' -> ['a', 'b']"""
    line = line.strip()
    if line.startswith("|"):
        line = line[1:]
    if line.endswith("|"):
        line = line[:-1]
    return [cell.strip().replace("<br>", "\n") for cell in line.split("|")]


def _is_separator(cells: list[str]) -> bool:
    """True for the '|----|:---:|' line under a table header."""
    return all(cell and set(cell) <= set("-: ") for cell in cells)


def find_tables(markdown: str) -> list[list[list[str]]]:
    """Return every Markdown table in the text as a list of rows (header first)."""
    tables, current = [], []
    for line in markdown.splitlines():
        if line.strip().startswith("|"):
            cells = _split_row(line)
            if not _is_separator(cells):
                current.append(cells)
        elif current:
            tables.append(current)
            current = []
    if current:
        tables.append(current)
    return tables


def get_test_cases(markdown: str) -> list[list[str]]:
    """
    Return the test-case table (header + rows).

    Picks the first table whose header has an "ID" column; falls back to the
    biggest table if the LLM named the columns differently.
    """
    tables = find_tables(markdown)
    if not tables:
        return []
    for table in tables:
        if any(cell.lower() == "id" for cell in table[0]):
            return _even_columns(table)
    return _even_columns(max(tables, key=len))


def _even_columns(table: list[list[str]]) -> list[list[str]]:
    """Pad or trim every row to the header's width (LLMs sometimes drop a cell)."""
    width = len(table[0])
    return [(row + [""] * width)[:width] for row in table]


def rows_to_csv_text(rows: list[list[str]], delimiter: str | None = None) -> str:
    """Turn rows into CSV text (used by the web app's download button)."""
    buffer = io.StringIO()
    csv.writer(buffer, delimiter=delimiter or config.CSV_DELIMITER).writerows(rows)
    return buffer.getvalue()


def export_csv(md_path: Path, csv_path: Path | None = None) -> Path | None:
    """Write the test cases of `md_path` to CSV. Returns the CSV path, or None if no table."""
    rows = get_test_cases(md_path.read_text(encoding="utf-8"))
    if len(rows) < 2:  # header only, or nothing
        return None
    csv_path = csv_path or md_path.with_suffix(".csv")
    # utf-8-sig adds a BOM so Excel shows umlauts and other characters correctly.
    csv_path.write_text(rows_to_csv_text(rows), encoding="utf-8-sig", newline="")
    return csv_path


def main() -> None:
    paths = [Path(p) for p in sys.argv[1:]] or sorted(Path(config.OUTPUT_DIR).glob("*.md"))
    if not paths:
        print(f"No .md files found in {config.OUTPUT_DIR}/")
        return
    for md_path in paths:
        result = export_csv(md_path)
        if result:
            print(f"Saved: {result}")
        else:
            print(f"No test-case table found in {md_path}")


if __name__ == "__main__":
    main()
