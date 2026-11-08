"""Run from the project folder:   python -m unittest tests.test_dates -v"""
import unittest
from datetime import date

from app.timeutil import month_end, month_start, previous_month


class MonthHelperTests(unittest.TestCase):
    def test_month_bounds(self):
        self.assertEqual(month_start(date(2026, 10, 24)), date(2026, 10, 1))
        self.assertEqual(month_end(date(2026, 10, 24)), date(2026, 10, 31))
        self.assertEqual(month_end(date(2026, 2, 10)), date(2026, 2, 28))
        self.assertEqual(month_end(date(2028, 2, 10)), date(2028, 2, 29))     # leap year
        self.assertEqual(month_end(date(2026, 12, 5)), date(2026, 12, 31))

    def test_previous_month(self):
        self.assertEqual(previous_month(date(2026, 3, 15)), date(2026, 2, 1))
        self.assertEqual(previous_month(date(2026, 1, 15)), date(2025, 12, 1))


if __name__ == "__main__":
    unittest.main()
