"""Offline acceptance tests for market_data.indicators (no market or brokerage APIs)."""
import csv
import tempfile
import unittest
from pathlib import Path

from market_data.indicators import (
    analyze_csv, bollinger, ema, load_daily_csv, macd, rsi_wilder, sma
)


class IndicatorTests(unittest.TestCase):
    def test_sma_warmup_and_values(self):
        self.assertEqual(sma([1, 2, 3, 4], 3), [None, None, 2, 3])

    def test_ema_seed(self):
        self.assertEqual(ema([1, 2, 3, 4], 3), [None, None, 2, 3])

    def test_rsi_no_change_neutral(self):
        result = rsi_wilder([100] * 20)
        self.assertEqual(result[14], 50)
        self.assertEqual(result[-1], 50)

    def test_rsi_rising(self):
        self.assertEqual(rsi_wilder(list(range(20)))[-1], 100)

    def test_macd_warmup(self):
        result = macd([float(i) for i in range(1, 41)])
        self.assertIsNone(result["macd"][24])
        self.assertIsNotNone(result["macd"][25])
        self.assertIsNone(result["signal"][32])
        self.assertIsNotNone(result["signal"][33])
        self.assertIsNotNone(result["histogram"][33])

    def test_bollinger_flat(self):
        result = bollinger([10.0] * 21)
        self.assertIsNone(result["middle"][18])
        self.assertEqual(result["middle"][19], 10)
        self.assertEqual(result["upper"][20], 10)
        self.assertEqual(result["lower"][20], 10)


class IngestionTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.path = Path(self.temp.name) / "daily.csv"

    def tearDown(self):
        self.temp.cleanup()

    def write_rows(self, rows):
        with self.path.open("w", newline="", encoding="utf-8") as f:
            writer = csv.DictWriter(f, fieldnames=["date", "open", "high", "low", "close", "volume"])
            writer.writeheader()
            writer.writerows(rows)

    def test_cutoff_prevents_future_bar_use(self):
        self.write_rows([
            dict(date="2026-10-01", open="100", high="110", low="90", close="105", volume="1000"),
            dict(date="2026-10-02", open="105", high="120", low="100", close="115", volume="2000"),
        ])
        rows = load_daily_csv(self.path, as_of="2026-10-01")
        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0]["close"], 105)
        output = analyze_csv(self.path, ticker="9983", as_of="2026-10-01",
                             source="synthetic-test-data",
                             retrieved_at="2026-11-01T10:00:00+09:00")
        self.assertEqual(output["last_bar_date"], "2026-10-01")
        self.assertIsNone(output["indicators"]["sma5"])
        self.assertEqual(output["bars_used"], 1)

    def test_invalid_ohlc_rejected(self):
        self.write_rows([dict(date="2026-10-01", open="100", high="95", low="90",
                              close="105", volume="1000")])
        with self.assertRaisesRegex(ValueError, "High"):
            load_daily_csv(self.path, as_of="2026-10-01")

    def test_unsorted_and_duplicate_dates_rejected(self):
        self.write_rows([
            dict(date="2026-10-02", open="100", high="110", low="90", close="105", volume="1000"),
            dict(date="2026-10-01", open="100", high="110", low="90", close="105", volume="1000"),
        ])
        with self.assertRaisesRegex(ValueError, "strictly increasing"):
            load_daily_csv(self.path, as_of="2026-10-02")

    def test_negative_volume_rejected(self):
        self.write_rows([dict(date="2026-10-01", open="100", high="110", low="90",
                              close="105", volume="-1")])
        with self.assertRaisesRegex(ValueError, "Volume"):
            load_daily_csv(self.path, as_of="2026-10-01")

    def test_timezone_required(self):
        self.write_rows([dict(date="2026-10-01", open="100", high="110", low="90",
                              close="105", volume="1000")])
        with self.assertRaisesRegex(ValueError, "timezone"):
            analyze_csv(self.path, ticker="9983", as_of="2026-10-01",
                        source="synthetic-test-data", retrieved_at="2026-11-01T10:00:00")


if __name__ == "__main__":
    unittest.main()
