"""Synthetic detached Ed25519 checks. No signing, I/O or operational authorization."""
from dataclasses import dataclass, fields
from enum import Enum
import hashlib
import json
import re

from cryptography.exceptions import InvalidSignature
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PublicKey
try:
    from nacl.bindings import crypto_core as _ed25519_core
except ImportError:
    _ed25519_core = None
from market_data import authenticity as a, trust_registry as r
from market_data.quality_gates import Purpose, Status
from market_data.snapshots import timestamp, validate_timestamp_text

POLICY_VERSION = 'synthetic-signature/1'
MESSAGE_DOMAIN = b'investment-tracker:signing-statement/1:synthetic-ed25519-message:v1\0'
RESULT_DOMAIN = b'investment-tracker:signature-input/1:synthetic-signature-result-binding:v1\0'
MAX_TEXT = 256
MAX_CONTEXT = 16
MAX_PAYLOAD = 65536
MAX_MESSAGE = 65536
MAX_INPUT = 1048576
MAX_CAPTURE_DEPTH = 8
MAX_CAPTURE_NODES = 30000


class CryptoState(Enum):
    VALID = 'VALID'
    INVALID = 'INVALID'
    NOT_CHECKED = 'NOT_CHECKED'


class _Rejected(ValueError):
    def __init__(self, reason):
        self.reason = reason
        super().__init__(reason)


def _text(value):
    if type(value) is not str:
        raise _Rejected('invalid_input')
    if not 1 <= len(value) <= MAX_TEXT:
        raise _Rejected('resource_limit' if len(value) > MAX_TEXT else 'invalid_input')
    if value != value.strip() or not value.strip():
        raise _Rejected('invalid_input')
    if any(0xD800 <= ord(c) <= 0xDFFF for c in value):
        raise _Rejected('invalid_input')


def _time_text(value):
    _text(value)
    validate_timestamp_text(value)


def _tuple(value, limit):
    if type(value) is not tuple:
        raise _Rejected('invalid_input')
    if len(value) > limit:
        raise _Rejected('resource_limit')


def _labels(values, allow_empty=False):
    _tuple(values, MAX_CONTEXT)
    if not values and not allow_empty:
        raise _Rejected('invalid_input')
    for value in values:
        _text(value)


def _digest_text(value):
    if type(value) is not str or len(value) != 64 or not re.fullmatch('[0-9a-f]{64}', value):
        raise _Rejected('invalid_input')


@dataclass(frozen=True)
class SigningStatement:
    schema_version: str
    environment: str
    issuer: str
    key_id: str
    algorithm: str
    key_use: r.KeyUse
    dataset: str
    purpose: Purpose
    target: a.Target
    candidate_digest: str
    issued_at: str
    context: tuple[str, ...]

    def __post_init__(self):
        _statement_preflight(self)


@dataclass(frozen=True)
class VerificationContext:
    schema_version: str
    purpose: Purpose
    evaluated_at: str
    context: tuple[str, ...]

    def __post_init__(self):
        _context_preflight(self)


@dataclass(frozen=True)
class SignatureInput:
    schema_version: str
    statement: SigningStatement
    public_key: bytes
    signature: bytes
    raw: bytes
    normalized: bytes
    candidate: r.RegistryCandidate
    context: VerificationContext

    def __post_init__(self):
        _input_preflight(self)


def _statement_preflight(value):
    if type(value) is not SigningStatement:
        raise _Rejected('invalid_input')
    for name in ('schema_version', 'environment', 'issuer', 'key_id', 'algorithm', 'dataset'):
        _text(getattr(value, name))
    _time_text(value.issued_at)
    _labels(value.context)
    _digest_text(value.candidate_digest)
    if (value.schema_version != 'signing-statement/1' or value.environment != 'synthetic'
            or value.algorithm != 'ed25519'):
        raise _Rejected('invalid_input')
    if type(value.key_use) is not r.KeyUse or type(value.purpose) is not Purpose:
        raise _Rejected('invalid_input')
    if type(value.target) is not a.Target:
        raise _Rejected('invalid_input')
    for field in fields(a.Target):
        _text(getattr(value.target, field.name))
    _digest_text(value.target.raw_digest)
    _digest_text(value.target.normalized_digest)


def _context_preflight(value):
    if type(value) is not VerificationContext:
        raise _Rejected('invalid_input')
    _text(value.schema_version)
    _time_text(value.evaluated_at)
    _labels(value.context)
    if value.schema_version != 'signature-context/1' or type(value.purpose) is not Purpose:
        raise _Rejected('invalid_input')


