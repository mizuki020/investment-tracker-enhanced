# Synthetic detached Ed25519 verification, v1

Specification fixed before implementation. Synthetic data only. No signing,
private-key generation/loading/storage, production trust, I/O, network, order or
operational gate integration is added to the implementation module.
Schemas: signing-statement/1, signature-context/1, signature-input/1.
Policy: synthetic-signature/1. Existing authenticity/1 and quality/1 are unchanged.

## Signed statement and exact bytes

SigningStatement fields: schema_version, environment (exactly synthetic), issuer,
key_id, algorithm (exactly ed25519), key_use (exact registry KeyUse), dataset,
purpose (exact existing Purpose), target (exact existing Target with ALL ten fields),
candidate_digest (registry content identity), issued_at and ordered context labels.
VerificationContext fields: schema_version, purpose, evaluated_at, ordered context.
SignatureInput fields: schema_version, statement, public_key, signature, raw,
normalized, candidate (exact RegistryCandidate) and context (VerificationContext).

Detached public_key is raw 32 bytes and signature is raw 64 bytes. No PEM,
Base64, hex-as-input, automatic algorithm negotiation or callbacks are supported.
PyNaCl/libsodium strict point validation precedes cryptography
Ed25519PublicKey.from_public_bytes(...).verify(signature,data). The latter verifies
the COMPLETE domain-prefixed message, never an independently
invented Ed25519 prehash or Ed25519ph variant. SHA-256 is used for payload/content
identity, not as a replacement for Ed25519 message verification.

Signing bytes are literal domain bytes
`investment-tracker:signing-statement/1:synthetic-ed25519-message:v1` + NUL +
UTF-8 JSON of the typed statement. Encoding: sorted field-map keys, compact comma/
colon separators, ensure_ascii=False, no BOM/newline, no Unicode normalization.
A record is ['record', exact class name, {ALL declared fields: encoded value}];
a tuple is ['tuple', ordered encoded values]; a string is ['str', exact text];
bytes are ['bytes.hex', lowercase hex]; an integer is ['int', decimal string];
Purpose and KeyUse carry distinct enum tags. None has an explicit tag only in
result diagnostics; it is not accepted in statement/input required fields.
No float or arbitrary type is accepted. Tuple order, field boundaries and Unicode
composed/decomposed spelling are distinct. Unpaired surrogates are rejected in
lightweight text validation before encoding. There is no JSON parser: exact-dict
adapters reject unknown/nonstring keys; duplicate raw JSON keys are consequently
outside the accepted input interface, not silently normalized. Unknown constructor
keywords are rejected. A future JSON parser must reject duplicates explicitly.

Target includes code, market, inclusive canonical trade-date range, price_basis,
data_version, separate raw/normalized lowercase SHA-256 hex digests,
normalization_id and normalization_version. The supported fixture normalization
label is synthetic-bytes/1: two explicitly supplied synthetic byte strings, NOT a
claim that a real provider normalization transformation was independently proved.
No unreviewed transformation function is executed. Both payload hashes are actually
recomputed and matched separately. Signature bytes are outside SigningStatement,
so no signature signs itself. Existing Evidence.payload/ApprovalRecord.signature
remain opaque claims and are never reinterpreted as this signature format.

## Key resolution and claim consistency

The registry candidate is re-inspected using its public inspector. BLOCK stops
verification and is retained as a complete RegistryInspection. UNVERIFIED permits
only synthetic mathematical checking; it never means an approved key. The signed
candidate_digest must match the freshly recomputed registry candidate digest.
Match issuer AND key_id, then compare the supplied raw key, algorithm, KeyUse,
claimed permitted uses, dataset, market, security code and inclusive scope range.
Existing registry validity/approval consistency also runs at evaluated_at. For a
resolved key, issued_at must also lie within its declared half-open validity.
Unknown key_id produces NOT_CHECKED/UNVERIFIED only after other applicable checks,
not a short circuit hiding payload or time contradictions. A known key_id with a
conflicting issuer/key/scope is BLOCK. Provider and collector uses remain distinct;
a collector VALID result does not attest provider origin. Management/time uses
are not supported as market-payload signatures in this minimum.
Statement purpose and ordered context must match VerificationContext. issued_at
must not exceed evaluated_at. These are claim consistency checks; first observation,
contractual availability, authoritative issue time, finality/freshness and as-of
certification are not implemented.

## Budgets, capture and fail-closed order

