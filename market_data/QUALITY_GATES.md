# Quality gate engine v1 — synthetic-only policy scaffold

Policy: `quality/1`. Implementation: `market_data.quality_gates`.
This change is not completion of Phase 2 and does not authorize production
analysis, persistence, external AI transmission, verified performance or orders.
There are no network, filesystem, credential or external-model calls.

## Implemented

- Strict `Status` enums: PASS, BLOCK, UNVERIFIED.
- Frozen `CheckResult`: check ID, status, reason code, target snapshot/scope ID,
  immutable evidence IDs, offset-aware evaluation time, policy version, purpose.
- Fixed mandatory check sets returned as frozensets. There is no caller subset,
  policy registry, plugin evaluator or implementation-status override parameter.
- Truth-table reducer `combine_statuses`: BLOCK first, then UNVERIFIED, otherwise
  PASS for a nonempty all-PASS set. Empty sets return UNVERIFIED; unknown states
  and iteration exceptions return BLOCK. This reducer conveys no authorization.
- Context-aware `aggregate_checks`: validates every result, purpose, target,
  policy version and evaluation instant (equivalent UTC/JST offsets are accepted).
  Duplicate IDs, malformed results, unknown purposes and evaluation exceptions
  yield BLOCK. Missing mandatory checks are materialized as UNVERIFIED results.
- Separate action-specific rights claim assessment for analyze, store and
  send_to_external_ai. A deny claim yields BLOCK; unknown/missing contract evidence
  yields UNVERIFIED. An allow claim with a reference still yields UNVERIFIED:
  contract authentication has NOT been implemented. HTTP success is not permission.

Constructors and rights-input validation may raise ValueError/TypeError on invalid
input; they never return PASS in that case. The aggregate boundary catches normal
evaluation/iteration exceptions and returns BLOCK without echoing exception
details. It does not execute callbacks. Invalid result types/fields, duplicates,
policy-version, purpose, target and evaluation-time mismatches have distinct fixed
reason codes. Unexpected iterator/evaluation exceptions use `evaluation_error`.
Each caller context field is checked independently: valid purpose, target and
offset-aware evaluation time survive errors; invalid fields become null. The
returned policy version is always the supported version, never copied from an
unsupported caller policy. These structural checks do not authenticate a target.

## Fixed required checks by purpose

Analysis baseline: schema, acquisition completeness, calendar, market state,
daily finality, as-of selection, analyze rights.

| Purpose | Mandatory checks |
| --- | --- |
| historical_research | Analysis baseline |
| verified_backtest | Baseline + time-evidence authenticity |
| analyze | Baseline + time-evidence authenticity + freshness |
| store | Schema + acquisition completeness + store rights |
| send_to_external_ai | Schema + acquisition completeness + external AI rights |

These are separate scopes, not freely interchangeable levels. A research result
cannot be reused under verified_backtest: purpose mismatch blocks aggregation.
Known extra checks cannot replace mandatory checks; their BLOCK/UNVERIFIED results
may conservatively stop the aggregate. Unknown check IDs are rejected.

## Not implemented or connected

| Gate | Current status |
| --- | --- |
| Snapshot schema validation adapter | Not connected to this engine |
| Acquisition/page completeness, calendar, suspension, missing/duplicate rows | Not implemented here |
| Session completion, provider finality and publication schedule | Not implemented |
| Purpose-specific freshness and entitlement delays | Not implemented |
| Time-evidence source authentication/revocation | Not implemented |
| As-of gate adapter | Existing snapshots.select_as_of is not connected |
| Contract authentication, scope, expiry, retention and AI license review | Not implemented |
| Indicator/history/adjustment and analysis handoff | Not connected |

Caller-supplied PASS results are NOT evidence of implementation. Aggregation
changes them to UNVERIFIED with `check_not_implemented` or
`contract_authentication_not_implemented`. Non-PASS claims may block work but
cannot grant it. No purpose currently has all required authenticated evaluators,
so **aggregate_checks cannot currently return PASS for any supported purpose**.
No test-only bypass is exposed in the production interface.

## Validated results and consumer boundary

`GateDecision` validates direct construction as well as factory output. Collection
fields must be built-in tuples containing validated immutable values. Status,
purpose, target, evaluation time and policy version are checked at runtime.
Non-diagnostic results require all mandatory checks, unique check IDs, consistent
scope/time/policy and agreement between the aggregate status/reasons and checks.
PASS in either the decision or its check list is currently rejected: required
authenticated evaluators do not yet exist. A caller cannot create a direct PASS
by supplying a complete but self-asserted list of checks.

Empty-check decisions are allowed only as BLOCK diagnostics with allowlisted
fixed error codes. Only these safety-stop records may have null context fields.
They are not successful validation certificates and never grant permissions.

`revalidate_decision` is the consumer boundary: given expected purpose, target,
time and policy, it revalidates the exact result type, rejects mismatched scope,
and recomputes normal results through `aggregate_checks`. It never trusts a status
field, a constructor marker or a private-factory convention. Valid diagnostic
BLOCKs remain BLOCK instead of being promoted on an empty-check recomputation.
Malformed or constructor-bypassed objects yield BLOCK with safe expected context.

`GateDecision.analysis_input_allowed`, `orders_allowed` and
`verified_performance_allowed` are read-only properties fixed to false, regardless
of status. Even the standalone all-PASS reducer grants no operational permission.
An application must not substitute that reducer or caller CheckResult objects
for a validated aggregate. Future integrations must use the consumer boundary
and authenticated evaluators, not a standalone `decision.status == PASS` test.
Enabling a future PASS path requires reviewed changes to both result validation
and trusted evaluation; no self-asserted result or origin flag is sufficient.
Same-process Python objects are not a security sandbox; arbitrary monkeypatching
of the evaluator implementation is outside this interface's trust boundary.

## Tests and next steps

Synthetic tests cover enum/metadata validation, frozen evidence, policy sets,
precedence and permutation invariance, empty/missing/duplicate checks, version,
purpose/target/time mismatches, exceptions, forged all-PASS reports, UTC/JST
equivalence, rights isolation and refusal to infer license from HTTP success.
Existing 63 regression tests must remain green.

Decision audit regressions cover direct empty/all-claimed PASS, mutable nested
collections, invalid status/types, mandatory-check omission, duplicate checks,
mixed scopes/policies, status/reason inconsistencies, safe partial-context error
retention, distinct error codes, consumer recomputation and constructor-bypass
rejection. Existing malformed-input tests retain their safety assertions while
expecting the new differentiated error codes instead of the former generic code.

Next: separately implement trusted evidence and contract evaluators, then the
schema/as-of adapters and actual calendar/finality/freshness checks. Enabling any
PASS path requires a reviewed code change and adversarial tests; no caller flag
can activate it. Live rights and market quality have not been verified by this
synthetic scaffold. Runtime integration and order execution remain disabled.
