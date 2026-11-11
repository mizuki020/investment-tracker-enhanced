# Synthetic trust registration model, stage 3-1

Specification fixed before implementation. Schema registry-candidate/1,
registration-request/1, approval-record/1; inspection policy registry-inspection/1.
This models CLAIMS only. It creates no trusted issuer, approved key or trust root.
No connection to authenticity/1, quality/1 or existing typed boundaries is added.

## Types and identity

KeyUse is an exact enum: provider, collector, management, time. KeyScope contains
one key use, market, dataset, canonical inclusive start/end dates and a nonempty
exact tuple of security codes (<=64, unique). Management scope is still explicit;
there is no implicit wildcard or arbitrary-code callback.
RegistrationRequest includes schema, request ID, registrant, management entity ID,
issuer ID, key ID, algorithm, raw immutable public-key bytes, KeyScope, claimed
permitted key uses, submitted_at and half-open validity [valid_from, valid_until).
Only ed25519/32-byte public-key REPRESENTATION is supported. Bytes are never used
for cryptographic verification. The permitted-use claim can cause denial when the
scope use is excluded, but can never grant authority.
ApprovalRecord includes schema, approval ID, approver, management entity ID, the
complete bound RegistrationRequest, state version, issued_at, half-open validity,
opaque signature bytes and a claimed active/unknown/revoked state. Embedding the
complete request binds public key, key ID, issuer, use, range, registrant and all
other request fields; an ID match alone is insufficient. An approver must differ
from the registrant, and the management entity must match. String identities are
unverified claims; real-person/organization independence is not authenticated.
RegistryCandidate includes schema, registry ID, state version, previous version,
request tuple and approval tuple. Versions are built-in integers 1..2^31-1 and
0..2^31-2 respectively; state_version must equal previous_version+1. This checks
only a claimed transition, not its agreement with an actual historical ledger.
Approval state versions must equal the candidate version.

All public nested types are exact frozen dataclasses with exact immutable built-in
field types. Unknown constructor keywords raise TypeError; a strict candidate
mapping adapter rejects unknown keys with ValueError. Nested values must already
be typed objects; no JSON/deserialization protocol or key loader is implemented.

## Refusal and diagnostics

BLOCK codes: invalid_input, invalid_evaluation_time, resource_limit,
evaluation_error, self_approval, approval_target_mismatch, state_conflict,
duplicate_request, duplicate_key, duplicate_approval, duplicate_approval_actor,
use_outside_claim, time_conflict, validity_conflict, invalid_decision,
context_mismatch. Expected malformed data becomes invalid_input; unexpected
inspection exceptions become evaluation_error. No exception body, key information
or caller value is included in reasons. Invalid context is null, not fabricated.

UNVERIFIED codes: trust_root_unverified, approval_signature_unverified,
revocation_unverified, history_unconnected, checkpoint_unverified,
requests_missing, approval_missing. All structurally valid evaluations retain the
first five. Claimed active/revoked never authenticates revocation. No PASS exists,
even via direct result construction. BLOCK outranks UNVERIFIED and evaluation does
not stop merely because root/signature/history is missing.

Request/approval IDs are unique in their own namespace. Repeated issuer/key ID is
rejected in one candidate, including different public keys. Approval IDs are unique;
repeated approver/request pair is also rejected. Full request mismatch, missing
bound request, management mismatch, version mismatch, self approval, and scope use
excluded by a request's declared permission list are BLOCK. Missing approvals are
UNVERIFIED. Approval issued_at cannot precede request submission or exceed the
provided evaluation instant; request submission cannot exceed evaluation time.
Request and approval must cover evaluation time; approval validity must fit within
the request validity. These are claim-consistency checks, not official time proof.

## Budgets and order

| Input | Provisional cap |
| --- | --- |
| Requests / approvals | 64 / 64 per exact tuple |
| Scope codes | 64 unique, each <=256 characters |
| Claimed permitted uses | 4 unique exact KeyUse values |
| All IDs/text/timestamps | 256 Python characters, built-in nonblank str without surrounding whitespace |
| Public key | exactly 32 immutable bytes, representation only |
| Signature claim | at most 4096 immutable bytes |
| Canonical request or approval | 65536 bytes each |
| Candidate canonical representation | 1048576 bytes total |
| Versions | 32-bit positive range; predecessor may be zero |

