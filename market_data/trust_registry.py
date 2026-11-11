"""Synthetic registration CLAIM inspection. No trust root, I/O or cryptography."""
from dataclasses import dataclass, fields
from enum import Enum
import json
import hashlib
import re

from market_data.snapshots import timestamp, validate_timestamp_text, trade_day
from market_data.quality_gates import Status

POLICY_VERSION = 'registry-inspection/1'
MAX_RECORDS = 64
MAX_TEXT = 256
MAX_RECORD_BYTES = 65536
MAX_BATCH_BYTES = 1048576
MAX_SIGNATURE_BYTES = 4096


class KeyUse(Enum):
    PROVIDER = 'provider'
    COLLECTOR = 'collector'
    MANAGEMENT = 'management'
    TIME = 'time'


class _Rejected(ValueError):
    def __init__(self, reason):
        self.reason = reason
        super().__init__(reason)


def _text(value):
    if type(value) is not str or not 1 <= len(value) <= MAX_TEXT or not value.strip() or value != value.strip():
        raise _Rejected('invalid_input')


def _tuple(value, limit):
    if type(value) is not tuple:
        raise _Rejected('invalid_input')
    if len(value) > limit:
        raise _Rejected('resource_limit')


def _version(value, minimum=1):
    if type(value) is not int or not minimum <= value <= 2147483647:
        raise _Rejected('invalid_input')


@dataclass(frozen=True)
class KeyScope:
    use: KeyUse
    market: str
    dataset: str
    start: str
    end: str
    codes: tuple[str, ...]

    def __post_init__(self):
        _validate(self)


@dataclass(frozen=True)
class RegistrationRequest:
    schema_version: str
    request_id: str
    registrant: str
    management_id: str
    issuer: str
    key_id: str
    algorithm: str
    public_key: bytes
    scope: KeyScope
    permitted_uses: tuple[KeyUse, ...]
    submitted_at: str
    valid_from: str
    valid_until: str

    def __post_init__(self):
        _validate(self)


@dataclass(frozen=True)
class ApprovalRecord:
    schema_version: str
    approval_id: str
    approver: str
    management_id: str
    request: RegistrationRequest
    state_version: int
    issued_at: str
    valid_from: str
    valid_until: str
    signature: bytes
    revocation: str

    def __post_init__(self):
        _validate(self)


@dataclass(frozen=True)
class RegistryCandidate:
    schema_version: str
    registry_id: str
    state_version: int
    previous_version: int
    requests: tuple[RegistrationRequest, ...]
    approvals: tuple[ApprovalRecord, ...]

    def __post_init__(self):
        _validate(self)


def _preflight(value):
    """Exact types/counts and primitive budgets only, before parsing or encoding."""
    kind = type(value)
    if kind is RegistryCandidate:
        _tuple(value.requests, MAX_RECORDS)
        _tuple(value.approvals, MAX_RECORDS)
        _text(value.schema_version)
        _text(value.registry_id)
        _version(value.state_version)
        _version(value.previous_version, 0)
        for child in value.requests:
            if type(child) is not RegistrationRequest:
                raise _Rejected('invalid_input')
            _preflight(child)
        for child in value.approvals:
            if type(child) is not ApprovalRecord:
                raise _Rejected('invalid_input')
            _preflight(child)
    elif kind is RegistrationRequest:
        if type(value.public_key) is not bytes or len(value.public_key) != 32:
            raise _Rejected('invalid_input')
        _tuple(value.permitted_uses, 4)
        for use in value.permitted_uses:
            if type(use) is not KeyUse:
                raise _Rejected('invalid_input')
        for name in ('schema_version', 'request_id', 'registrant', 'management_id',
                     'issuer', 'key_id', 'algorithm'):
            _text(getattr(value, name))
        for instant in (value.submitted_at, value.valid_from, value.valid_until):
            validate_timestamp_text(instant)
        if type(value.scope) is not KeyScope:
            raise _Rejected('invalid_input')
        _preflight(value.scope)
    elif kind is ApprovalRecord:
        if type(value.signature) is not bytes:
            raise _Rejected('invalid_input')
        if len(value.signature) > MAX_SIGNATURE_BYTES:
            raise _Rejected('resource_limit')
        for name in ('schema_version', 'approval_id', 'approver', 'management_id', 'revocation'):
            _text(getattr(value, name))
        _version(value.state_version)
        for instant in (value.issued_at, value.valid_from, value.valid_until):
            validate_timestamp_text(instant)
        if type(value.request) is not RegistrationRequest:
            raise _Rejected('invalid_input')
        _preflight(value.request)
    elif kind is KeyScope:
        if type(value.use) is not KeyUse:
            raise _Rejected('invalid_input')
        _tuple(value.codes, 64)
        for text in (value.market, value.dataset, value.start, value.end):
            _text(text)
        for code in value.codes:
            _text(code)
    else:
        raise _Rejected('invalid_input')


