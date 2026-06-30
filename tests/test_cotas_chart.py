import unittest

from app_dashboard import _extract_month_number


class CotasChartTests(unittest.TestCase):
    def test_extract_month_number_for_portuguese_month_names(self):
        self.assertEqual(_extract_month_number("Janeiro/2024"), 1)
        self.assertEqual(_extract_month_number("Março/2024"), 3)
        self.assertEqual(_extract_month_number("2026-06-01 00:00:00"), 6)

    def test_extract_month_number_returns_none_for_invalid_values(self):
        self.assertIsNone(_extract_month_number(""))


if __name__ == "__main__":
    unittest.main()