Canonical size is UTF-8 JSON with sorted keys, compact separators, ensure_ascii=False,
bytes as lowercase hex, enums as their values; schema field order is irrelevant.
The candidate encoding includes repeated bound requests and all metadata. This is
size accounting, not a signing protocol or canonical-signature guarantee.
Container count and primitive payload lengths are checked before child traversal,
datetime parsing or serialization. A bounded schema preflight validates ALL text,
nested types and collection limits before any date/datetime parsing or conversion.
Then sizes are counted with bounded serialization, then semantic/time validation
runs. No cryptography for signature verification, file access, iteration callbacks or
networking exists. Bounded structural content hashing is described below.
Evaluation-time text is checked before candidate traversal. Full structural and
byte preflight then precedes evaluation-time parsing and all semantic date parsing. Unknown-length
iterators, lists and subclasses are refused without consuming them.

RegistryInspection holds exact Status, canonical reason tuple, registry ID and
state version (or null for invalid context), evaluated_at, supported policy and
candidate_digest (null only for unbound BLOCK diagnostics).
Its constructor rejects PASS, mutable collections, invalid reasons and inconsistent
severity. revalidate_inspection requires complete candidate input and reruns the
inspector, comparing full result rather than trusting copied status. It cannot
prove provenance of a self-consistent candidate. All five operational permission
properties (analysis, verified performance, store, external AI, orders) are false.

## Non-guarantees and audit plan

Root distribution, administrator/key authentication, management signatures,
revocation, identity equivalence, key strength, key possession, actual approval,
history monotonicity, replay/rollback prevention, checkpoint verification and
persistent storage are unimplemented. No registry entry is written or trusted.
Synthetic claims are not promotable into a production trust store by this module.
Frozen records are not a security sandbox. Normally constructed records and stable
shared references are required during evaluation; concurrent object.__setattr__,
implementation monkeypatching and same-process adversarial execution are outside
scope. Parents revalidate malformed child fields; valid-looking forced edits
cannot be detected without independent signed history. Future consumers must not
use status alone, and must not flatten this result into existing quality checks.

Tests first fail before the module exists; they cover self approval, exact binding,
version consistency, duplicates, eager budgets, datetime boundaries, synthetic
unknown root/approval/revocation, late BLOCK, fixed exceptions and result tampering.
Independent audit should prioritize canonical byte accounting, parent preflight,
full binding equality, early stops, direct constructors and post-construction edits.


## ERR-016: structural candidate binding

A normal inspected result fixes a lowercase 64-hex SHA-256 candidate_digest.
UNVERIFIED construction requires this digest; a BLOCK safety diagnostic produced
before successful semantic validation may have no digest. Both status and digest
format are validated again at consumption. No factory marker is trusted.

Binding input is the literal domain bytes
`investment-tracker:registry-candidate/1:registry-inspection/1:structural-candidate-binding:sha256:v1`
followed by one NUL byte, then UTF-8 JSON of the typed representation below.
JSON uses sort_keys=True, separators=(',', ':'), ensure_ascii=False, no BOM or
trailing newline. No Unicode normalization is performed: composed/decomposed
strings are distinct. Invalid UTF-8-encodable text fails closed before binding.
This encoding is separate from the pre-existing byte-budget encoding.

- Each record: ['record', exact class name, {every declared field: encoded value}].
- Tuple: ['tuple', ordered encoded elements].
- Bytes: ['bytes.hex', lowercase hex].
- KeyUse: ['KeyUse', exact enum value].
- String: ['str', exact text]. Integer: ['int', canonical decimal text].
- Other types are rejected. Record field maps are key-sorted by the JSON encoder.

Every candidate/request/approval/scope field is included, including schema,
identifiers, issuer/management/registrant/approver, public key, key use/permission,
market/dataset/security/date range, time claims, candidate/predecessor/approval
versions, signature bytes and claimed revocation. All schema tuple fields are
order-sensitive for content identity, consistent with the existing exact request
binding. Equal independent objects have the same digest. Reordering tuples is a
different content identity; no tuple is silently treated as a mathematical set.
Internal duplicate-detection sets and unordered diagnostic reasons are NOT candidate
fields. Reason tuples remain canonical sorted sets outside candidate hashing.

