"""Run from the project folder:   python -m unittest tests.test_calc -v"""
import unittest
from decimal import Decimal

from app.services.calc import (bill_totals, farm_balance, line_amount, parse_money,
                               parse_signed_int, parse_signed_money)


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


class ReturnTests(unittest.TestCase):
    def test_dinesh_returns_5_of_20_chili_at_23(self):
        totals = bill_totals([{"qty": 20, "rate": Decimal("23")}], Decimal("0"),
                             [{"qty": 5, "credit_rate": Decimal("23")}])
        self.assertEqual(totals["subtotal"], Decimal("460.00"))
        self.assertEqual(totals["returns_credit"], Decimal("115.00"))
        self.assertEqual(totals["total"], Decimal("345.00"))

    def test_return_at_a_different_rate_with_discount(self):
        totals = bill_totals([{"qty": 20, "rate": Decimal("25")}], Decimal("10"),
                             [{"qty": 5, "credit_rate": Decimal("20")}])
        self.assertEqual(totals["total"], Decimal("390.00"))   # 500 - 100 - 10

    def test_no_returns_leaves_total_unchanged(self):
        totals = bill_totals([{"qty": 2, "rate": Decimal("15")}], Decimal("0"))
        self.assertEqual(totals["returns_credit"], Decimal("0.00"))
        self.assertEqual(totals["total"], Decimal("30.00"))


class FarmBalanceTests(unittest.TestCase):
    def test_settlement_costs_and_payments(self):
        settled = line_amount(20, Decimal("18"))                  # Tomato 20 at 18 = 360
        balance = farm_balance(settled, Decimal("0"), Decimal("200"), Decimal("100"))
        self.assertEqual(balance, Decimal("60.00"))               # I owe him 60

    def test_advance_makes_the_balance_negative(self):
        balance = farm_balance(Decimal("360"), Decimal("0"), Decimal("200"), Decimal("600"))
        self.assertEqual(balance, Decimal("-440"))                # he owes me 440

    def test_opening_balance_is_added(self):
        self.assertEqual(farm_balance(Decimal("0"), Decimal("1000"), Decimal("0"), Decimal("0")), Decimal("1000"))
        self.assertEqual(farm_balance(Decimal("0"), Decimal("-200"), Decimal("0"), Decimal("0")), Decimal("-200"))

    def test_several_settlement_rates_for_one_row(self):
        total = (line_amount(50, Decimal("18")) + line_amount(30, Decimal("17"))
                 + line_amount(20, Decimal("15")))
        self.assertEqual(total, Decimal("1710.00"))               # 900 + 510 + 300


class SignedMoneyTests(unittest.TestCase):
    def test_valid(self):
        self.assertEqual(parse_signed_money("1000"), (Decimal("1000.00"), None))
        self.assertEqual(parse_signed_money("-200"), (Decimal("-200.00"), None))
        self.assertEqual(parse_signed_money("+50.5"), (Decimal("50.50"), None))

    def test_invalid(self):
        for bad in ("", "0", "abc", "--5", "1.234"):
            value, error = parse_signed_money(bad)
            self.assertIsNone(value, bad)
            self.assertTrue(error, bad)


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
