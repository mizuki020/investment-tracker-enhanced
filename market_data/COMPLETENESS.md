# Raw completeness diagnostics v1 (synthetic-only)

Module: `market_data.completeness`. This adds new pure functions and immutable
input/output types, without modifying the existing adapter, snapshots or quality
engine. There is no API, file storage, external AI or order operation.
Phase 2 remains incomplete.

## Inputs

- `RawBar`: canonical code, canonical YYYY-MM-DD, raw decimal-string OHLC and
  integer volume. Null fields are preserved for inspection, never imputed.
  The caller must explicitly map provider codes to the requested identity; the
  inspector does not silently equate a different code with the requested code.
- `Page`: immutable rows, requested cursor and returned next cursor. All pages
  must begin at the initial cursor, chain exactly and end without a pending cursor.
  Empty page lists, interrupted completion, premature termination, disconnected
  chains and repeated next cursors cannot count as complete.
- Requested range and acquired range: compared exactly, independent of row dates.
  An entitlement range is a separate unverified claim; an excluded requested
  interval blocks rather than silently narrowing the request.
- `CalendarDay`: one claim per calendar date, including closed dates. Full halt,
  partial halt, no trades and unknown market state are distinct. Security-specific
  states must match the requested code or remain unknown. Evidence IDs are
  references, not authenticated certificates.
- Listing and entitlement range claims retain optional evidence references.
  Listing bounds are inclusive. Unknown/open-ended listing history requires a
  future richer model; null listing is explicitly unverified in this version.
- Expected purpose, target and offset-aware evaluation time use existing quality
  types and policy version. Ordinary invalid context raises an exception, never
  PASS. Overlong evaluation time has the structured early-BLOCK behavior below.

Constructors reject mutable containers, wrong types, date aliases and invalid
dates. Inspection revalidates the supplied dataclasses, including page rows.
Malformed input/evaluation exceptions return BLOCK without exception details.
Finding statuses require the exact `Status` enum type; equality-compatible fake
objects are rejected, including when nested in a directly constructed Inspection.
No external mutable status/evidence reference is retained. Result severity must
agree with its immutable findings. Inclusive date enumeration checks the terminal
day before incrementing, so `0001-01-01` and `9999-12-31` are valid boundaries.

## Provisional resource limits

These are fixed code constants for the current single-security minimum, not API
entitlements, evidence of data completeness or caller-adjustable trust settings.

| Input | Maximum | Rationale |
| --- | ---: | --- |
| Rows per page and total rows | 4,096 | Bounded daily-history inspection and duplicate detection |
| Pages | 64 | Bounded cursor-chain validation |
| Calendar claims | 4,096 | Covers the bounded request with limited diagnostic headroom |
| Inclusive requested period | 3,660 days | Approximately ten years; caps date expansion |
| Each raw price string | 64 characters | Decimal conversion budget with generous precision headroom |
| Evidence ID / cursor / other short text | 256 characters | Bounds metadata and diagnostics |
| Volume magnitude | 64 bits | Avoids arbitrarily large integer payloads; negative values still fail OHLCV checks |
| Dates in a diagnostic/comparison tuple | 4,096 | Bounds set/sort work and public output construction |
| Evidence IDs per output check | 4,100 | Calendar references plus four range-claim references |
| Findings | 49,216 | Conservative bound derived from bounded rows/calendar plus fixed checks |

Re-evaluate these provisional limits before multi-security or longer-history use.
Collection counts and total row count are checked before flattening, copying,
sorting or Decimal conversion. Range size is checked before any row processing.
Calendar/reference and raw-field validation runs before numeric conversion.
Constructors also enforce their local size limits. Input already allocated by the
caller cannot be unallocated or prevented by this pure function.

Only built-in tuples are accepted; unknown-length iterators and mutable lists are
rejected without iteration. No unbounded iterator materialization is performed.
Normal bounded processing may allocate lists/sets proportional to accepted input.
Direct constructors/comparison helpers reject invalid input with ValueError.
Inspection turns data limit violations into four BLOCK checks with fixed codes
such as `row_count_limit`, `page_count_limit`, `calendar_count_limit`,
`range_day_limit`, `price_length_limit` and `reference_length_limit`. Other malformed
data retains the safe `invalid_input_or_inspection_error` code. Invalid outer
context normally remains an exception and never becomes PASS. No raw offending value or
exception text is copied into a reason code.

### Evaluation-time entry guard

After validating target and purpose, `inspect_completeness` requires evaluated_at
to be a nonempty built-in string and checks its length against the existing
`MAX_REFERENCE_CHARS=256` before timestamp parsing, page/row inspection, copying,
date expansion or Decimal conversion. No separate timestamp-size limit is added.
Normal ISO inputs retain the existing Inspection result and original timestamp.

An overlong timestamp returns the existing `GateDecision` diagnostic type with
status BLOCK, reason `invalid_evaluation_time`, validated target/purpose, supported
policy version, no checks, and evaluated_at=null. The rejected timestamp is not
parsed, retained, logged, truncated or replaced by an invented time. A normal
CheckResult requires a valid timestamp, so it is not fabricated for this error.
The return annotation is therefore `Inspection | GateDecision`. Consumers must
honor the early diagnostic BLOCK rather than discard it and aggregate its empty
check list. `revalidate_decision` keeps it non-PASS; all permissions remain false.
Other malformed/naive timestamps continue to raise ValueError as before.

