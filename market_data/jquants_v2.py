"""J-Quants API V2 daily OHLCV adapter; no brokerage integration.

API key is read only from JQUANTS_API_KEY environment variable.
No key, raw HTTP headers, or authenticated URL is persisted.
"""
from __future__ import annotations

import argparse
import csv
import io
import json
import os
import re
import time
import urllib.error
import urllib.parse
import urllib.request
from datetime import date, datetime, timezone
from pathlib import Path
from typing import Callable

from market_data.indicators import analyze_csv, load_daily_csv

ENDPOINT = "https://api.jquants.com/v2/equities/bars/daily"


class MarketDataError(Exception):
    """Non-secret provider, validation or data-availability error."""


def normalize_bars(payloads: list[dict], *, code: str, as_of: str) -> list[dict]:
    """Convert J-Quants V2 unadjusted OHLCV to validated, sorted daily bars.

    Suspended/untraded rows (null OHLCV) are omitted; no invented zero-price bars.
    """
    cutoff = date.fromisoformat(as_of)
    normalized: list[dict] = []
    seen: set[str] = set()
    for raw in payloads:
        if not isinstance(raw, dict):
            raise MarketDataError("Provider returned a non-object bar")
        day = raw.get("Date")
        try:
            parsed = date.fromisoformat(day)
        except (TypeError, ValueError) as e:
            raise MarketDataError("Provider returned invalid bar date") from e
        if str(raw.get("Code")) not in {code, code + "0"}:
            raise MarketDataError("Provider returned an unexpected security code")
        if parsed > cutoff:
            continue
        if day in seen:
            raise MarketDataError("Provider returned duplicate dates")
        seen.add(day)
        fields = ("O", "H", "L", "C", "Vo")
        if any(raw.get(key) is None for key in fields):
            continue
        try:
            volume_float = float(raw["Vo"])
            if not volume_float.is_integer() or volume_float < 0:
                raise ValueError("invalid volume")
            values = [float(raw[key]) for key in fields[:4]]
            volume = int(volume_float)
        except (ValueError, TypeError, OverflowError) as e:
            raise MarketDataError("Provider returned invalid OHLCV values") from e
        normalized.append(dict(zip(("date", "open", "high", "low", "close", "volume"),
                                   (day, *values, volume))))
    normalized.sort(key=lambda row: row["date"])
    return normalized


def _request_page(*, code: str, start: str, end: str, api_key: str,
                  pagination_key: str | None, opener: Callable,
                  sleep: Callable, max_retries: int = 2) -> dict:
    params = {"code": code, "from": start, "to": end}
    if pagination_key:
        params["pagination_key"] = pagination_key
    url = ENDPOINT + "?" + urllib.parse.urlencode(params)
    request = urllib.request.Request(
        url, headers={"x-api-key": api_key, "Accept": "application/json"},
        method="GET")
    for attempt in range(max_retries + 1):
        try:
            with opener(request, timeout=20) as response:
                body = response.read()
            parsed = json.loads(body)
            if not isinstance(parsed, dict) or not isinstance(parsed.get("data"), list):
                raise MarketDataError("Unexpected provider response format")
            return parsed
        except urllib.error.HTTPError as e:
            if e.code in (429, 500, 502, 503, 504) and attempt < max_retries:
                sleep(min(2 ** attempt, 4))
                continue
            # Do not echo response body or authentication headers.
            raise MarketDataError(f"J-Quants request failed (HTTP {e.code})") from None
        except (urllib.error.URLError, TimeoutError) as e:
            if attempt < max_retries:
                sleep(min(2 ** attempt, 4))
                continue
            raise MarketDataError("J-Quants network request failed") from None
        except (UnicodeDecodeError, json.JSONDecodeError):
            raise MarketDataError("J-Quants returned invalid JSON") from None
    raise MarketDataError("J-Quants retry limit reached")