Only after all exact-type/text/count/byte budgets AND semantic validation pass is
the binding representation serialized and hashed. Budget measurement still uses
bounded serialization as specified above; it is not claimed to be zero work.
The typed encoding adds bounded field/type-tag overhead to the bounded candidate.

Consumer revalidation recalculates the expected inspection from the supplied
candidate. A different candidate_digest yields fixed candidate_mismatch BLOCK,
even when registry ID, state version, evaluation time and reasons coincide.
Full result/context mismatch remains context_mismatch. No raw key, signature or
candidate text is put in diagnostics. Late inspection exceptions use evaluation_error.

## ERR-017: consumer preflight order

Both ordinary and revalidation entries share _bounded_candidate. Revalidation:
A) validate expected evaluation-time text and all actual result metadata with
_inspection_preflight (exact result type, bounded text/collections/versions,
digest format, status/reason consistency and nullable-context rules; no parsing);
B) inspect exact outer candidate and tuple count bounds;
C) bounded child primitive/text checks and canonical byte-budget checks;
D) only then parse result/expected/candidate times, validate semantics, encode/hash
binding and compare full result. Oversize candidates invoke neither timestamp nor
SHA-256 in either entry. Typed invalid data yields fixed BLOCK reasons. The existing
result's __post_init__ (which parses time) is deliberately deferred until C passes.
The ordinary entry has no supplied result; its own time text still precedes B/C.

This digest proves only structural content identity, not authentic approval or
inspection provenance. A caller able to forge a candidate, its digest and all
consistent result fields can still manufacture a matching UNVERIFIED object.
Revalidation cannot establish an independent trust root or prevent arbitrary
same-process code changes. PASS remains forbidden and every permission remains
false. Shared references must stay stable throughout validation/use; concurrent
mutation can race checks and hashing. There is no signed history or immutable
security boundary. No operational or existing gate integration is added.

Regression evidence: before fixes, matching changed public keys passed old-result
revalidation as UNVERIFIED; over-count candidates parsed two timestamps. Tests now
require candidate_mismatch BLOCK and zero parser/hash calls. Coverage includes
all schema fields, independent copies, ordered tuples, Unicode/type boundaries,
count/signature/record/batch excess, result tampering, late BLOCK and exceptions.


## ERR-017 follow-up: result metadata before datetime semantics

RegistryInspection.__post_init__ first invokes the same _inspection_preflight used
by revalidate_inspection. It checks all seven actual fields: status, reasons,
registry_id, state_version, evaluated_at, policy_version and candidate_digest.
No schema_version or writable permission flags exist on this result type.

The guard requires exact result/enum/container/primitive types, supported policy,
registry ID text <=256 characters, version 1..2147483647, <=the existing fixed
reason-code count, nonblank bounded reason strings from the fixed allowlist,
canonical unique reasons and consistent severity. Candidate digest is null only
where existing BLOCK diagnostics permit it, otherwise exactly 64 lowercase hex
characters. Result-time text uses the existing 256-character guard. UNVERIFIED
requires complete existing context and a candidate binding. No new limits are
introduced. Permissions remain read-only false properties, not caller fields.

Only after this entire guard succeeds does the constructor parse evaluated_at.
Revalidation checks expected-time text, then this guard, then the existing
candidate type/text/count/byte preflight; only afterward may datetime semantics,
canonical binding and SHA-256 run. Invalid result metadata returns the existing
invalid_decision BLOCK before candidate traversal. The constructor raises a safe
ValueError subclass without parsing. Result and candidate violations together
retain this result-guard priority. Unknown reason iterators are never consumed.

Regressions first reproduced one timestamp parse for a 257-character registry ID
and an overflowing result version. Both now reject with timestamp=0 and SHA-256=0
at construction/revalidation. Candidate-side limits and content binding are
unchanged. This adds no trust root, signatures, revocation/history authentication,
concurrent-mutation protection or operational permission. Prior non-guarantees
continue to apply.
