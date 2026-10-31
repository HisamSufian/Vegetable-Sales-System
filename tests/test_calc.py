"""Run from the project folder:   python -m unittest tests.test_calc -v"""
import unittest
from decimal import Decimal

from app.services.calc import bill_totals, line_amount, parse_money, parse_signed_int


class LineAndBillTests(unittest.TestCase):
    def test_joynal_buys_20_tomato_at_25(self):
        self.assertEqual(line_amount(20, Decimal("25")), Decimal("500.00"))

    def test_rate_pending_counts_as_zero(self):
        self.assertEqual(line_amount(20, None), Decimal("0.00"))

    def test_decimal_rates_are_exact(self):
        self.assertEqual(line_amount(3, Decimal("0.10")), Decimal("0.30"))
        self.assertEqual(line_amount(7, Decimal("12.35")), Decimal("86.45"))

    def test_bill_total_with_discount_and_pending(self):
        lines = [{"qty": 20, "rate": Decimal("25")},
                 {"qty": 5, "rate": Decimal("24")},
                 {"qty": 10, "rate": None}]
        totals = bill_totals(lines, Decimal("10"))
        self.assertEqual(totals["subtotal"], Decimal("620.00"))
        self.assertEqual(totals["total"], Decimal("610.00"))
        self.assertEqual(totals["pending_count"], 1)

    def test_empty_bill(self):
        totals = bill_totals([], Decimal("0"))
        self.assertEqual(totals["total"], Decimal("0.00"))


class ParseMoneyTests(unittest.TestCase):
    def test_blank_returns_default(self):
        self.assertEqual(parse_money("", blank=None), (None, None))
        self.assertEqual(parse_money("  ", blank=Decimal("0.00")), (Decimal("0.00"), None))

    def test_valid_numbers(self):
        self.assertEqual(parse_money("25"), (Decimal("25.00"), None))
        self.assertEqual(parse_money("25.5"), (Decimal("25.50"), None))
        self.assertEqual(parse_money("1,250.75"), (Decimal("1250.75"), None))

    def test_rejects_bad_input(self):
        for bad in ("abc", "-5", "1.234", "NaN", "Infinity", "1e20"):
            value, error = parse_money(bad)
            self.assertIsNone(value, bad)
            self.assertTrue(error, bad)


class SignedIntTests(unittest.TestCase):
    def test_valid(self):
        self.assertEqual(parse_signed_int("5"), 5)
        self.assertEqual(parse_signed_int("+5"), 5)
        self.assertEqual(parse_signed_int("-12"), -12)
        self.assertEqual(parse_signed_int(" - 3 "), -3)
        self.assertEqual(parse_signed_int("0"), 0)

    def test_invalid(self):
        for bad in ("", "  ", "1.5", "abc", "--3", "5-", "1e3", "12345678901"):
            self.assertIsNone(parse_signed_int(bad), bad)


if __name__ == "__main__":
    unittest.main()