_RECORDS = (SigningStatement, VerificationContext, SignatureInput,
            a.Target, r.RegistryCandidate, r.RegistrationRequest, r.ApprovalRecord, r.KeyScope)


def _typed(value):
    kind = type(value)
    if kind in _RECORDS:
        return ['record', kind.__name__, {f.name: _typed(getattr(value, f.name)) for f in fields(value)}]
    if kind is tuple:
        return ['tuple', [_typed(v) for v in value]]
    if kind is bytes:
        return ['bytes.hex', value.hex()]
    if kind in (Purpose, r.KeyUse):
        return [kind.__name__, value.value]
    if kind is str:
        return ['str', value]
    if kind is int:
        return ['int', str(value)]
    raise _Rejected('invalid_input')


def _encode(value):
    return json.dumps(_typed(value), sort_keys=True, separators=(',', ':'),
                      ensure_ascii=False).encode('utf-8')


def _message(value):
    return MESSAGE_DOMAIN + _encode(value)


def _input_preflight(value):
    if type(value) is not SignatureInput:
        raise _Rejected('invalid_input')
    _text(value.schema_version)
    if value.schema_version != 'signature-input/1':
        raise _Rejected('invalid_input')
    for name, exact in (('public_key', 32), ('signature', 64)):
        data = getattr(value, name)
        if type(data) is not bytes or len(data) != exact:
            raise _Rejected('invalid_input')
    for data in (value.raw, value.normalized):
        if type(data) is not bytes:
            raise _Rejected('invalid_input')
        if len(data) > MAX_PAYLOAD:
            raise _Rejected('resource_limit')
    _statement_preflight(value.statement)
    _context_preflight(value.context)
    # Deliberate dependency on existing pure bounded guard; no parser/hash here.
    r._bounded_candidate(value.candidate)
    if len(_message(value.statement)) > MAX_MESSAGE or len(_encode(value)) > MAX_INPUT:
        raise _Rejected('resource_limit')


def _capture(value):
    """Copy only declared fields; do not run deepcopy, constructor or iterator hooks."""
    remaining = [MAX_CAPTURE_NODES]
    def copy_value(item, depth):
        remaining[0] -= 1
        if remaining[0] < 0 or depth > MAX_CAPTURE_DEPTH:
            raise _Rejected('resource_limit')
        kind = type(item)
        if kind in _RECORDS or kind in (SignatureInspection, r.RegistryInspection):
            copied = object.__new__(kind)
            for field in fields(kind):
                object.__setattr__(copied, field.name, copy_value(getattr(item, field.name), depth + 1))
            return copied
        if kind is tuple:
            _tuple(item, 64)
            return tuple(copy_value(v, depth + 1) for v in item)
        if kind is str:
            _text(item)
            return item
        if kind is bytes:
            if len(item) > MAX_PAYLOAD:
                raise _Rejected('resource_limit')
            return item
        if kind is int:
            if not 0 <= item <= 2147483647:
                raise _Rejected('invalid_input')
            return item
        if item is None or kind in (Purpose, r.KeyUse, CryptoState, Status):
            return item
        raise _Rejected('invalid_input')
    return copy_value(value, 0)


def _statement_semantics(value):
    value.target.__post_init__()
    timestamp(value.issued_at)


def signing_bytes(statement):
    _statement_preflight(statement)
    captured = _capture(statement)
    _statement_preflight(captured)
    data = _message(captured)
    if len(data) > MAX_MESSAGE:
        raise _Rejected('resource_limit')
    _statement_semantics(captured)
    return data


def statement_from_mapping(value):
    names = {f.name for f in fields(SigningStatement)}
    if type(value) is not dict or len(value) > len(names):
        raise ValueError('invalid statement mapping')
    if any(type(key) is not str or key not in names for key in value):
        raise ValueError('invalid statement mapping')
    try:
        return SigningStatement(**value)
    except (ValueError, TypeError):
        raise ValueError('invalid statement mapping') from None


UNKNOWN = frozenset(('trust_root_unverified', 'revocation_unverified', 'history_unconnected',
                     'signature_valid_untrusted', 'key_unresolved'))
BLOCK = frozenset(('invalid_input', 'invalid_result', 'resource_limit', 'registry_blocked',
                   'key_binding_mismatch', 'scope_mismatch', 'context_mismatch', 'time_conflict',
                   'raw_digest_mismatch', 'normalized_digest_mismatch', 'unsupported_normalization',
                   'signature_invalid', 'verification_error', 'input_mismatch', 'invalid_public_key'))