Read-only adjacent-path review: Inspection validates each check's timestamp text
length before check validation/parsing. The normal inspection path supplies only
its bounded evaluated_at to CheckResult. Direct calls to tracked snapshots.timestamp
or quality_gates aggregation/revalidation still have no timestamp-length guard;
this change does not modify those unrelated existing APIs. Their callers need a
separate boundary review before production use. Do not re-submit an unbounded
rejected timestamp to another parser.

## Implemented checks

Before any adapter normalization, inspect original row/page order and detect:
wrong security, out-of-request rows, duplicate dates across all pages, null fields,
invalid/nonfinite/nonpositive OHLC, high/low contradictions, negative volume,
and non-increasing original dates. Null and malformed rows remain diagnostics;
they are not replaced with zero, forward-filled, removed or sorted by this code.

Calendar coverage must explicitly cover every requested calendar date. Duplicate
or conflicting calendar versions and out-of-request calendar dates block; a
corrected calendar must be selected upstream instead of merged blindly.
The pure `compare_dates` function reports missing, unexpected and duplicate dates.
Its `matches` boolean is set arithmetic under supplied assumptions, not a quality
status or a certificate of evidence trust. Raw ordering is checked separately.

Absence classifications include closed day, pre-listing, post-delisting, full-day
halt and no trades. Partial halts still expect a bar. Every proposed absence
exception remains `absence_requires_authenticated_evidence`; even a plausible
date/code/reference cannot justify it here. Rows conflicting with these claims
are explicitly diagnosed. No weekday-based calendar or price-based halt inference
is used. Empty holiday-only periods remain unverified until evidence is trusted.

## No production PASS path

Evidence authentication is not implemented. Therefore calendar, listing, halt,
no-trade and entitlement assertions never become verified facts. Missing expected
rows based on an unverified calendar are reported as UNVERIFIED with the dates;
independently observable structural violations such as duplication or scope
truncation yield BLOCK. A restrictive entitlement claim can stop work but never
grant rights. Market data finality, freshness and temporal authenticity remain
separate unimplemented gates.

`Inspection.checks` contains exactly one existing `CheckResult` for each of SCHEMA,
COMPLETENESS, CALENDAR and MARKET_STATE. Each has policy, purpose, target, evaluation
time and evidence references. `findings` preserves every reason and affected date;
the check's primary reason is chosen deterministically from the highest severity.
The returned check statuses are only BLOCK or UNVERIFIED, never PASS. Output
constructors reject PASS and mutable collections. All three operational permission
properties remain false. Evidence reference collection is diagnostic, not trust.

Consumers may pass these four checks to `aggregate_checks`, then validate the
decision with `revalidate_decision`. Other mandatory gates are not filled with
placeholder PASS. This module neither selects a historical snapshot nor bypasses
`select_as_of`: an authenticated historical calendar/listing/halt version and
as-of data selection are still required upstream, and AS_OF remains mandatory.
No existing runtime pipeline is enabled or modified by this addition.

## Synthetic validation and remaining work

Tests use synthetic prices and calendar assumptions only. A matching date set
under a synthetic verified-fixture assumption tests the mathematical expectation;
it does not create a production `verified` flag, trust hook or PASS bypass.
Cases cover single/multiple missing days, duplicate/out-of-range/wrong-code rows,
closed-day confusion, full/partial halt, no trades, listing bounds, page failures,
null/invalid OHLCV, ordering, calendar coverage/correction, entitlement truncation,
mutable/invalid inputs and exceptions, and quality-engine consumer revalidation.
Existing 114 tests are required regression checks.
Audit regressions preserve the previous 147 tests and add strict status/type and
immutability checks, month-end/leap/minimum/maximum-date boundaries, range reversal,
limit-1/limit/limit+1 for all five requested input dimensions and requested duration,
total rows across pages, early rejection before Decimal, iterator non-consumption
and quality-boundary safety. The prior excessive-period test now expects the
specific `range_day_limit` code rather than a generic internal error. Tests stay
within a few thousand synthetic items; memory exhaustion is not attempted.
Evaluation-time regressions add the reported long-fraction input, 255/256/257
character boundaries, normal ISO timestamps, invalid types/empty/malformed times,
zero parser/page/row/Decimal calls on early rejection, iterator non-consumption,
immutable diagnostic output and refusal to promote the diagnostic at the consumer
boundary. Existing 163 cases remain regression coverage.

Independent review should prioritize calendar/market-state trust and date/code
scope, cursor-chain completeness, the distinction between claims and proven
absence, raw-to-normalized mapping, input resource limits and exception handling.
Still absent: actual source authentication, calendar/revision as-of selection,
open-ended listing histories, session finality, freshness, license review and
production integration. All dates/prices supplied here are assumed inputs, not
independently observed live evidence. This does not certify backtest performance.
