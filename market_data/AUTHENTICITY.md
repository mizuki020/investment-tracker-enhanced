# Evidence contract and conservative authenticity inspection (stage 1/2)

Policy `authenticity/1`, evidence `evidence/1`, claim `trust/1`.
Synthetic-only pure functions: no I/O, storage, cryptography, trust registration,
external AI, authorization or integration into quality/1. Phase 2 is incomplete.

## Public contract

`Target` binds code, market, canonical inclusive start/end dates, price basis,
data version, raw SHA-256 digest, normalized SHA-256 digest, normalization ID and
normalization version. Both hashes are required lowercase 64-character hex strings.
They are expected claims, not computed or authenticated payload hashes. The raw
hash names original bytes; the normalized hash names the specified canonical data.
Neither is a replacement for the other or for issuer authentication.

`Evidence` holds schema version, ID, issuer ID, kind, exact Target, issued_at,
valid_from, valid_until, optional corrects/replaces IDs and opaque immutable bytes.
Kinds: receipt, provider_attestation, calendar, market_state, time. Receipt means
a claimed acquisition receipt, not a provider signature. All kinds remain unverified.
The opaque payload is never decoded, hashed or interpreted as a key/signature.
`evidence_from_mapping` accepts only an exact bounded dictionary with known fields;
its nested target must already be an exact Target. No JSON parser is provided.
Dataclass constructors reject unknown keyword fields; the mapping adapter uses a
safe ValueError. No trusted/verified/public_key field is accepted.

`TrustClaim` is a SEPARATE unapproved claim schema: issuer, authority strings,
registration reference, approval history, allowed methods, key ID, validity,
claimed revocation state, environment and schema version. Claims never register
issuers or keys. Approval strings and even a claimed revoked status are not
independently authenticated. They therefore do not emit verified-revocation or
signature-failure reasons. Production trust loading does not exist; environment
is restricted to synthetic/unapproved. Such labels do not establish provenance.
No public key is automatically ingested or trusted.

All fields are built-in immutable primitives or exact frozen nested dataclasses.
The evaluator rechecks child objects, rather than trusting constructor execution.
Dates use the existing canonical date contract. Every supplied timestamp requires
an offset, exact nonblank string and <=256 characters before ISO parsing.
Validity is [valid_from, valid_until). Future issue times and evidence outside the
requested evaluation validity are observable claim conflicts and BLOCK; this does
not prove actual expiration/revocation by an authoritative issuer. Past evaluation
is not proof of past observation or availability.

## Input and resource budgets

| Input | Provisional maximum and unit |
| --- | --- |
| Evidence count | 64 objects per exact built-in tuple |
| Trust claims | 64 objects; each authority/approval/method tuple <=64 strings |
| Target-version inventory | 4096 exact Target objects, including duplicates |
| Metadata strings / timestamps | 256 Python characters per value |
| Opaque bytes | 65536 bytes per payload before any encoding/child processing |
| Complete evidence | 65536 bytes: canonical metadata UTF-8 bytes + payload bytes |
| Complete batch evidence | 1048576 bytes: sum of complete evidence sizes |

Canonical size metadata is json.dumps(sort_keys=True, separators=(',', ':'),
ensure_ascii=False) of all Evidence fields except payload, with Target as an
explicit field mapping. Thus Unicode is counted by UTF-8 bytes for evidence size,
independently of the character guard. This encoding defines size only, not a
signature normalization protocol. Evidence metadata is included in both byte caps.
Trust/schema input is separately bounded, not included in the evidence-byte sum.
Version inventory is structurally checked, not an allowlist overriding the exact
expected Target. Evidence must match the explicit expected Target in full.

The tuple type/count and aggregate raw-payload budgets are checked before child
processing, datetime parsing, metadata expansion, sorting or encoding. All child
and claim timestamp texts are preflighted before parsing. Complete metadata-byte
sizes require encoding after bounded field validation; this bounded work is not
claimed to be zero. No hashing/signature verification is performed. A batch may
perform at most 64 bounded metadata encodings and <=4096 Target validations.
Reference-cycle traversal has an explicit 4096-step budget per starting evidence;
ambiguous or costly replacement graphs fail closed, not by recursion exhaustion.

Lists, subclasses, generators and custom iterators are rejected without consuming
them. No implicit tuple(generator) conversion occurs. Caller preallocation is
outside this function's memory budget. These are temporary single-scope limits,
not provider entitlements; they require review before expansion.

## Decision rules and consumer restrictions

PASS is prohibited by evaluator AND direct AuthenticityDecision construction.
UNVERIFIED always contains trust_registration_unimplemented and/or
verification_unimplemented for an ordinary inspected batch. Missing evidence adds
evidence_missing. Unknown referenced corrections add replacement_unverified.

