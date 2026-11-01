"""Validated daily OHLCV ingestion and deterministic technical indicators.

No network access, no brokerage orders, no guessed market prices.
Input CSV columns: date,open,high,low,close,volume (ISO dates, unadjusted units).
"""
from __future__ import annotations

import csv
import json
import math
from datetime import date, datetime
from pathlib import Path
from statistics import pstdev
from typing import Optional


def load_daily_csv(path: str | Path, *, as_of: str) -> list[dict]:
    """Read and validate OHLCV; include only bars on/before as_of (JST trading date)."""
    cutoff = date.fromisoformat(as_of)
    result: list[dict] = []
    last_date: Optional[date] = None
    with open(path, newline="", encoding="utf-8-sig") as f:
        reader = csv.DictReader(f)
        required = {"date", "open", "high", "low", "close", "volume"}
        if not reader.fieldnames or not required.issubset(reader.fieldnames):
            raise ValueError(f"CSV requires columns: {', '.join(sorted(required))}")
        for line, raw in enumerate(reader, start=2):
            try:
                day = date.fromisoformat(raw["date"])
                values = {k: float(raw[k]) for k in ("open", "high", "low", "close")}
                volume_raw = raw["volume"]
                volume = int(volume_raw)
                if str(volume) != volume_raw.strip():
                    raise ValueError("volume must be a nonnegative integer")
            except (TypeError, ValueError, OverflowError) as e:
                raise ValueError(f"Invalid OHLCV at CSV line {line}: {e}") from e
            if last_date is not None and day <= last_date:
                raise ValueError(f"Dates must be strictly increasing; line {line}")
            last_date = day
            if not all(math.isfinite(v) and v > 0 for v in values.values()):
                raise ValueError(f"Prices must be positive and finite; line {line}")
            if volume < 0:
                raise ValueError(f"Volume cannot be negative; line {line}")
            if values["high"] < max(values["open"], values["close"], values["low"]):
                raise ValueError(f"High below another OHLC price; line {line}")
            if values["low"] > min(values["open"], values["close"], values["high"]):
                raise ValueError(f"Low above another OHLC price; line {line}")
            if day <= cutoff:
                result.append({"date": day.isoformat(), **values, "volume": volume})
    if not result:
        raise ValueError("No validated bars at or before as_of")
    return result


def sma(values: list[float], period: int) -> list[Optional[float]]:
    if period < 1:
        raise ValueError("period must be positive")
    out: list[Optional[float]] = [None] * len(values)
    running = 0.0
    for i, v in enumerate(values):
        running += v
        if i >= period:
            running -= values[i - period]
        if i >= period - 1:
            out[i] = running / period
    return out


def ema(values: list[float], period: int) -> list[Optional[float]]:
    """EMA seeded with the SMA of the first period, not the first close."""
    if period < 1:
        raise ValueError("period must be positive")
    out: list[Optional[float]] = [None] * len(values)
    if len(values) < period:
        return out
    seed = sum(values[:period]) / period
    out[period - 1] = seed
    alpha = 2 / (period + 1)
    prev = seed
    for i in range(period, len(values)):
        prev = alpha * values[i] + (1 - alpha) * prev
        out[i] = prev
    return out


def rsi_wilder(closes: list[float], period: int = 14) -> list[Optional[float]]:
    if period < 1:
        raise ValueError("period must be positive")
    out: list[Optional[float]] = [None] * len(closes)
    if len(closes) <= period:
        return out
    changes = [closes[i] - closes[i - 1] for i in range(1, len(closes))]
    gains = [max(x, 0) for x in changes]
    losses = [max(-x, 0) for x in changes]
    avg_gain = sum(gains[:period]) / period
    avg_loss = sum(losses[:period]) / period

    def score(gain: float, loss: float) -> float:
        if loss == 0:
            return 100.0 if gain > 0 else 50.0
        return 100 - 100 / (1 + gain / loss)

    out[period] = score(avg_gain, avg_loss)
    for i in range(period + 1, len(closes)):
        avg_gain = (avg_gain * (period - 1) + gains[i - 1]) / period
        avg_loss = (avg_loss * (period - 1) + losses[i - 1]) / period
        out[i] = score(avg_gain, avg_loss)
    return out


