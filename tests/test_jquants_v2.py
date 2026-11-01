"""J-Quants adapter tests with fake HTTP responses: never use an API key or network."""
import json
import tempfile
import unittest
from pathlib import Path
from urllib.error import HTTPError

from market_data.jquants_v2 import (
    MarketDataError, analyze_bars, fetch_daily, normalize_bars, save_snapshot,
)


def bar(day, close=100, code="99830"):
    return {"Date": day, "Code": code, "O": close - 1, "H": close + 1,
            "L": close - 2, "C": close, "Vo": 1000.0}


class FakeResponse:
    def __init__(self, data):
        self.data = json.dumps(data).encode("utf-8")

    def __enter__(self):
        return self

    def __exit__(self, *args):
        return False

    def read(self):
        return self.data


class AdapterTests(unittest.TestCase):
    def test_pagination_and_key_header_not_in_snapshot(self):
        urls = []
        def opener(request, timeout):
            self.assertEqual(request.get_header("X-api-key"), "secret-for-test")
            urls.append(request.full_url)
            if len(urls) == 1:
                return FakeResponse({"data": [bar("2026-10-01")], "pagination_key": "next"})
            return FakeResponse({"data": [bar("2026-10-02", 110)]})
        bars, metadata = fetch_daily(
            code="9983", start="2026-10-01", end="2026-10-02",
            as_of="2026-10-02", api_key="secret-for-test",
            opener=opener, sleep=lambda _: None)
        self.assertEqual(len(bars), 2)
        self.assertEqual(metadata["pages"], 2)
        self.assertIn("pagination_key=next", urls[1])
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "snapshot.json"
            save_snapshot(path, bars=bars, metadata=metadata)
            self.assertNotIn("secret-for-test", path.read_text())
            with self.assertRaises(FileExistsError):
                save_snapshot(path, bars=bars, metadata=metadata)

    def test_future_query_refused_without_network(self):
        def no_network(*args, **kwargs):
            self.fail("No HTTP call should be made")
        with self.assertRaisesRegex(ValueError, "start <= end <= as_of"):
            fetch_daily(code="9983", start="2026-10-01", end="2026-10-02",
                        as_of="2026-10-01", api_key="test", opener=no_network)

    def test_null_suspension_and_future_rows_excluded(self):
        halted = bar("2026-10-02")
        halted["C"] = None
        bars = normalize_bars([bar("2026-10-01"), halted,
                               bar("2026-10-03")], code="9983",
                              as_of="2026-10-02")
        self.assertEqual([r["date"] for r in bars], ["2026-10-01"])

    def test_unexpected_code_rejected(self):
        with self.assertRaisesRegex(MarketDataError, "unexpected security"):
            normalize_bars([bar("2026-10-01", code="72030")],
                           code="9983", as_of="2026-10-01")

    def test_repeated_cursor_rejected(self):
        def opener(request, timeout):
            return FakeResponse({"data": [bar("2026-10-01")],
                                 "pagination_key": "loop"})
        with self.assertRaisesRegex(MarketDataError, "pagination"):
            fetch_daily(code="9983", start="2026-10-01", end="2026-10-01",
                        as_of="2026-10-01", api_key="test", opener=opener,
                        sleep=lambda _: None)

    def test_http_auth_error_is_sanitized(self):
        def opener(request, timeout):
            raise HTTPError(request.full_url, 403, "secret-for-test", {}, None)
        with self.assertRaises(MarketDataError) as ctx:
            fetch_daily(code="9983", start="2026-10-01", end="2026-10-01",
                        as_of="2026-10-01", api_key="secret-for-test",
                        opener=opener, sleep=lambda _: None)
        self.assertNotIn("secret-for-test", str(ctx.exception))
        self.assertIn("403", str(ctx.exception))

    def test_integration_to_indicators(self):
        bars = [dict(date=f"2026-09-{i:02d}", open=100.0, high=102.0,
                     low=98.0, close=100.0, volume=1000)
                for i in range(1, 21)]
        output = analyze_bars(bars, code="9983", as_of="2026-09-20",
                              retrieved_at="2026-11-01T10:00:00+09:00")
        self.assertEqual(output["indicators"]["sma5"], 100)
        self.assertEqual(output["last_bar_date"], "2026-09-20")
        self.assertIsNone(output["indicators"]["sma25"])


if __name__ == "__main__":
    unittest.main()
