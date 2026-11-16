"""Builds the backup zip. No database in this file, so it is easy to test.
One CSV per table (UTF-8 with a BOM so Excel shows every character correctly)
plus a README with the date and row counts."""
import csv
import io
import zipfile
from datetime import date, datetime
from decimal import Decimal

FORMULA_STARTERS = ("=", "+", "-", "@")


def _cell(value) -> str:
    """One value as text. Text that Excel could read as a formula gets a leading ' so it is
    shown as plain text. Real numbers (Decimal, int) are left exactly as they are."""
    if value is None:
        return ""
    if isinstance(value, bool):
        return "TRUE" if value else "FALSE"
    if isinstance(value, datetime):
        return value.isoformat(sep=" ", timespec="seconds")
    if isinstance(value, (date, Decimal, int, float)):
        return str(value)
    text = str(value)
    return "'" + text if text.startswith(FORMULA_STARTERS) else text


def rows_to_csv_bytes(columns: list[str], rows: list[dict]) -> bytes:
    buffer = io.StringIO(newline="")
    writer = csv.writer(buffer)
    writer.writerow(columns)
    for row in rows:
        writer.writerow([_cell(row[c]) for c in columns])
    return ("\ufeff" + buffer.getvalue()).encode("utf-8")


def readme_text(tables: dict[str, tuple[list[str], list[dict]]], when: datetime) -> str:
    lines = [
        "SUFI VEGETABLE SALES SYSTEM - DATA BACKUP",
        f"Created: {when:%d %b %Y, %H:%M} (Dubai time)",
        "",
        "This zip holds one CSV file for every table. Double-click a file to open it in Excel.",
        "Hidden records are included too: they have is_deleted = TRUE.",
        "This is a copy of your data for safekeeping. Keep it somewhere safe (not only on this phone).",
        "",
        "Rows per table:",
    ]
    for name in sorted(tables):
        lines.append(f"  {name}: {len(tables[name][1])}")
    return "\n".join(lines) + "\n"


def build_zip(tables: dict[str, tuple[list[str], list[dict]]], when: datetime) -> bytes:
    """tables: name -> (column names, rows as dicts)."""
    out = io.BytesIO()
    with zipfile.ZipFile(out, "w", zipfile.ZIP_DEFLATED) as archive:
        archive.writestr("README.txt", readme_text(tables, when))
        for name in sorted(tables):
            columns, rows = tables[name]
            archive.writestr(f"{name}.csv", rows_to_csv_bytes(columns, rows))
    return out.getvalue()