def _plain(value):
    if type(value) in (KeyScope, RegistrationRequest, ApprovalRecord, RegistryCandidate):
        return {f.name: _plain(getattr(value, f.name)) for f in fields(value)}
    if type(value) is tuple:
        return [_plain(v) for v in value]
    if type(value) is bytes:
        return value.hex()
    if type(value) is KeyUse:
        return value.value
    return value


def _size(value):
    return len(json.dumps(_plain(value), sort_keys=True, separators=(',', ':'),
                          ensure_ascii=False).encode('utf-8'))


def _sizes(value):
    if type(value) is RegistryCandidate:
        for record in value.requests + value.approvals:
            if _size(record) > MAX_RECORD_BYTES:
                raise _Rejected('resource_limit')
        if _size(value) > MAX_BATCH_BYTES:
            raise _Rejected('resource_limit')
    elif _size(value) > MAX_RECORD_BYTES:
        raise _Rejected('resource_limit')


def _semantic(value):
    kind = type(value)
    if kind is KeyScope:
        if not value.codes or len(set(value.codes)) != len(value.codes):
            raise _Rejected('invalid_input')
        if trade_day(value.start) > trade_day(value.end):
            raise _Rejected('invalid_input')
    elif kind is RegistrationRequest:
        if value.schema_version != 'registration-request/1' or value.algorithm != 'ed25519':
            raise _Rejected('invalid_input')
        if len(set(value.permitted_uses)) != len(value.permitted_uses):
            raise _Rejected('invalid_input')
        _semantic(value.scope)
        if timestamp(value.valid_from) >= timestamp(value.valid_until):
            raise _Rejected('validity_conflict')
        timestamp(value.submitted_at)
    elif kind is ApprovalRecord:
        if value.schema_version != 'approval-record/1' or value.revocation not in ('unknown', 'active', 'revoked'):
            raise _Rejected('invalid_input')
        _semantic(value.request)
        if timestamp(value.valid_from) >= timestamp(value.valid_until):
            raise _Rejected('validity_conflict')
        timestamp(value.issued_at)
    else:
        if value.schema_version != 'registry-candidate/1':
            raise _Rejected('invalid_input')
        if value.state_version != value.previous_version + 1:
            raise _Rejected('state_conflict')
        for child in value.requests + value.approvals:
            _semantic(child)


def _validate(value):
    _preflight(value)
    _sizes(value)
    _semantic(value)


def candidate_from_mapping(value):
    names = {f.name for f in fields(RegistryCandidate)}
    if type(value) is not dict or len(value) > len(names):
        raise ValueError('invalid candidate mapping')
    if any(type(k) is not str or k not in names for k in value):
        raise ValueError('invalid candidate mapping')
    try:
        return RegistryCandidate(**value)
    except (ValueError, TypeError):
        raise ValueError('invalid candidate mapping') from None


UNKNOWN = frozenset(('trust_root_unverified', 'approval_signature_unverified',
                     'revocation_unverified', 'history_unconnected', 'checkpoint_unverified',
                     'requests_missing', 'approval_missing'))