BLOCK reasons are fixed codes: invalid_input, invalid_evaluation_time,
evaluation_error, target_mismatch, duplicate_evidence, evidence_time_conflict,
evidence_not_current, replacement_conflict, resource_limit, context_mismatch,
invalid_decision. No raw input or exception text is copied into a reason.
Invalid constructors raise ValueError; the outer evaluator turns failures into
safe BLOCK. Expected validation failures are invalid_input; unexpected inspection
exceptions are evaluation_error. Invalid root context is not retained. Safe context
is retained when inspection fails after context validation. Invalid time is null,
never substituted with another time. BLOCK outranks all collected UNVERIFIED
reasons; scanning does not stop simply because trust/verification is missing.

`AuthenticityDecision` uses exact enum/type checks, canonical immutable reason
tuples, nested Target validation and severity/reason agreement. `revalidate`
rejects invalid structure and different target/time context. This is structural
revalidation, NOT proof that an inspector ran or evidence became authentic.
Direct or tampered non-PASS objects cannot authorize anything. All three permission
properties (analysis input, verified performance, orders) are hardcoded false.
No standalone backtest-eligible flag exists here.

## Existing boundary and deferred integration

No changes to snapshots, completeness, quality_gates, gate_boundary or their tests.
New decisions are not CheckResult/Inspection/GateDecision and must not be flattened
into checks or supplied as certified quality results. Existing route_gate_result
rejects this new result type; quality/1 remains unchanged. Upstream BLOCK handling
remains with that typed boundary. This inspector has no upstream parameter and
cannot certify retention of upstream diagnostics; future integration must carry
complete typed upstream and authenticity records, preserve unknown time and every
BLOCK reason, and rerun trusted verification rather than trust status.

Not implemented: independent trust registry/approval loader, provider or collector
key verification, signature validation, current/historical revocation, key rotation,
anti-rollback ledger, authenticated first observation, replay authorization,
authoritative correction resolution, actual payload hash calculation, licensing,
as-of certification, finality, freshness, operational input or persistent storage.
Duplicate evidence IDs are refused in one batch, but legitimate reacquisition
across calls is not classified as an attack. Future replay defense needs a trusted
versioned history; this pure function has no such state.

Frozen types are not a Python security sandbox. Shared objects must not be changed
concurrently or via object.__setattr__ while an evaluator/consumer is using them.
No arbitrary callbacks or caller-defined iteration are run. Same-process code
replacement, thread races, compromised trust administrators and correctly signed
false statements remain outside the guaranteed scope.

## Test evidence

Tests were created before modules existed and initially failed to import the
missing implementation. They then exercise synthetic schema/limits, no-PASS,
self-assertions, exact subject binding, eager time guards, finite input, zero-yield
rejection, late BLOCK after UNVERIFIED, fixed exception diagnostics, result
revalidation and false permissions. No real market data or real key is included.
The existing 213 tests are independent regression coverage, not live API evidence.

## ERR-014: correction consistency and revalidation entry guard

For both corrects and replaces, when the referenced evidence is present with the
same Target, the referring issued_at must be strictly later in absolute time.
Older or equal instants (including different offsets denoting the same instant)
add BLOCK reason replacement_time_conflict. Structural timestamp validation runs
before graph comparisons, including for constructor-bypassed child objects.
The comparison applies regardless of evidence order and does not stop on existing
UNVERIFIED reasons. It checks consistency of claims, not official publication time.
Missing references remain replacement_unverified; no predecessor time is invented.
Different subjects still trigger target_mismatch under the existing scope rule.

If corrects and replaces name different IDs, replacement_conflict BLOCK applies,
even if both references are missing. The same ID is allowed in both fields and is
one graph edge; normal strict chronology, self-reference and cycle rules still
apply. Duplicated matching edges do not multiply traversal paths. Allowing distinct
IDs in a future version requires a new evidence schema version and reviewed rules.

revalidate first checks expected evaluation-time type, nonempty/blank and <=256
character budget, then parses the offset-aware timestamp, then validates the
expected Target and decision. Invalid expected time yields the existing safe
invalid_decision BLOCK with null context, with no Target traversal; it is not
filled or echoed. Normal equivalent-offset or fractional-second instants retain
context comparison behavior. These changes do not register trust, authenticate
signatures/revocation, connect to quality/1, or change any permission property.

ERR-014 tests first reproduced older correction -> UNVERIFIED, distinct double
reference -> UNVERIFIED, and long expected time -> one Target validation. The
implementation then rejected all three as required. Additional synthetic coverage
includes equal/strictly later times, UTC/JST equivalence, both relation types,
input order, missing references, late contradictions, forced child mutation,
255/256 time acceptance, malformed-time early rejection and a 64-node chain with
matching dual references. All prior resource and trust limitations remain.
