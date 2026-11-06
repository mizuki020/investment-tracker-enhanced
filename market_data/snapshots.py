"""Versioned in-memory schemas and pure comparisons; no storage or network API.

Evidence is supplied by the caller, not independently authenticated here.
Selection conservatively requires this exact version to have been observed by
the decision time, even when a provider claims an earlier publication date.
"""
from dataclasses import dataclass, asdict
from datetime import date, datetime
from decimal import Decimal
import hashlib
import json
import re
from zoneinfo import ZoneInfo

from market_data.jquants_v2 import normalize_bars


def timestamp(value: str) -> datetime:
    if type(value) is not str:
        raise ValueError("timestamp must be an immutable string")
    result = datetime.fromisoformat(value)
    if result.tzinfo is None or result.utcoffset() is None:
        raise ValueError("timestamp requires timezone")
    return result


def trade_day(value: str) -> date:
    """Reject aliases before any string-based identity/range comparison."""
    if type(value) is not str or not re.fullmatch(r"[0-9]{4}-[0-9]{2}-[0-9]{2}", value):
        raise ValueError("date requires canonical YYYY-MM-DD")
    return date.fromisoformat(value)


@dataclass(frozen=True)
class TimeEvidence:
    value: str | None = None
    status: str = "unknown"
    evidence: str | None = None

    def __post_init__(self):
        if type(self.status) is not str:
            raise ValueError("evidence status must be a string")
        if self.status not in {"unknown", "unverified", "verified"}:
            raise ValueError("invalid evidence status")
        if self.value is not None:
            timestamp(self.value)
        if self.evidence is not None and (
                type(self.evidence) is not str or not self.evidence.strip()):
            raise ValueError("evidence must be a nonblank immutable string")
        if self.status == "unknown" and self.value is not None:
            raise ValueError("unknown time must remain null")
        if self.status == "verified" and (self.value is None or not self.evidence):
            raise ValueError("verified time requires value and evidence")

    @property
    def is_verified(self):
        self.__post_init__()
        return self.status == "verified"


@dataclass(frozen=True)
class BarVersion:
    provider: str
    code: str
    trade_date: str
    open: str
    high: str
    low: str
    close: str
    volume: int
    adjustment_factor: str
    published_at: TimeEvidence
    available_at: TimeEvidence
    first_observed_at: str
    retrieved_at: str
    price_basis: str = "unadjusted"
    market: str = "TSE"
    currency: str = "JPY"

    def __post_init__(self):
        trade_day(self.trade_date)
        for evidence in (self.published_at, self.available_at):
            if type(evidence) is not TimeEvidence:
                raise ValueError("time evidence must use immutable TimeEvidence")
            evidence.__post_init__()
        if not all(isinstance(v, str) and v.strip() for v in
                   (self.provider, self.code, self.market, self.currency)):
            raise ValueError("source and instrument identity required")
        if self.price_basis not in {"unadjusted", "adjusted"}:
            raise ValueError("invalid price basis")
        if not all(isinstance(v, str) for v in
                   (self.open, self.high, self.low, self.close, self.adjustment_factor)):
            raise ValueError("prices and factor require decimal strings")
        prices = [Decimal(v) for v in (self.open, self.high, self.low, self.close)]
        factor = Decimal(self.adjustment_factor)
        if not all(v.is_finite() and v > 0 for v in prices + [factor]):
            raise ValueError("prices and factor must be positive finite decimals")
        o, h, l, c = prices
        if not l <= min(o, c) <= max(o, c) <= h:
            raise ValueError("invalid OHLC range")
        if type(self.volume) is not int or self.volume < 0:
            raise ValueError("volume must be nonnegative integer")
        # Reuse the existing pure adapter's date/security normalization contract.
        normalize_bars([dict(Date=self.trade_date, Code=self.code,
                             O=self.open, H=self.high, L=self.low, C=self.close,
                             Vo=self.volume)], code=self.code, as_of=self.trade_date)
        observed, retrieved = map(timestamp, (self.first_observed_at, self.retrieved_at))
        if observed.astimezone(ZoneInfo("Asia/Tokyo")).date() < date.fromisoformat(self.trade_date):
            raise ValueError("observation cannot precede trade date")
        if observed > retrieved:
            raise ValueError("first observation cannot follow retrieval")
        for evidence in (self.published_at, self.available_at):
            if evidence.value is not None:
                t = timestamp(evidence.value)
                if t > observed:
                    raise ValueError("publication/availability cannot follow observation")
                if t.astimezone(ZoneInfo("Asia/Tokyo")).date() < date.fromisoformat(self.trade_date):
                    raise ValueError("daily bar cannot precede its trade date")
        if self.published_at.value and self.available_at.value:
            if timestamp(self.published_at.value) > timestamp(self.available_at.value):
                raise ValueError("availability cannot precede publication")

    @property
    def key(self):
        return (self.provider, self.market, self.code, self.currency, "1d",
                self.trade_date, self.price_basis)

    @property
    def content_hash(self):
        # No retrieval/evidence metadata: identical market content is idempotent.
        def canonical(value):
            # Decimal.normalize() rounds to the active context; never use it for identity.
            text = format(Decimal(value), "f")
            return text.rstrip("0").rstrip(".") if "." in text else text
        values = [canonical(v) for v in
                  (self.open, self.high, self.low, self.close, self.adjustment_factor)]
        content = [self.key, values, self.volume]
        return hashlib.sha256(json.dumps(content, separators=(",", ":")).encode()).hexdigest()