BLOCK = frozenset(('invalid_input', 'invalid_evaluation_time', 'resource_limit',
                   'evaluation_error', 'self_approval', 'approval_target_mismatch',
                   'state_conflict', 'duplicate_request', 'duplicate_key',
                   'duplicate_approval', 'duplicate_approval_actor', 'use_outside_claim',
                   'time_conflict', 'validity_conflict', 'invalid_decision', 'context_mismatch',
                   'candidate_mismatch'))


@dataclass(frozen=True)
class RegistryInspection:
    status: Status
    reasons: tuple[str, ...]
    registry_id: str | None
    state_version: int | None
    evaluated_at: str | None
    policy_version: str = POLICY_VERSION
    candidate_digest: str | None = None

    def __post_init__(self):
        _inspection_preflight(self)
        if self.evaluated_at is not None:
            timestamp(self.evaluated_at)

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


def _inspection_preflight(inspection):
    """Bound every actual result field before parsing, candidate walks or SHA-256."""
    if type(inspection) is not RegistryInspection:
        raise ValueError('invalid inspection')
    if type(inspection.status) is not Status or inspection.status is Status.PASS:
        raise ValueError('PASS is unavailable')
    _text(inspection.policy_version)
    if inspection.policy_version != POLICY_VERSION:
        raise ValueError('unsupported inspection policy')
    if inspection.registry_id is not None:
        _text(inspection.registry_id)
    if inspection.state_version is not None:
        _version(inspection.state_version)
    if inspection.evaluated_at is not None:
        validate_timestamp_text(inspection.evaluated_at)
    if inspection.candidate_digest is not None:
        if (type(inspection.candidate_digest) is not str
                or len(inspection.candidate_digest) != 64
                or not re.fullmatch('[0-9a-f]{64}', inspection.candidate_digest)):
            raise ValueError('invalid candidate digest')
    _tuple(inspection.reasons, len(UNKNOWN | BLOCK))
    for reason in inspection.reasons:
        _text(reason)
        if reason not in UNKNOWN | BLOCK:
            raise ValueError('invalid reasons')
    if not inspection.reasons or inspection.reasons != tuple(sorted(set(inspection.reasons))):
        raise ValueError('noncanonical reasons')
    if (inspection.status is Status.BLOCK) != bool(set(inspection.reasons) & BLOCK):
        raise ValueError('inconsistent severity')
    if inspection.status is Status.UNVERIFIED:
        if inspection.candidate_digest is None:
            raise ValueError('missing candidate binding')
        if None in (inspection.registry_id, inspection.state_version, inspection.evaluated_at):
            raise ValueError('incomplete context')


def _decision(reasons, candidate=None, evaluated_at=None, candidate_digest=None):
    codes = tuple(sorted(set(reasons)))
    return RegistryInspection(Status.BLOCK if set(codes) & BLOCK else Status.UNVERIFIED,
                              codes, None if candidate is None else candidate.registry_id,
                              None if candidate is None else candidate.state_version, evaluated_at,
                              candidate_digest=candidate_digest)


# This is a content-binding domain, never an approval/signature domain.
BINDING_DOMAIN = (b'investment-tracker:registry-candidate/1:'
                  b'registry-inspection/1:structural-candidate-binding:sha256:v1\0')


def _binding_value(value):
    kind = type(value)
    if kind in (KeyScope, RegistrationRequest, ApprovalRecord, RegistryCandidate):
        return ['record', kind.__name__,
                {f.name: _binding_value(getattr(value, f.name)) for f in fields(value)}]
    if kind is tuple:
        return ['tuple', [_binding_value(v) for v in value]]
    if kind is bytes:
        return ['bytes.hex', value.hex()]
    if kind is KeyUse:
        return ['KeyUse', value.value]
    if kind is str:
        return ['str', value]
    if kind is int:
        return ['int', str(value)]
    raise _Rejected('invalid_input')


def _candidate_digest(candidate):
    # Only invoked after bounded structure, size and semantic validation.
    body = json.dumps(_binding_value(candidate), sort_keys=True,
                      separators=(',', ':'), ensure_ascii=False).encode('utf-8')
    return hashlib.sha256(BINDING_DOMAIN + body).hexdigest()