@dataclass(frozen=True)
class SignatureInspection:
    crypto_state: CryptoState
    status: Status
    reasons: tuple[str, ...]
    input_digest: str | None
    purpose: Purpose | None
    evaluated_at: str | None
    context: tuple[str, ...]
    policy_version: str = POLICY_VERSION
    registry_result: r.RegistryInspection | None = None

    def __post_init__(self):
        _result_preflight(self)
        if self.evaluated_at is not None:
            timestamp(self.evaluated_at)
        if self.registry_result is not None:
            self.registry_result.__post_init__()

    @property
    def analysis_input_allowed(self): return False
    @property
    def verified_performance_allowed(self): return False
    @property
    def store_allowed(self): return False
    @property
    def external_ai_allowed(self): return False
    @property
    def orders_allowed(self): return False


def _result_preflight(value):
    if type(value) is not SignatureInspection:
        raise _Rejected('invalid_result')
    if type(value.crypto_state) is not CryptoState or type(value.status) is not Status or value.status is Status.PASS:
        raise _Rejected('invalid_result')
    _text(value.policy_version)
    if value.policy_version != POLICY_VERSION:
        raise _Rejected('invalid_result')
    _tuple(value.reasons, len(UNKNOWN | BLOCK))
    for code in value.reasons:
        _text(code)
        if code not in UNKNOWN | BLOCK:
            raise _Rejected('invalid_result')
    if not value.reasons or value.reasons != tuple(sorted(set(value.reasons))):
        raise _Rejected('invalid_result')
    if (value.status is Status.BLOCK) != bool(set(value.reasons) & BLOCK):
        raise _Rejected('invalid_result')
    if value.input_digest is not None:
        _digest_text(value.input_digest)
    if value.purpose is not None and type(value.purpose) is not Purpose:
        raise _Rejected('invalid_result')
    if value.evaluated_at is not None:
        _time_text(value.evaluated_at)
    _labels(value.context, allow_empty=True)
    if value.registry_result is not None:
        r._inspection_preflight(value.registry_result)
        if value.registry_result.status is Status.BLOCK and value.status is not Status.BLOCK:
            raise _Rejected('invalid_result')
    if value.crypto_state is CryptoState.VALID:
        if value.status is not Status.UNVERIFIED or 'signature_valid_untrusted' not in value.reasons:
            raise _Rejected('invalid_result')
    elif value.crypto_state is CryptoState.INVALID:
        if value.status is not Status.BLOCK or 'signature_invalid' not in value.reasons:
            raise _Rejected('invalid_result')
    elif 'signature_invalid' in value.reasons or 'signature_valid_untrusted' in value.reasons:
        raise _Rejected('invalid_result')
    if value.status is Status.UNVERIFIED:
        if (value.input_digest is None or value.purpose is None or value.evaluated_at is None
                or not value.context or value.registry_result is None):
            raise _Rejected('invalid_result')
        if not {'trust_root_unverified', 'revocation_unverified', 'history_unconnected'} <= set(value.reasons):
            raise _Rejected('invalid_result')
        if value.crypto_state is CryptoState.NOT_CHECKED and 'key_unresolved' not in value.reasons:
            raise _Rejected('invalid_result')


def _outcome(reasons, state=CryptoState.NOT_CHECKED, value=None, registry_result=None, digest=None):
    codes = tuple(sorted(set(reasons)))
    return SignatureInspection(state, Status.BLOCK if set(codes) & BLOCK else Status.UNVERIFIED,
                               codes, digest, None if value is None else value.context.purpose,
                               None if value is None else value.context.evaluated_at,
                               () if value is None else value.context.context,
                               registry_result=registry_result)


def _verify_ed25519(public_key, signature, message):
    Ed25519PublicKey.from_public_bytes(public_key).verify(signature, message)


def _validate_public_key(public_key):
    """Strict point acceptance, never trust approval; no permissive fallback."""
    if type(public_key) is not bytes or len(public_key) != 32:
        raise _Rejected('invalid_public_key')
    try:
        if _ed25519_core is None or _ed25519_core.has_crypto_core_ed25519 is not True:
            raise _Rejected('verification_error')
        valid = _ed25519_core.crypto_core_ed25519_is_valid_point(public_key)
    except Exception:
        raise _Rejected('verification_error') from None
    if type(valid) is not bool:
        raise _Rejected('verification_error')
    if not valid:
        raise _Rejected('invalid_public_key')


def _input_digest(value):
    return hashlib.sha256(RESULT_DOMAIN + _encode(value)).hexdigest()


