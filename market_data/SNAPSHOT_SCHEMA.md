# In-memory snapshot contract v1

`market_data.snapshots` defines frozen Python dataclass schemas, not a storage
service or a JSON parser. `Snapshot.to_dict()` returns a detached JSON-compatible
value. No filesystem, API, environment-secret, or order access is added.

- `snapshot/1`: acquisition manifest plus an immutable tuple of daily bar versions.
- `acquisition/1`: acquisition ID, provider, code, inclusive request range,
  retrieval completion timestamp, and explicit completion flag.
- Each bar retains source/instrument identity, trade date, decimal-string OHLC,
  integer volume, provider adjustment factor, price basis, publication evidence,
  contract-availability evidence, first observation and retrieval timestamps.
- Trade dates and request bounds accept only real dates in canonical
  `YYYY-MM-DD` form. Basic ISO and week-date aliases are rejected before keying.
- `TimeEvidence` preserves null unknowns, unverified claims and verified claims
  with evidence references. All supplied timestamps must have offsets. The
  caller must authenticate the evidence; a string reference is not proof.
  Supplied evidence must be a nonblank built-in string; mutable containers are
  rejected. Unknown evidence may remain null. Verified evidence requires both
  a timestamp and a nonblank reference. Bar time-evidence fields require the
  frozen `TimeEvidence` type. Selection revalidates evidence consistency.
- Evidence applies to the exact content version, including adjustment factors.
  Publication <= availability <= first observation <= retrieval when known.
  No daily close/publication time is inferred from a trade date.

The adapter's pure normalization contract is reused for date/security validation.
OHLC/factor validation also uses Decimal to avoid binary rounding. Existing
adapter, indicator calculations and persistence entry points remain unchanged.

## Pure comparison

`compare_snapshots` accepts identical provider/code/request scopes. Logical keys
include provider, market, code, currency, timeframe, date and price basis. Content
SHA-256 includes canonical decimal OHLC/factor and volume, excluding acquisition
and evidence metadata. Decimal formatting differences are equivalent, but
high-precision revisions remain distinct.

Results distinguish unchanged, revised, added, missing and duplicate keys.
Missing means absent in this response, never permission to delete. The completion
flag must be checked before interpreting missing rows. A duplicate in either
acquisition or an incomplete manifest makes result `complete=false` and clears
all publishable `added`, `revised` and `unchanged` candidates, including unrelated
keys. `missing` and `duplicates` remain diagnostic only. Manifest `complete`
describes the caller's acquisition claim, not independent quality certification.
Evidence changes with
identical prices still remain in the supplied immutable versions; the unchanged
classification describes market content only. Price-basis changes are distinct
keys and must not silently enter one indicator series.

## Conservative as-of selection

`select_as_of` uses supplied version tuples and an offset-aware decision timestamp.
It filters future JST trade dates and versions first observed after the decision,
then chooses the latest observed version per key. Conflicting versions at the
same observation time raise an error. Version identity includes the content hash,
first observation instant and both time-evidence values, statuses and references.
Retrieval time is an acquisition event and is excluded from version identity.
Identical versions retrieved repeatedly collapse to one deterministic
representative (earliest retrieval, then stable textual tie-breaks). Decimal and
offset formatting alone do not create a new content/observation version.
Changed content or evidence at the same observation instant remains ambiguous.
Evidence learned later must be supplied as a version observed at that later time,
never backdated to the original price observation.
Unverified latest revisions block verified
selection instead of silently falling back to an older value.

`historical_research` permits unknown publication/contract availability only for
already observed versions and always returns `verified_backtest_eligible=False`.
`verified_backtest` requires verified publication and availability evidence for
each selected version. Exclusions or empty results make eligibility false.
This deliberately conservative policy cannot reconstruct periods before the
system began observation, even from later provider claims. Reacquisition must
preserve the original first-observed time rather than replacing it with now.
Mixing adjusted and unadjusted selected bars for the same source/instrument raises
an error in both modes; a caller must explicitly choose one basis beforehand.

The eligibility flag is a necessary temporal gate, not a certification of trading
performance. The caller still must verify acquisition completeness, expected
calendar coverage, freshness, licensing, market-session completion, adjustment
consistency and simulated execution timing. Selection is not connected to any
performance reporting or live analysis pipeline in this change.

## Deferred work

No disk writer, atomic commit, schema migration/JSON deserialization, evidence
authentication, automated revision linkage, calendar/freshness gate, corporate
action reconstruction, analysis JSON handoff or backtest engine is enabled.
Synthetic unit tests cover this contract; live historical availability remains
unproven. Existing 23 tests remain regression checks.

Audit regressions additionally cover date aliases, mutable/blank evidence,
normal reacquisition, fail-closed duplicate handling, unknown publication,
UTC/JST midnight, exact availability boundaries, later corrections/evidence
updates and mixed price bases. Synthetic midnight cases test time conversion,
not whether a real market session has completed.