def _bounded_candidate(candidate):
    if type(candidate) is not RegistryCandidate:
        raise _Rejected('invalid_input')
    _preflight(candidate)
    _sizes(candidate)


def _inspect(candidate, evaluated_at):
    # Public entry completed exact-type/text/size preflight before parsing.
    _semantic(candidate)
    reasons = set(UNKNOWN - {'requests_missing', 'approval_missing'})
    now = timestamp(evaluated_at)
    by_id = {}
    keys = set()
    for request in candidate.requests:
        if request.request_id in by_id:
            reasons.add('duplicate_request')
        by_id[request.request_id] = request
        key = (request.issuer, request.key_id)
        if key in keys:
            reasons.add('duplicate_key')
        keys.add(key)
        if request.scope.use not in request.permitted_uses:
            reasons.add('use_outside_claim')
        if timestamp(request.submitted_at) > now:
            reasons.add('time_conflict')
        if not timestamp(request.valid_from) <= now < timestamp(request.valid_until):
            reasons.add('validity_conflict')
    approvals = set()
    actors = set()
    covered = set()
    for approval in candidate.approvals:
        bound = approval.request
        request = by_id.get(bound.request_id)
        if request is None or bound != request or approval.management_id != bound.management_id:
            reasons.add('approval_target_mismatch')
        if approval.approver == bound.registrant:
            reasons.add('self_approval')
        if approval.state_version != candidate.state_version:
            reasons.add('state_conflict')
        if approval.approval_id in approvals:
            reasons.add('duplicate_approval')
        approvals.add(approval.approval_id)
        actor = (bound.request_id, approval.approver)
        if actor in actors:
            reasons.add('duplicate_approval_actor')
        actors.add(actor)
        covered.add(bound.request_id)
        if not timestamp(bound.submitted_at) <= timestamp(approval.issued_at) <= now:
            reasons.add('time_conflict')
        if (not timestamp(approval.valid_from) <= now < timestamp(approval.valid_until)
                or timestamp(approval.valid_from) < timestamp(bound.valid_from)
                or timestamp(approval.valid_until) > timestamp(bound.valid_until)):
            reasons.add('validity_conflict')
    if not candidate.requests:
        reasons.add('requests_missing')
    if by_id.keys() - covered:
        reasons.add('approval_missing')
    return _decision(reasons, candidate, evaluated_at, _candidate_digest(candidate))


def inspect_registry(candidate, *, evaluated_at):
    try:
        validate_timestamp_text(evaluated_at)
    except Exception:
        return _decision(('invalid_evaluation_time',))
    try:
        _bounded_candidate(candidate)
    except _Rejected as error:
        return _decision((error.reason,))
    except ValueError:
        return _decision(('invalid_input',))
    except Exception:
        return _decision(('evaluation_error',))
    try:
        timestamp(evaluated_at)
    except Exception:
        return _decision(('invalid_evaluation_time',))
    try:
        return _inspect(candidate, evaluated_at)
    except _Rejected as error:
        return _decision((error.reason,))
    except ValueError:
        return _decision(('invalid_input',))
    except Exception:
        return _decision(('evaluation_error',))


def revalidate_inspection(inspection, *, candidate, evaluated_at):
    # A: text-only guards; no datetime parsing or caller iteration.
    try:
        validate_timestamp_text(evaluated_at)
        _inspection_preflight(inspection)
    except Exception:
        return _decision(('invalid_decision',))
    # B/C: share the ordinary entry's resource boundary before result validation.
    try:
        _bounded_candidate(candidate)
    except _Rejected as error:
        return _decision((error.reason,))
    except ValueError:
        return _decision(('invalid_input',))
    except Exception:
        return _decision(('evaluation_error',))
    # D: parsing, result structure, semantic inspection and full content binding.
    try:
        inspection.__post_init__()
        expected = inspect_registry(candidate, evaluated_at=evaluated_at)
        if inspection.candidate_digest != expected.candidate_digest:
            return _decision(('candidate_mismatch',))
        if inspection != expected:
            return _decision(('context_mismatch',))
        return expected
    except Exception:
        return _decision(('invalid_decision',))