def _evaluate_snapshot(value):
    st, ctx = value.statement, value.context
    registry = r.inspect_registry(value.candidate, evaluated_at=ctx.evaluated_at)
    if registry.status is Status.BLOCK:
        return _outcome(('registry_blocked',), registry_result=registry)
    _statement_semantics(st)
    now = timestamp(ctx.evaluated_at)
    if st.candidate_digest != registry.candidate_digest:
        return _outcome(('context_mismatch',), registry_result=registry)
    if st.purpose is not ctx.purpose or st.context != ctx.context:
        return _outcome(('context_mismatch',), registry_result=registry)
    if timestamp(st.issued_at) > now:
        return _outcome(('time_conflict',), registry_result=registry)
    if st.key_use not in (r.KeyUse.PROVIDER, r.KeyUse.COLLECTOR):
        return _outcome(('scope_mismatch',), registry_result=registry)
    matches = [q for q in value.candidate.requests if q.issuer == st.issuer and q.key_id == st.key_id]
    key = matches[0] if matches else None
    if key is None:
        if any(q.key_id == st.key_id for q in value.candidate.requests):
            return _outcome(('key_binding_mismatch',), registry_result=registry)
    else:
        if key.public_key != value.public_key or key.algorithm != st.algorithm:
            return _outcome(('key_binding_mismatch',), registry_result=registry)
        if not timestamp(key.valid_from) <= timestamp(st.issued_at) < timestamp(key.valid_until):
            return _outcome(('time_conflict',), registry_result=registry)
        scope = key.scope
        if (scope.use is not st.key_use or st.key_use not in key.permitted_uses
                or scope.market != st.target.market or scope.dataset != st.dataset
                or st.target.code not in scope.codes
                or not scope.start <= st.target.start <= st.target.end <= scope.end):
            return _outcome(('scope_mismatch',), registry_result=registry)
    if (st.target.normalization_id, st.target.normalization_version) != ('synthetic-bytes', '1'):
        return _outcome(('unsupported_normalization',), registry_result=registry)
    try:
        _validate_public_key(value.public_key)
    except _Rejected as error:
        return _outcome((error.reason,), registry_result=registry)
    errors = []
    if hashlib.sha256(value.raw).hexdigest() != st.target.raw_digest:
        errors.append('raw_digest_mismatch')
    if hashlib.sha256(value.normalized).hexdigest() != st.target.normalized_digest:
        errors.append('normalized_digest_mismatch')
    if errors:
        return _outcome(errors, registry_result=registry)
    message = signing_bytes(st)
    reasons = {'trust_root_unverified', 'revocation_unverified', 'history_unconnected'}
    state = CryptoState.NOT_CHECKED
    if key is None:
        reasons.add('key_unresolved')
    else:
        try:
            _verify_ed25519(value.public_key, value.signature, message)
            state = CryptoState.VALID
            reasons.add('signature_valid_untrusted')
        except InvalidSignature:
            state = CryptoState.INVALID
            reasons.add('signature_invalid')
        except Exception:
            return _outcome(('verification_error',), registry_result=registry)
    return _outcome(reasons, state, value, registry, _input_digest(value))


def _resource_reason(error):
    return 'resource_limit' if getattr(error, 'reason', None) == 'resource_limit' else 'invalid_input'


def evaluate_signature(value):
    try:
        _input_preflight(value)
        snapshot = _capture(value)
        _input_preflight(snapshot)
    except (ValueError, TypeError) as error:
        return _outcome((_resource_reason(error),))
    except Exception:
        return _outcome(('verification_error',))
    try:
        return _evaluate_snapshot(snapshot)
    except (ValueError, TypeError):
        return _outcome(('invalid_input',))
    except Exception:
        return _outcome(('verification_error',))


def revalidate_signature(result, *, value):
    try:
        _result_preflight(result)
        recorded = _capture(result)
        _result_preflight(recorded)
    except Exception:
        return _outcome(('invalid_result',))
    try:
        _input_preflight(value)
        snapshot = _capture(value)
        _input_preflight(snapshot)
    except (ValueError, TypeError) as error:
        return _outcome((_resource_reason(error),))
    except Exception:
        return _outcome(('verification_error',))
    try:
        recorded.__post_init__()
        expected = _evaluate_snapshot(snapshot)
        if recorded.input_digest != expected.input_digest:
            return _outcome(('input_mismatch',))
        if recorded != expected:
            return _outcome(('context_mismatch',))
        return expected
    except Exception:
        return _outcome(('invalid_result',))