| Input | Fixed provisional limit |
| --- | --- |
| IDs/text/timestamps | 256 built-in characters; nonblank, no outer whitespace/surrogates |
| Context labels | 1..16 exact strings in an exact ordered tuple |
| Key/signature | 32/64 exact immutable bytes |
| raw / normalized bytes | 65536 bytes EACH |
| Signed message | 65536 bytes including domain and canonical statement |
| Full input budget | 1048576 bytes of compact typed JSON, including candidate, metadata and hex bytes |
| Registry | Existing 64 requests/64 approvals, 64KiB record/1MiB candidate budgets |
| Capture | Fixed accepted record graph, depth <=8, <=30000 nodes, tuple <=64 |

The full-input budget is additional to registry budgets, not permission to exceed
them. Typed encoding overhead and hex expansion count. Size computation necessarily
uses bounded encoding after primitive preflight. No datetime parsing, SHA-256,
public-key point validation or
Ed25519 verification occurs on type/count/length/size failures. Only exact built-ins,
known dataclasses/enums and finite tuples are accepted; no caller iterator executes.

Order in both evaluation and result revalidation:
1. All expected/result metadata text/type/count guards (no semantic time parsing).
2. Input primitive/container preflight and registry bounded preflight.
3. Budget encoding/size checks, then capture a detached graph of immutable values.
   Recheck primitive/count/depth bounds DURING capture and validate the snapshot.
4. Registry structure/key relationship and timestamp/Target/Purpose consistency.
   Strict point acceptance of the captured supplied public key, even for unknown
   key IDs. A resolved key must first match the candidate's claimed key bytes.
5. SHA-256(raw), SHA-256(normalized) and expected-digest comparison.
6. Exact domain-prefixed signing bytes; cryptography Ed25519 verification.
7. Result bound to full captured input and verifier policy using a DIFFERENT domain
   `investment-tracker:signature-input/1:synthetic-signature-result-binding:v1`+NUL.

Capture copies only declared known fields (no deepcopy hooks/caller callbacks).
Verification and output identity use the captured input, not shared source records.
Concurrent hostile mutation DURING capture is not atomically prevented; local
bounds and post-capture revalidation limit invalid snapshots, not prove a coherent
external transaction. Arbitrary class monkeypatching/same-process hostile code is
not a supported security boundary. Caller mutation after capture cannot alter the
captured byte strings used by verification. Original input preallocation is outside
this module's memory guarantees. Input identity is not authenticated provenance.

## Result model and reasons

SignatureInspection fields: crypto_state (VALID/INVALID/NOT_CHECKED), status
(existing Status, only BLOCK/UNVERIFIED), canonical reasons, input_digest,
purpose, evaluated_at, ordered context, policy_version, registry_result.
VALID means only a correct mathematical signature and requires UNVERIFIED plus
signature_valid_untrusted. INVALID requires BLOCK/signature_invalid.
NOT_CHECKED may be BLOCK (invalid data) or UNVERIFIED/key_unresolved.
Normal results retain trust_root_unverified, revocation_unverified and
history_unconnected. All five operational permission properties are always false.
No standalone backtest eligibility or storage/transmission authorization exists.

Fixed BLOCK reasons: invalid_input, invalid_result, resource_limit,
registry_blocked, key_binding_mismatch, scope_mismatch, context_mismatch,
time_conflict, raw_digest_mismatch, normalized_digest_mismatch,
unsupported_normalization, signature_invalid, verification_error, input_mismatch,
invalid_public_key.
No input/key/exception text enters reasons. Root schema/type failures raise safe
ValueError at construction or produce BLOCK at the evaluation boundary. Size
failures use resource_limit where distinguishable. InvalidSignature alone means
signature_invalid; unexpected backend errors mean verification_error.

Public signing_bytes only serializes a bounded valid statement; it never signs,
resolves keys, approves trust or grants permissions. evaluate_signature and
revalidate_signature perform full checks. The latter validates every result field
BEFORE any parsing, candidate traversal or crypto, then recomputes on supplied
input and compares full input identity/context/status. Normal direct construction
cannot create PASS. A forged matching UNVERIFIED result and digest is not a trusted
certificate; independent trust remains absent. Exceptions never grant authority.

## CI, tests and deferred work

Tests generate ONLY synthetic private keys in test memory. RFC 8032 test vector 1
checks the library against a published empty-message vector; fixture messages test
the domain-separated application protocol separately. No real credentials or real
market data are used. Existing 297 tests use fake HTTP openers, synthetic fixtures,
read-only skill files or temporary synthetic CSV/JSON; no real API/order path is run.
CI runs all test_*.py with socket connections denied, no injected secrets, read-only
contents permission and checkout credentials not persisted. Dependency installation
uses the package index but tests do not require market/network access.
Pinned cryptography, PyNaCl and transitive runtime dependencies are test-only.
Python 3.11/3.12 are validated in separate /tmp environments, not node_modules.