@dataclass(frozen=True)
class AcquisitionManifest:
    acquisition_id: str
    provider: str
    code: str
    requested_from: str
    requested_to: str
    retrieved_at: str
    complete: bool
    schema_version: str = "acquisition/1"

    def __post_init__(self):
        if self.schema_version != "acquisition/1":
            raise ValueError("unsupported manifest schema")
        if not all(isinstance(v, str) and v.strip() for v in
                   (self.acquisition_id, self.provider, self.code)):
            raise ValueError("manifest identity required")
        if type(self.complete) is not bool:
            raise ValueError("complete must be boolean")
        if trade_day(self.requested_from) > trade_day(self.requested_to):
            raise ValueError("invalid request range")
        timestamp(self.retrieved_at)


@dataclass(frozen=True)
class Snapshot:
    manifest: AcquisitionManifest
    bars: tuple[BarVersion, ...]
    schema_version: str = "snapshot/1"

    def __post_init__(self):
        if self.schema_version != "snapshot/1" or type(self.bars) is not tuple:
            raise ValueError("unsupported schema or mutable bars")
        for bar in self.bars:
            m = self.manifest
            if (bar.provider, bar.code) != (m.provider, m.code):
                raise ValueError("manifest/bar identity mismatch")
            if not m.requested_from <= bar.trade_date <= m.requested_to:
                raise ValueError("bar outside requested range")
            if timestamp(bar.retrieved_at) > timestamp(m.retrieved_at):
                raise ValueError("bar retrieval follows manifest completion")

    def to_dict(self):
        """Return a detached JSON-compatible value, without persisting anything."""
        return asdict(self)


def compare_snapshots(previous: Snapshot, current: Snapshot) -> dict:
    """Compare only identical acquisition scopes; never interpret missing as deletion."""
    a, b = previous.manifest, current.manifest
    if (a.provider, a.code, a.requested_from, a.requested_to) != (
            b.provider, b.code, b.requested_from, b.requested_to):
        raise ValueError("incomparable acquisition scopes")
    def group(snapshot):
        result = {}
        for bar in snapshot.bars:
            result.setdefault(bar.key, []).append(bar)
        return result
    old, new = group(previous), group(current)
    duplicates = sorted(k for k in old.keys() | new.keys()
                        if len(old.get(k, [])) > 1 or len(new.get(k, [])) > 1)
    common = (old.keys() & new.keys()) - set(duplicates)
    publishable = a.complete and b.complete and not duplicates
    return {
        "unchanged": sorted(k for k in common if old[k][0].content_hash == new[k][0].content_hash) if publishable else [],
        "revised": sorted(k for k in common if old[k][0].content_hash != new[k][0].content_hash) if publishable else [],
        "added": sorted(new.keys() - old.keys()) if publishable else [],
        "missing": sorted(old.keys() - new.keys()),
        "duplicates": duplicates,
        "complete": bool(publishable),
    }


@dataclass(frozen=True)
class Selection:
    bars: tuple[BarVersion, ...]
    excluded: tuple[tuple[str, str], ...]
    verified_backtest_eligible: bool


def select_as_of(versions: tuple[BarVersion, ...], *, decision_at: str,
                 mode: str) -> Selection:
    """Select latest observed version per key; never fall back past an unverified revision.

    Research may use unknown publication/availability, but not future observations.
    Eligibility covers temporal evidence only, not calendar/freshness/licensing gates.
    """
    if mode not in {"historical_research", "verified_backtest"}:
        raise ValueError("invalid selection mode")
    decision = timestamp(decision_at)
    candidates, excluded = {}, []
    for bar in versions:
        if date.fromisoformat(bar.trade_date) > decision.astimezone(ZoneInfo("Asia/Tokyo")).date():
            excluded.append((bar.content_hash, "future_trade_date"))
            continue
        if timestamp(bar.first_observed_at) > decision:
            excluded.append((bar.content_hash, "future_version"))
            continue
        candidates.setdefault(bar.key, []).append(bar)
    selected = []
    for key in sorted(candidates):
        group = candidates[key]
        latest_time = max(timestamp(b.first_observed_at) for b in group)
        latest = [b for b in group if timestamp(b.first_observed_at) == latest_time]
        def version_identity(b):
            def evidence_identity(e):
                return (timestamp(e.value) if e.value is not None else None,
                        e.status, e.evidence)
            return (b.content_hash, timestamp(b.first_observed_at),
                    evidence_identity(b.published_at), evidence_identity(b.available_at))
        if any(version_identity(b) != version_identity(latest[0]) for b in latest[1:]):
            raise ValueError("ambiguous versions at same observation time")
        # Reacquisition is an event, not a new version. Choose deterministically
        # without changing any input record or inventing an earlier observation.
        bar = min(latest, key=lambda b: (timestamp(b.retrieved_at), b.retrieved_at,
                                        json.dumps(asdict(b), sort_keys=True)))
        verified = all(e.is_verified for e in (bar.published_at, bar.available_at))
        if mode == "verified_backtest" and not verified:
            excluded.append((bar.content_hash, "historical_availability_unverified"))
        else:
            selected.append(bar)
    bases = {}
    for bar in selected:
        instrument = (bar.provider, bar.market, bar.code, bar.currency)
        bases.setdefault(instrument, set()).add(bar.price_basis)
    if any(len(values) > 1 for values in bases.values()):
        raise ValueError("mixed price bases for one instrument")
    eligible = mode == "verified_backtest" and bool(selected) and not excluded and all(
        e.is_verified for b in selected for e in (b.published_at, b.available_at))
    return Selection(tuple(selected), tuple(excluded), eligible)
