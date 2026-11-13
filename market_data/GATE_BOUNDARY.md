# Shared safe gate boundary — ERR-011 / ERR-012

Pure synthetic-first addition on quality/1. No network, market-data persistence,
external AI, orders or operational authorization. Phase 2 is not complete.

## ERR-011: keep the typed upstream diagnostic

Use `route_gate_result(upstream, purpose=..., target=..., evaluated_at=...)` with
the complete `Inspection` or `GateDecision`, not `upstream.checks`. Bare check
tuples, lists, dictionaries, generators and unknown types are rejected as BLOCK.
Expected context is validated before upstream traversal. Invalid expected context
returns a diagnostic BLOCK without retaining an unvalidated upstream object.

- Inspection is revalidated, then its four checks are aggregated and the decision
  passes the existing consumer revalidation. Missing gates remain UNVERIFIED.
- GateDecision is structurally/contextually revalidated. A matching diagnostic
  BLOCK with evaluated_at=null is preserved unchanged, not filled with a supplied
  evaluation time and not replaced by a context-mismatch reason.
- Mismatched purpose/target/time/policy remains BLOCK. A validated upstream object
  is retained separately, even if the downstream contextual check rejects it.
- Unexpected validation exceptions return a fixed invalid_decision BLOCK without
  echoing exception details or retaining an unvalidated object.

`BoundaryOutcome` contains the decision AND the immutable validated upstream.
The upstream's original reasons, target and rejected/unknown time remain available;
`reason_codes` unions downstream reasons with upstream BLOCK reasons/findings.
BLOCK severity cannot be reduced. Direct construction validates types, nested
objects, immutable values, context for non-BLOCK results and severity agreement.
There is no trusted=True flag or factory marker. Construction is not provenance.

`analysis_input_allowed`, `verified_performance_allowed` and `orders_allowed`
remain read-only false. Direct result construction cannot grant permission. Future
connections must still invoke this boundary and authenticated actual evaluators.
No existing app/runtime caller is enabled by this change.

The existing low-level aggregate_checks API still accepts check iterables for
compatibility. It cannot infer whether an empty tuple came from a diagnostic.
Calling it directly with discarded diagnostic checks can still lose information
and return UNVERIFIED (never operational PASS in the current policy). This is not
a globally interceptable operation in Python; the new boundary explicitly refuses
that input form. Consumers must adopt the typed handoff. Arbitrary same-process
monkeypatching of implementation code is outside the interface trust boundary.

## ERR-012: bounded direct datetime inputs

`snapshots.validate_timestamp_text` requires a built-in nonblank string of at most
256 characters, checking length before whitespace scanning. `timestamp` calls it
before datetime.fromisoformat, then enforces timezone awareness as before.
No new limit differing from completeness's existing 256-character guard is used.

Protected direct paths:

| API | Invalid/overlong time behavior |
| --- | --- |
| snapshots.timestamp / TimeEvidence | ValueError before datetime parsing |
| BarVersion | All supplied time text checked before Decimal/normalization |
| AcquisitionManifest / Snapshot | Retrieval text checked before data traversal |
| select_as_of | Invalid decision time raises before consuming versions |
| quality CheckResult / GateDecision | Time text checked before nested-field traversal |
| evaluate_rights | Time text rejected before rights/reference work |
| aggregate_checks | invalid_evaluation_time BLOCK before consuming results |
| revalidate_decision | Invalid expected time BLOCK before inspecting decision |
| route_gate_result | Invalid expected time BLOCK before upstream inspection |
| completeness.inspect_completeness | Existing early diagnostic BLOCK unchanged |

### Nested child-time revalidation (ERR-012 audit follow-up)

Snapshot now requires the exact manifest/bar/evidence types and preflights every
child's first_observed_at, retrieved_at, published_at.value and available_at.value.
Unknown evidence with value=null remains allowed. All supplied values must pass
type/nonempty/256-character checks before parsing. The parent's tuple preflight
finishes before manifest parsing; the first invalid child stops traversal.
It then revalidates the manifest and each child's evidence/time ordering. This
does not rely on frozen dataclass construction having happened honestly.

select_as_of separates required validation from status/eligibility calculation.
It accepts only an exact built-in tuple and preflights child time text before
parsing decision_at. Generators, custom iterators, lists and tuple/list subclasses
are rejected before iteration. Invalid decision_at is rejected before traversal. Both evidence
objects are validated eagerly, so unknown publication cannot short-circuit
available_at validation. Chronology and future-observation exclusion are unchanged.