Not implemented: real trust-root distribution/registration approval, real provider
signature formats, management signature verification, authenticated revocation,
replay/rollback ledger, trusted clock/observation, license/as-of/finality/freshness,
existing quality-boundary wiring or any operational authorization. Replaying a valid
old message can still be mathematically VALID, never certified fresh or approved.

## Local acceptance evidence and independent-audit priorities

TDD first failed to import the absent module. After the minimal implementation,
15 initial tests passed. Expanded period-consistency testing then reproduced a
mathematically valid statement issued before the declared key-validity start being
left UNVERIFIED; the added strict period check changed it to time_conflict BLOCK.
Initial coverage was 31 new tests plus the original 297 = 328, with no failure/error/
skip, on CPython 3.11.17 and 3.12.14. The same socket-denied suite was used for both.
The Python 3.11 environment was created under /tmp, with cryptography 50.0.0,
cffi 2.1.1 and pycparser 3.0 installed from binary distributions. No real key,
provider API or real market payload was used. GitHub-hosted CI itself has not run
these local uncommitted workflow changes.

The workflow now discovers these ten files (current counts):

| File | Tests |
| --- | ---: |
| test_jquants_v2.py | 7 |
| test_market_data_authenticity.py | 38 |
| test_market_data_completeness.py | 56 |
| test_market_data_gate_boundary.py | 43 |
| test_market_data_indicators.py | 11 |
| test_market_data_quality_gates.py | 51 |
| test_market_data_snapshots.py | 40 |
| test_market_data_synthetic_signatures.py | 49 |
| test_market_data_trust_registry.py | 46 |
| test_stock_analysis_skill.py | 5 |

The only existing tracked edit is market-data-check.yml: broaden safe discovery
and path triggers, install the test-only pins, read-only contents permission and
no persisted checkout credential. Test-only changes and dependency-pin changes
trigger it. Existing adapters/gates and their test files are unchanged.

Independent audit should prioritize: all signed/result-binding field coverage;
separation of provider/collector claims; unknown-key paths not hiding late BLOCK;
full input/registry/result metadata caps before parser/hash/backend calls; exact
UTF-8 byte accounting; frozen capture under source mutation; and forged VALID
results requiring fresh cryptographic verification. This module intentionally
uses the registry's existing private bounded-input/result-metadata validators as
pure guards before its public inspector; changes to those helpers require these
regressions. It does not treat RegistryInspection as an approval certificate.
The standard vector tests the backend; domain/protocol tests separately test this
application. No claim of exhaustive cryptographic, concurrent or supply-chain
security follows from synthetic test success. Pinned versions are not signed
package provenance or provider trust roots.

## ERR-018 strict public-key acceptance and distribution qualification

cryptography 50.0.0 alone accepts the identity public key `01 || 00*31`
with detached signature `01 || 00*63` for different synthetic messages A/B.
The new key acceptance predicate is PyNaCl 1.6.2's
`nacl.bindings.crypto_core.crypto_core_ed25519_is_valid_point`.
It checks canonical encoding, curve membership, prime-order subgroup membership,
and rejects small-order points, including the identity. It is not a blacklist or
an application implementation of curve arithmetic. Message verification remains
Ed25519 over the full signed statement, with no new prehash or signing function.

The predicate must return exact bool True. False gives
BLOCK/invalid_public_key, crypto_state NOT_CHECKED, with zero Ed25519 verification
calls. Missing dependency/feature/function, UnavailableError, unexpected exception
or a non-bool return gives fixed BLOCK/verification_error; no exception text or key
bytes enter diagnostics. There is NO cryptography-only fallback. This check runs
only after all input/result bounded preflights and detached capture. It does not
make an unknown key trusted, and an unknown ID cannot hide an ineligible point.
Revalidation recomputes this predicate as well as the signature and full binding.
Public schemas and synthetic-signature/1 remain compatible; invalid_public_key
is the only added reason code. Existing authenticity/1 and quality/1 are untouched.
VALID still implies UNVERIFIED with every operational permission false.

