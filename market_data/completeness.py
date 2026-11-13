"""Synthetic-first raw completeness diagnostics. No evidence authenticator or I/O."""
from collections import Counter
from dataclasses import dataclass
from datetime import timedelta
from decimal import Decimal
from enum import Enum

from market_data.snapshots import trade_day, timestamp
from market_data.quality_gates import Check, CheckResult, GateDecision, Status, Purpose, POLICY_VERSION

MAX_ROWS = 4096
MAX_PAGES = 64
MAX_CALENDAR_DAYS = 4096
MAX_RANGE_DAYS = 3660  # inclusive
MAX_PRICE_CHARS = 64
MAX_REFERENCE_CHARS = 256
MAX_FINDINGS = 8 * MAX_ROWS + 4 * MAX_CALENDAR_DAYS + 64


class _LimitExceeded(ValueError):
    def __init__(self, code):
        self.code = code
        super().__init__(code)


def _bound(count, limit, code):
    if count > limit:
        raise _LimitExceeded(code)


def _tuple_bound(values, limit, code):
    if type(values) is not tuple:
        raise ValueError("immutable tuple required; iterators are not consumed")
    _bound(len(values), limit, code)


def _day(value):
    if type(value) is not str:
        raise ValueError("date string required")
    _bound(len(value), 10, "date_length_limit")
    return trade_day(value)


def _text(value):
    if type(value) is not str:
        raise ValueError("immutable string required")
    _bound(len(value), MAX_REFERENCE_CHARS, "text_length_limit")
    if not value.strip():
        raise ValueError("nonblank immutable string required")


def _reference(value):
    if value is not None:
        if type(value) is str:
            _bound(len(value), MAX_REFERENCE_CHARS, "reference_length_limit")
        _text(value)


@dataclass(frozen=True)
class RawBar:
    code: str
    day: str
    open: str | None
    high: str | None
    low: str | None
    close: str | None
    volume: int | None

    def __post_init__(self):
        _text(self.code)
        _day(self.day)
        for value in (self.open, self.high, self.low, self.close):
            if value is not None and type(value) is not str:
                raise ValueError("raw prices require decimal strings or null")
            if value is not None:
                _bound(len(value), MAX_PRICE_CHARS, "price_length_limit")
        if self.volume is not None and type(self.volume) is not int:
            raise ValueError("raw volume requires integer or null")
        if self.volume is not None and self.volume.bit_length() > 64:
            raise _LimitExceeded("volume_size_limit")


class MarketState(Enum):
    NORMAL = "normal"
    FULL_HALT = "full_halt"
    PARTIAL_HALT = "partial_halt"
    NO_TRADES = "no_trades"
    UNKNOWN = "unknown"


@dataclass(frozen=True)
class CalendarDay:
    day: str
    session: bool
    state: MarketState
    evidence_id: str | None = None
    code: str | None = None

    def __post_init__(self):
        _day(self.day)
        if type(self.session) is not bool or type(self.state) is not MarketState:
            raise ValueError("invalid calendar claim")
        _reference(self.evidence_id)
        _reference(self.code)


@dataclass(frozen=True)
class DateRangeClaim:
    start: str
    end: str
    evidence_id: str | None = None

    def __post_init__(self):
        if _day(self.start) > _day(self.end):
            raise ValueError("invalid date range")
        _reference(self.evidence_id)


@dataclass(frozen=True)
class Page:
    rows: tuple[RawBar, ...]
    requested_cursor: str | None = None
    next_cursor: str | None = None

    def __post_init__(self):
        _tuple_bound(self.rows, MAX_ROWS, "row_count_limit")
        if type(self.rows) is not tuple or any(type(r) is not RawBar for r in self.rows):
            raise ValueError("rows must be immutable raw bars")
        for row in self.rows:
            row.__post_init__()
        _reference(self.requested_cursor)
        _reference(self.next_cursor)


@dataclass(frozen=True)
class DateComparison:
    missing: tuple[str, ...]
    unexpected: tuple[str, ...]
    duplicates: tuple[str, ...]

    def __post_init__(self):
        for values in (self.missing, self.unexpected, self.duplicates):
            _tuple_bound(values, MAX_CALENDAR_DAYS, "date_count_limit")
            for value in values:
                _day(value)
            if type(values) is not tuple or values != tuple(sorted(set(values))):
                raise ValueError("comparison dates must be canonical immutable sets")
            for value in values:
                _day(value)

    @property
    def matches(self):
        """Arithmetic comparison only; not a trust/quality/operational PASS."""
        return not (self.missing or self.unexpected or self.duplicates)