The same child-time validator is reused by BarVersion rather than duplicating its
ordering rules. Snapshot.to_dict and compare_snapshots also invoke parent
revalidation before serialization/hashing, closing the analogous post-construction
child-time corruption paths with no storage or network changes. These additions
validate temporal metadata; they are not general revalidation of every numeric
field after hostile in-process mutation, nor proof that time evidence is genuine.

Audit regressions first reproduced the accepted 283-character observation in
Snapshot and the accepted 257-character availability under unknown publication.
Tests cover all four altered time fields, both modes, 255/256 boundaries, invalid
types/ISO values, child construction bypass, zero parser/Decimal/normalization
calls on tuple preflight failure, early stop before later tuple items, stream refusal,
and serialization/comparison refusal before conversion/hashing. Existing 191
cases remain regression coverage. Objects must still cross the shared gate
boundary for quality decisions; standalone temporal eligibility grants no orders
or operational permissions.

None remains valid only where an existing diagnostic/unknown-time schema allows
it; it is not parsed, fabricated or filled. Valid timestamps up to 256 characters
retain prior parsing semantics, including offsets and fractional seconds. Future
timestamps can be syntactically valid: this guard does not attest availability,
finality, freshness or truth. Existing as-of/version checks remain in force.

Constructors keep their existing safe exception contracts, aggregate boundaries
keep their BLOCK contract. Existing files need no JSON/schema migration. No
completeness.py or existing test changes are required. General date-only fields,
non-time string/collection budgets in older APIs, and authenticating a supplied
first-observed timestamp are separate tasks; this is not a universal resource or
trust validator. Per-record guards apply at validation, not an omniscient scan of
an arbitrary iterator, which select_as_of now rejects.

## Regression evidence and deferred work

Existing 170 tests remain baseline. New synthetic tests first reproduced the old
diagnostic replacement, permissive long timestamp parsing, and result-iterator
consumption on invalid context. Additional coverage includes both result types,
all five purposes, empty/bare checks, mutable/forged objects, exceptions, mismatched
scope, 255/256/257-character inputs, invalid types/blank inputs, future-time meaning,
and direct constructors/functions with parser/conversion/traversal spies.

Still absent: root-of-trust/source verification, contract authentication, calendar
as-of evidence, session finality, freshness, actual licensing and runtime handoff.
No real market payload or API credential is part of the tests or this document.
Enabling any operational permission requires a separate reviewed implementation.


## ERR-013: finite selection input boundary

`select_as_of` requires `type(versions) is tuple`, consistent with its existing
annotation and documented version-tuple contract. Lists are not accepted either;
no implicit conversion or generator materialization occurs. Unsupported inputs
raise ValueError, never a successful empty Selection. The provisional
`MAX_SELECTION_VERSIONS = 4096` budget aligns with completeness.MAX_ROWS without
coupling the schema module to that gate. It counts versions including duplicates
and reacquisitions, not unique dates. Larger research histories require a separate
reviewed interface; silently truncating or independently selecting chunks would
change revision/conflict semantics and is not supported.

Order: mode validation, decision text guard, exact container type, tuple length,
all child time-text preflight, decision parsing, existing eager child time/order
validation, observation filtering and selection. Over-budget tuples are rejected
before child traversal, datetime parsing, conversion, sorting or hashing. Unknown
evidence does not skip validation of other supplied timestamps. Empty tuples remain
valid with temporal eligibility false. Existing normal tuple semantics are kept.

This closes the generator TOCTOU path where resuming iteration after yield changed
an already validated bar, including on iterator exhaustion. Regressions reproduce
both future-observation eligibility and long-availability leakage before the fix,
then require rejection with zero yields. Tests also cover custom/subclass inputs,
0/4095/4096/4097 counts, both modes, and unchanged operational denial.

Guarantee scope: the selection loop no longer runs caller-defined iteration code.
This is not a security sandbox for arbitrary Python objects or concurrent mutation.
Frozen bars and nested evidence are still shared references: another thread or
hostile same-process code using object.__setattr__, monkeypatching or custom field
objects can violate their assumptions. Callers must provide normally constructed
immutable records and prevent concurrent mutation through use of the result.
Independent immutable capture and broader field revalidation would require a
separate design. No authenticity, license, finality, freshness or order permission
is established by accepting a finite tuple or temporal eligibility.