Stage A qualified actual binary distributions BEFORE the implementation change.
PyNaCl 1.6.2 release notes and installed wheel METADATA identify bundled libsodium
1.0.20-stable, 2025-12-31 build, fixing CVE-2025-69277:
https://github.com/pyca/pynacl/blob/1.6.2/CHANGELOG.rst
The PyPI sdist (inspection only, never built/installed) SHA-256 is
018494d6d696ae03c7e656e5e74cdfd8ea1326962cc401bcf018f1ed8436811c.
Its subgroup implementation checks BOTH [l]P.X == 0 and [l]P.Y == [l]P.Z.
The wheel's native subgroup function also contains two zero tests combined with
AND, inspected locally. The extension exposes no runtime sodium-version API;
the release/build identity is corroborated by official metadata, source, binary
identity and regression behavior, not a fabricated runtime version string.
ldd shows no dynamically loaded system libsodium. No SODIUM_INSTALL=system or
source build is used. The native extension SHA-256 is identical on both Pythons:
554206748472a39920ad95a26b6c217ce65439fd58d755a0f05457b3cbfbb57f.

Official PyPI wheel hashes were checked against PyPI release JSON, not merely
computed locally. These are the artifacts actually installed under /tmp:

| Wheel | SHA-256 |
| --- | --- |
| pynacl-1.6.2-cp38-abi3-manylinux_2_34_x86_64.whl | c8a231e36ec2cab018c4ad4358c386e36eede0319a0c41fed24f840b1dac59f6 |
| cryptography-50.0.0-cp311-abi3-manylinux_2_34_x86_64.whl | 82148ec5bddac30b51a5b3c1945075f896fa022cb93f8e4a01e9f6ee95292c5f |
| cffi-2.1.1-cp311-cp311-manylinux2014_x86_64.manylinux_2_17_x86_64.whl | 34e261f78cb6ceaaa36f42f2613f4380d94d9c759a9c73c769ee6e0247364632 |
| cffi-2.1.1-cp312-cp312-manylinux2014_x86_64.manylinux_2_17_x86_64.whl | c1453022f490d2459a11819d83ad1d586e9ff65a12ac3e705ffebd46d3685dcf |
| pycparser-3.0-py3-none-any.whl | b727414169a36b7d524c1c3e31839a521725078d7b2ff038656844266160a992 |

Qualification on EACH of CPython 3.11.17 and 3.12.14: 14 small-order/noncanonical/
sign variants rejected, 32 synthetic generated keys accepted, 224 mixed-order
points rejected (32 keys times ALL seven nontrivial torsion8 cosets), four named
official boundary/subgroup fixtures correct and two RFC 8032 vectors successful.
The important regression is the order-2 residue (j=4), which the old X-only
subgroup check could miss; earlier eight mixed-point tests were not sufficient.
The official repeated-addition regression and torsion8 fixture come from:
https://github.com/jedisct1/libsodium/blob/db1238f0a509de16b4bc323def5e68fdee78adda/test/default/core_ed25519.c
That source SHA-256 is
0687e796f7b6e4459cd9d2ece353224142e00078db0a73ceebd517acec7f4370.
All test curve operations use libsodium, not custom arithmetic. A fixed j=4
regression vector is also retained in repository tests. This is finite regression
evidence, not proof over every curve point. PyNaCl's actual minimal-feature guard
was exercised by disabling its feature flag in isolated processes; missing-API
and call exceptions were simulated. No minimal source build was performed.

Stage B RED: both actual identity-signature A/B regression tests failed before
the fix (UNVERIFIED instead of BLOCK). The 18 added test methods initially showed
81 failing assertions/subtests and two missing-helper errors. After the fix,
297 original + 31 initial signature + 18 ERR-018 = 346 tests pass with no failures,
errors or skips on both Python versions. The existing external independent audit
script was available: 78/78 passed on each version after the fix, compared with
76/78 before it. The API failure tests require zero Ed25519 verification calls;
resource-failure tests additionally require zero timestamp/SHA-256/point calls.
Capture mutation, candidate binding, ERR-016/017, deadlines, issuer/key-ID/scope
handling and permissions remain covered. The workflow now uses both Python
versions, retains socket-denied offline execution and installs exact wheel-only
dependency pins. GitHub-hosted Actions has not run these uncommitted changes.

This qualification covers the listed Linux x86_64 wheel only. Other wheels,
system libraries, source builds and architectures need equivalent qualification.
Package hashes/release metadata are not independent reproducible-build attestation.
Concurrent hostile mutation during capture, trust roots, authenticated revocation,
replay and real-provider evidence remain outside the guarantee. No production
gate wiring, trust approval or authority is added by this correction.