def compare_dates(expected: tuple[str, ...], observed: tuple[str, ...]) -> DateComparison:
    """Pure comparison under caller-supplied assumptions, without authenticating them."""
    for values in (expected, observed):
        _tuple_bound(values, MAX_ROWS, "date_count_limit")
        if type(values) is not tuple:
            raise ValueError("dates must be immutable tuples")
        for value in values:
            _day(value)
    if len(set(expected)) != len(expected):
        raise ValueError("duplicate expected calendar dates")
    return DateComparison(tuple(sorted(set(expected) - set(observed))),
                          tuple(sorted(set(observed) - set(expected))),
                          tuple(sorted(d for d, n in Counter(observed).items() if n > 1)))


@dataclass(frozen=True)
class Finding:
    check: Check
    status: Status
    reason: str
    dates: tuple[str, ...] = ()

    def __post_init__(self):
        if (type(self.check) is not Check or type(self.status) is not Status
                or self.status not in (Status.BLOCK, Status.UNVERIFIED)):
            raise ValueError("findings cannot authenticate PASS")
        _text(self.reason)
        _tuple_bound(self.dates, MAX_CALENDAR_DAYS, "date_count_limit")
        for day in self.dates:
            _day(day)


@dataclass(frozen=True)
class Inspection:
    checks: tuple[CheckResult, ...]
    findings: tuple[Finding, ...]

    def __post_init__(self):
        _tuple_bound(self.checks, 4, "check_count_limit")
        _tuple_bound(self.findings, MAX_FINDINGS, "finding_count_limit")
        if type(self.checks) is not tuple or type(self.findings) is not tuple:
            raise ValueError("inspection requires immutable collections")
        required = {Check.SCHEMA, Check.COMPLETENESS, Check.CALENDAR, Check.MARKET_STATE}
        if len(self.checks) != 4 or {r.check for r in self.checks} != required:
            raise ValueError("inspection requires four distinct checks")
        context = None
        for r in self.checks:
            if type(r) is not CheckResult:
                raise ValueError("invalid check")
            _tuple_bound(r.evidence_ids, MAX_CALENDAR_DAYS + 4, "evidence_count_limit")
            for reference in r.evidence_ids:
                _reference(reference)
            for value in (r.reason_code, r.target, r.evaluated_at, r.policy_version):
                _text(value)
            r.__post_init__()
            if r.status is Status.PASS or r.policy_version != POLICY_VERSION:
                raise ValueError("inspection cannot authenticate PASS")
            current = (r.target, r.purpose, timestamp(r.evaluated_at))
            if context is not None and current != context:
                raise ValueError("mixed inspection context")
            context = current
        for finding in self.findings:
            if type(finding) is not Finding:
                raise ValueError("invalid finding")
            finding.__post_init__()
            if finding.check not in required:
                raise ValueError("unsupported inspection finding")
        for r in self.checks:
            relevant = [f for f in self.findings if f.check is r.check]
            if not relevant:
                raise ValueError("check requires diagnostic findings")
            status = Status.BLOCK if any(f.status is Status.BLOCK for f in relevant) else Status.UNVERIFIED
            if r.status is not status or r.reason_code != sorted(
                    f.reason for f in relevant if f.status is status)[0]:
                raise ValueError("check disagrees with findings")

    @property
    def analysis_input_allowed(self):
        return False

    @property
    def verified_performance_allowed(self):
        return False

    @property
    def orders_allowed(self):
        return False