def macd(closes: list[float]) -> dict[str, list[Optional[float]]]:
    fast = ema(closes, 12)
    slow = ema(closes, 26)
    line: list[Optional[float]] = [
        a - b if a is not None and b is not None else None
        for a, b in zip(fast, slow)
    ]
    valid = [v for v in line if v is not None]
    signal_valid = ema(valid, 9)
    signal = [None] * (len(line) - len(valid)) + signal_valid
    histogram = [
        a - b if a is not None and b is not None else None
        for a, b in zip(line, signal)
    ]
    return {"macd": line, "signal": signal, "histogram": histogram}


def bollinger(closes: list[float], period: int = 20, deviations: float = 2.0) -> dict:
    middle = sma(closes, period)
    upper: list[Optional[float]] = [None] * len(closes)
    lower: list[Optional[float]] = [None] * len(closes)
    for i in range(period - 1, len(closes)):
        std = pstdev(closes[i - period + 1:i + 1])
        upper[i] = middle[i] + deviations * std
        lower[i] = middle[i] - deviations * std
    return {"middle": middle, "upper": upper, "lower": lower}


def analyze_csv(path: str | Path, *, ticker: str, as_of: str,
                source: str, retrieved_at: str, price_basis: str = "unadjusted") -> dict:
    if not ticker.strip() or not source.strip():
        raise ValueError("ticker and source must be nonempty")
    if price_basis not in ("adjusted", "unadjusted"):
        raise ValueError("price_basis must be adjusted or unadjusted")
    retrieved = datetime.fromisoformat(retrieved_at)
    if retrieved.tzinfo is None or retrieved.utcoffset() is None:
        raise ValueError("retrieved_at must include a timezone offset")
    rows = load_daily_csv(path, as_of=as_of)
    closes = [r["close"] for r in rows]
    bb = bollinger(closes)
    m = macd(closes)
    ma5, ma25, ma75 = (sma(closes, p) for p in (5, 25, 75))
    rsi = rsi_wilder(closes)
    idx = len(rows) - 1
    return {
        "ticker": ticker, "timeframe": "1d", "market_timezone": "Asia/Tokyo",
        "as_of": as_of, "last_bar_date": rows[-1]["date"],
        "source": source, "retrieved_at": retrieved_at, "price_basis": price_basis,
        "bars_used": len(rows), "last_ohlcv": rows[-1],
        "indicators": {
            "sma5": ma5[idx], "sma25": ma25[idx], "sma75": ma75[idx],
            "rsi14_wilder": rsi[idx],
            "macd_12_26_9": {k: v[idx] for k, v in m.items()},
            "bollinger_20_2": {k: v[idx] for k, v in bb.items()},
        },
        "warnings": [
            "Historical as-of filters bars only. Source publication/availability times "
            "must be verified separately before point-in-time backtesting.",
            "Corporate-action adjustment and vendor calculation conventions must be checked.",
        ],
    }


if __name__ == "__main__":
    import argparse
    p = argparse.ArgumentParser(description="Analyze validated daily OHLCV CSV (no network or orders)")
    p.add_argument("--csv", required=True)
    p.add_argument("--ticker", required=True)
    p.add_argument("--as-of", required=True, help="YYYY-MM-DD (JST market date)")
    p.add_argument("--source", required=True)
    p.add_argument("--retrieved-at", required=True, help="ISO-8601 with timezone")
    p.add_argument("--price-basis", choices=["adjusted", "unadjusted"], default="unadjusted")
    args = p.parse_args()
    print(json.dumps(analyze_csv(args.csv, ticker=args.ticker, as_of=args.as_of,
                                  source=args.source, retrieved_at=args.retrieved_at,
                                  price_basis=args.price_basis), ensure_ascii=False, indent=2))
