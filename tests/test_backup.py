"""Run from the project folder:   python -m unittest tests.test_backup -v"""
import csv
import io
import unittest
import zipfile
from datetime import date, datetime, timezone
from decimal import Decimal

from app.services.backup_files import build_zip, rows_to_csv_bytes


def _read_csv(data: bytes) -> list[list[str]]:
    return list(csv.reader(io.StringIO(data.decode("utf-8-sig"))))


class CsvTests(unittest.TestCase):
    def test_header_and_values(self):
        data = rows_to_csv_bytes(["id", "name", "amount", "when", "hidden"],
                                 [{"id": 1, "name": "Azam", "amount": Decimal("25.50"),
                                   "when": date(2026, 1, 8), "hidden": False}])
        self.assertEqual(_read_csv(data), [["id", "name", "amount", "when", "hidden"],
                                           ["1", "Azam", "25.50", "2026-01-08", "FALSE"]])

    def test_empty_values_commas_quotes_and_bangla(self):
        data = rows_to_csv_bytes(["a", "b", "c"], [{"a": None, "b": 'He said "hi", ok', "c": "বেগুন"}])
        self.assertEqual(_read_csv(data)[1], ["", 'He said "hi", ok', "বেগুন"])

    def test_text_that_looks_like_a_formula_is_made_safe_but_numbers_are_not(self):
        data = rows_to_csv_bytes(["note", "amount"], [{"note": "=SUM(A1:A9)", "amount": Decimal("-200.00")}])
        self.assertEqual(_read_csv(data)[1], ["'=SUM(A1:A9)", "-200.00"])

    def test_timestamp_keeps_its_time_zone(self):
        # the database stores UTC; the backup keeps the +00:00 so the time is never ambiguous
        stamp = datetime(2026, 1, 8, 9, 30, 15, tzinfo=timezone.utc)
        self.assertEqual(_read_csv(rows_to_csv_bytes(["t"], [{"t": stamp}]))[1], ["2026-01-08 09:30:15+00:00"])

    def test_file_starts_with_a_bom_so_excel_reads_utf8(self):
        self.assertTrue(rows_to_csv_bytes(["a"], []).startswith(b"\xef\xbb\xbf"))


class ZipTests(unittest.TestCase):
    def test_zip_has_a_csv_per_table_and_a_readme(self):
        tables = {"farm_owners": (["id", "name"], [{"id": 1, "name": "Azam"}, {"id": 2, "name": "Khalil"}]),
                  "days": (["id"], [])}
        archive = zipfile.ZipFile(io.BytesIO(build_zip(tables, datetime(2026, 1, 8, 9, 30))))
        self.assertEqual(sorted(archive.namelist()), ["README.txt", "days.csv", "farm_owners.csv"])
        readme = archive.read("README.txt").decode("utf-8")
        self.assertIn("farm_owners: 2", readme)
        self.assertIn("days: 0", readme)
        self.assertIn("08 Jan 2026, 09:30", readme)
        self.assertEqual(_read_csv(archive.read("farm_owners.csv"))[2], ["2", "Khalil"])


if __name__ == "__main__":
    unittest.main()