def fetch_daily(*, code: str, start: str, end: str, as_of: str,
                api_key: str, opener: Callable = urllib.request.urlopen,
                sleep: Callable = time.sleep) -> tuple[list[dict], dict]:
    """Fetch all pages; stop if pagination loops; refuse future query dates."""
    if not re.fullmatch(r"[0-9A-Z]{4,5}", code):
        raise ValueError("code must be a 4- or 5-character J-Quants security code")
    start_day, end_day, cutoff = map(date.fromisoformat, (start, end, as_of))
    if start_day > end_day or end_day > cutoff:
        raise ValueError("Require start <= end <= as_of")
    if not api_key.strip():
        raise ValueError("JQUANTS_API_KEY is required")
    all_rows: list[dict] = []
    cursor: str | None = None
    cursors: set[str] = set()
    pages = 0
    while True:
        payload = _request_page(code=code, start=start, end=end,
                                api_key=api_key, pagination_key=cursor,
                                opener=opener, sleep=sleep)
        pages += 1
        all_rows.extend(payload["data"])
        next_cursor = payload.get("pagination_key")
        if not next_cursor:
            break
        if not isinstance(next_cursor, str) or next_cursor in cursors:
            raise MarketDataError("Invalid or repeated pagination key")
        cursors.add(next_cursor)
        cursor = next_cursor
        if pages >= 1000:
            raise MarketDataError("Pagination limit reached")
    bars = normalize_bars(all_rows, code=code, as_of=as_of)
    if not bars:
        raise MarketDataError("No tradable OHLCV bars in requested period")
    return bars, {"provider": "J-Quants API V2", "endpoint": ENDPOINT,
                  "code": code, "from": start, "to": end, "as_of": as_of,
                  "retrieved_at": datetime.now(timezone.utc).isoformat(),
                  "price_basis": "unadjusted", "pages": pages,
                  "returned_records": len(all_rows),
                  "tradable_bars": len(bars),
                  "limitations": [
                      "Source publication/availability timestamps are not supplied per bar.",
                      "Historical point-in-time integrity requires original snapshots.",
                      "The user's subscription may provide delayed prices.",
                  ]}


def save_snapshot(path: str | Path, *, bars: list[dict], metadata: dict) -> None:
    """Create-only snapshot: never silently overwrite historical evidence."""
    target = Path(path)
    target.parent.mkdir(parents=True, exist_ok=True)
    with target.open("x", encoding="utf-8") as f:
        json.dump({"metadata": metadata, "bars": bars}, f,
                  ensure_ascii=False, indent=2)
        f.write("\n")


def analyze_bars(bars: list[dict], *, code: str, as_of: str,
                 retrieved_at: str) -> dict:
    """Reuse validated CSV indicator engine without persistent temporary files."""
    import tempfile
    with tempfile.TemporaryDirectory() as directory:
        path = Path(directory) / "ohlcv.csv"
        with path.open("w", newline="", encoding="utf-8") as f:
            writer = csv.DictWriter(f, fieldnames=["date", "open", "high", "low", "close", "volume"])
            writer.writeheader()
            writer.writerows(bars)
        return analyze_csv(path, ticker=code, as_of=as_of,
                           source="J-Quants API V2 /equities/bars/daily",
                           retrieved_at=retrieved_at, price_basis="unadjusted")


def main() -> None:
    parser = argparse.ArgumentParser(description="Fetch Japanese daily prices; no orders")
    parser.add_argument("--code", default="9983")
    parser.add_argument("--from-date", required=True)
    parser.add_argument("--to-date", required=True)
    parser.add_argument("--as-of", required=True)
    parser.add_argument("--snapshot", required=True, help="New local JSON file, never overwritten")
    parser.add_argument("--analysis-output", help="New local indicator JSON file")
    args = parser.parse_args()
    api_key = os.environ.get("JQUANTS_API_KEY", "")
    bars, meta = fetch_daily(code=args.code, start=args.from_date,
                             end=args.to_date, as_of=args.as_of, api_key=api_key)
    save_snapshot(args.snapshot, bars=bars, metadata=meta)
    if args.analysis_output:
        output = analyze_bars(bars, code=args.code, as_of=args.as_of,
                              retrieved_at=meta["retrieved_at"])
        with Path(args.analysis_output).open("x", encoding="utf-8") as f:
            json.dump(output, f, ensure_ascii=False, indent=2)
            f.write("\n")
    print(json.dumps({"snapshot": args.snapshot,
                      "analysis_output": args.analysis_output,
                      "last_bar_date": bars[-1]["date"],
                      "bars": len(bars),
                      "retrieved_at": meta["retrieved_at"]},
                     ensure_ascii=False))


if __name__ == "__main__":
    main()