def inspect_completeness(*, code: str, requested: DateRangeClaim,
                         acquired: DateRangeClaim, pages: tuple[Page, ...],
                         pages_complete: bool, calendar: tuple[CalendarDay, ...],
                         listing: DateRangeClaim | None,
                         entitlement: DateRangeClaim | None,
                         purpose: Purpose, target: str, evaluated_at: str) -> Inspection | GateDecision:
    """Inspect raw values; calendar/listing/halt/entitlement claims remain unverified.

    Overlong evaluation time returns a contextual diagnostic BLOCK without parsing.
    Other invalid context raises ValueError (never PASS). Invalid data or evaluation
    exceptions return BLOCK findings without leaking exception contents.
    """
    _text(target)
    if type(purpose) is not Purpose:
        raise ValueError("unknown purpose")
    if type(evaluated_at) is not str or not evaluated_at:
        raise ValueError("evaluation time requires a nonempty immutable string")
    if len(evaluated_at) > MAX_REFERENCE_CHARS:
        return GateDecision(Status.BLOCK, ("invalid_evaluation_time",), (),
                            target, None, purpose)
    timestamp(evaluated_at)
    findings = []
    evidence = set()
    def add(check, status, reason, dates=()):
        findings.append(Finding(check, status, reason, tuple(sorted(dates))))
    try:
        _text(code)
        for claim in (requested, acquired, listing, entitlement):
            if claim is not None:
                if type(claim) is not DateRangeClaim:
                    raise ValueError("invalid range claim")
                claim.__post_init__()
                if claim.evidence_id:
                    evidence.add(claim.evidence_id)
        if requested is None or acquired is None:
            raise ValueError("requested and acquired ranges required")
        current, end = _day(requested.start), _day(requested.end)
        _bound((end - current).days + 1, MAX_RANGE_DAYS, "range_day_limit")
        # Check collection sizes and summed row counts before validating rows,
        # flattening, sorting, date expansion or Decimal conversion.
        _tuple_bound(pages, MAX_PAGES, "page_count_limit")
        _tuple_bound(calendar, MAX_CALENDAR_DAYS, "calendar_count_limit")
        total_rows = 0
        for page in pages:
            if type(page) is not Page:
                raise ValueError("invalid page")
            _tuple_bound(page.rows, MAX_ROWS, "row_count_limit")
            total_rows += len(page.rows)
            _bound(total_rows, MAX_ROWS, "row_count_limit")
        for day in calendar:
            if type(day) is not CalendarDay:
                raise ValueError("invalid calendar")
            day.__post_init__()
        for page in pages:
            page.__post_init__()
        if type(pages) is not tuple or type(calendar) is not tuple or type(pages_complete) is not bool:
            raise ValueError("immutable collections and boolean completion required")
        if (requested.start, requested.end) != (acquired.start, acquired.end):
            add(Check.COMPLETENESS, Status.BLOCK, "acquired_scope_mismatch")
        if entitlement is None:
            add(Check.COMPLETENESS, Status.UNVERIFIED, "entitlement_unknown")
        elif entitlement.start > requested.start or entitlement.end < requested.end:
            add(Check.COMPLETENESS, Status.BLOCK, "claimed_entitlement_excludes_request")
        add(Check.COMPLETENESS, Status.UNVERIFIED, "entitlement_authentication_not_implemented")
        if listing is None:
            add(Check.MARKET_STATE, Status.UNVERIFIED, "listing_unknown")
        add(Check.MARKET_STATE, Status.UNVERIFIED, "market_evidence_authentication_not_implemented")
        expected_cursor = None
        seen_cursors = set()
        rows = []
        if not pages or not pages_complete:
            add(Check.COMPLETENESS, Status.BLOCK, "pages_incomplete")
        for i, page in enumerate(pages):
            if type(page) is not Page:
                raise ValueError("invalid page")
            page.__post_init__()
            if page.requested_cursor != expected_cursor or (i > 0 and expected_cursor is None):
                add(Check.COMPLETENESS, Status.BLOCK, "page_chain_invalid")
            if page.next_cursor is not None:
                if page.next_cursor in seen_cursors:
                    add(Check.COMPLETENESS, Status.BLOCK, "page_cursor_cycle")
                seen_cursors.add(page.next_cursor)
            expected_cursor = page.next_cursor
            rows.extend(page.rows)
        if expected_cursor is not None:
            add(Check.COMPLETENESS, Status.BLOCK, "pages_incomplete")
        observed = []
        for row in rows:
            observed.append(row.day)
            if row.code != code:
                add(Check.SCHEMA, Status.BLOCK, "wrong_security", (row.day,))
            if not requested.start <= row.day <= requested.end:
                add(Check.COMPLETENESS, Status.BLOCK, "row_outside_request", (row.day,))
            values = (row.open, row.high, row.low, row.close, row.volume)
            if any(value is None for value in values):
                add(Check.SCHEMA, Status.BLOCK, "raw_null_ohlcv", (row.day,))
                continue
            try:
                o, h, l, c = map(Decimal, values[:4])
                valid = (all(v.is_finite() and v > 0 for v in (o, h, l, c))
                         and l <= min(o, c) <= max(o, c) <= h and row.volume >= 0)
            except Exception:
                valid = False
            if not valid:
                add(Check.SCHEMA, Status.BLOCK, "invalid_ohlcv", (row.day,))
        duplicates = tuple(d for d, n in Counter(observed).items() if n > 1)
        if duplicates:
            add(Check.COMPLETENESS, Status.BLOCK, "duplicate_dates", duplicates)
        if any(a >= b for a, b in zip(observed, observed[1:])):
            add(Check.SCHEMA, Status.BLOCK, "raw_date_order_invalid")
        claims = {}
        for day in calendar:
            if type(day) is not CalendarDay:
                raise ValueError("invalid calendar")
            day.__post_init__()
            if day.day in claims:
                add(Check.CALENDAR, Status.BLOCK, "duplicate_or_revised_calendar_day", (day.day,))
            if not requested.start <= day.day <= requested.end:
                add(Check.CALENDAR, Status.BLOCK, "calendar_outside_request", (day.day,))
            claims[day.day] = day
            if day.evidence_id:
                evidence.add(day.evidence_id)
        all_days = []
        while current <= end:
            all_days.append(current.isoformat())
            if current == end:
                break
            current += timedelta(days=1)
        absent_calendar = set(all_days) - claims.keys()
        if absent_calendar:
            add(Check.CALENDAR, Status.UNVERIFIED, "calendar_coverage_missing", absent_calendar)
        add(Check.CALENDAR, Status.UNVERIFIED, "calendar_authentication_not_implemented")
        observed_set = set(observed)
        expected = []
        for day in all_days:
            claim = claims.get(day)
            if claim is None:
                continue
            scoped_state = claim.state
            if claim.state is not MarketState.NORMAL and claim.code != code:
                add(Check.MARKET_STATE, Status.UNVERIFIED, "market_state_scope_unverified", (day,))
                scoped_state = MarketState.UNKNOWN
            if listing and not listing.start <= day <= listing.end:
                category = "pre_listing_claim" if day < listing.start else "post_delisting_claim"
            elif not claim.session:
                category = "closed_day_claim"
            elif scoped_state is MarketState.FULL_HALT:
                category = "full_halt_claim"
            elif scoped_state is MarketState.NO_TRADES:
                category = "no_trades_claim"
            else:
                category = "expected_bar_claim"
                expected.append(day)
            if category != "expected_bar_claim":
                add(Check.MARKET_STATE, Status.UNVERIFIED, category, (day,))
                if day in observed_set:
                    add(Check.MARKET_STATE, Status.UNVERIFIED, "bar_conflicts_with_market_claim", (day,))
                else:
                    add(Check.COMPLETENESS, Status.UNVERIFIED, "absence_requires_authenticated_evidence", (day,))
            elif scoped_state is MarketState.UNKNOWN:
                add(Check.MARKET_STATE, Status.UNVERIFIED, "market_state_unknown", (day,))
        comparison = compare_dates(tuple(expected), tuple(observed))
        if comparison.missing:
            add(Check.COMPLETENESS, Status.UNVERIFIED, "missing_expected_dates_unverified_calendar", comparison.missing)
        if comparison.unexpected:
            add(Check.CALENDAR, Status.UNVERIFIED, "unexpected_dates_unverified_calendar", comparison.unexpected)
        add(Check.SCHEMA, Status.UNVERIFIED, "raw_structure_checked_source_unverified")
    except _LimitExceeded as error:
        for check in (Check.SCHEMA, Check.COMPLETENESS, Check.CALENDAR, Check.MARKET_STATE):
            add(check, Status.BLOCK, error.code)
    except Exception:
        for check in (Check.SCHEMA, Check.COMPLETENESS, Check.CALENDAR, Check.MARKET_STATE):
            add(check, Status.BLOCK, "invalid_input_or_inspection_error")
    checks = []
    for check in (Check.SCHEMA, Check.COMPLETENESS, Check.CALENDAR, Check.MARKET_STATE):
        relevant = [f for f in findings if f.check is check]
        status = Status.BLOCK if any(f.status is Status.BLOCK for f in relevant) else Status.UNVERIFIED
        reason = sorted(f.reason for f in relevant if f.status is status)[0]
        checks.append(CheckResult(check, status, reason, target, tuple(sorted(evidence)),
                                  evaluated_at, POLICY_VERSION, purpose))
    return Inspection(tuple(checks), tuple(findings))
