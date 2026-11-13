"""Bounded, synthetic-first evidence inspection. Never authenticates PASS or does I/O."""
from dataclasses import dataclass, fields, asdict
import json
import re
from market_data.snapshots import timestamp, validate_timestamp_text, trade_day
from market_data.quality_gates import Status
from market_data.trust_policy import (
    TrustClaim, text, finite_tuple, MAX_EVIDENCES, MAX_EVIDENCE_BYTES,
    MAX_TOTAL_BYTES, MAX_TARGET_VERSIONS,
)

POLICY_VERSION = 'authenticity/1'
REASONS = frozenset((
    'invalid_input','invalid_evaluation_time','evaluation_error','evidence_missing',
    'trust_registration_unimplemented','verification_unimplemented','target_mismatch',
    'duplicate_evidence','evidence_time_conflict','evidence_not_current',
    'replacement_conflict','replacement_time_conflict','replacement_unverified',
    'resource_limit','context_mismatch',
    'invalid_decision',
))
BLOCK_REASONS = REASONS - frozenset((
    'evidence_missing','trust_registration_unimplemented','verification_unimplemented',
    'replacement_unverified',
))


@dataclass(frozen=True)
class Target:
    code: str
    market: str
    start: str
    end: str
    price_basis: str
    data_version: str
    raw_digest: str
    normalized_digest: str
    normalization_id: str
    normalization_version: str

    def __post_init__(self):
        for f in fields(self):text(getattr(self,f.name))
        if self.price_basis not in ('unadjusted','adjusted'):
            raise ValueError('invalid price basis')
        if trade_day(self.start)>trade_day(self.end):raise ValueError('invalid date range')
        for digest in (self.raw_digest,self.normalized_digest):
            if not re.fullmatch('[0-9a-f]{64}',digest):raise ValueError('invalid sha256 digest')


def _target(value):
    if type(value) is not Target:raise ValueError('exact Target required')
    value.__post_init__()


@dataclass(frozen=True)
class Evidence:
    schema_version: str
    evidence_id: str
    issuer: str
    kind: str
    target: Target
    issued_at: str
    valid_from: str
    valid_until: str
    corrects: str | None = None
    replaces: str | None = None
    payload: bytes = b''

    def __post_init__(self):
        # Text/type budgets before parsing or encoding; no user iterators.
        for v in (self.issued_at,self.valid_from,self.valid_until):validate_timestamp_text(v)
        for v in (self.schema_version,self.evidence_id,self.issuer,self.kind):text(v)
        for v in (self.corrects,self.replaces):
            if v is not None:text(v)
        if type(self.payload) is not bytes or len(self.payload)>MAX_EVIDENCE_BYTES:
            raise ValueError('invalid bounded bytes')
        _target(self.target)
        if self.schema_version!='evidence/1':raise ValueError('unsupported evidence schema')
        if self.kind not in ('receipt','provider_attestation','calendar','market_state','time'):
            raise ValueError('unsupported evidence kind')
        if timestamp(self.valid_from)>=timestamp(self.valid_until):raise ValueError('invalid evidence period')
        timestamp(self.issued_at)


def evidence_from_mapping(value):
    """Optional strict mapping adapter, not an unbounded JSON parser."""
    if type(value) is not dict or len(value)>len(fields(Evidence)):
        raise ValueError('exact bounded dictionary required')
    names={f.name for f in fields(Evidence)}
    for key in value:
        if type(key) is not str or key not in names:raise ValueError('unknown evidence field')
    try:
        result=Evidence(**value)
    except (TypeError,ValueError):
        raise ValueError('invalid evidence mapping') from None
    return result


def evidence_size(evidence):
    """UTF-8 canonical metadata bytes plus opaque payload bytes; never decode payload."""
    if type(evidence) is not Evidence:raise ValueError('exact Evidence required')
    evidence.__post_init__()
    metadata={f.name:getattr(evidence,f.name) for f in fields(Evidence) if f.name!='payload'}
    metadata['target']=asdict(evidence.target)
    return len(json.dumps(metadata,sort_keys=True,separators=(',',':'),ensure_ascii=False).encode('utf-8'))+len(evidence.payload)


@dataclass(frozen=True)
class AuthenticityDecision:
    status: Status
    reasons: tuple[str, ...]
    target: Target | None
    evaluated_at: str | None
    policy_version: str = POLICY_VERSION

    def __post_init__(self):
        if type(self.status) is not Status or self.status is Status.PASS:
            raise ValueError('PASS is unavailable')
        if type(self.policy_version) is not str or self.policy_version!=POLICY_VERSION:
            raise ValueError('unsupported decision policy')
        finite_tuple(self.reasons,len(REASONS))
        if not self.reasons or any(type(r) is not str or r not in REASONS for r in self.reasons):
            raise ValueError('invalid diagnostic reasons')
        if self.reasons!=tuple(sorted(set(self.reasons))):raise ValueError('noncanonical reasons')
        if (self.status is Status.BLOCK)!=bool(set(self.reasons)&BLOCK_REASONS):
            raise ValueError('inconsistent severity')
        if self.target is not None:_target(self.target)
        if self.evaluated_at is not None:timestamp(self.evaluated_at)
        if self.status is Status.UNVERIFIED and (self.target is None or self.evaluated_at is None):
            raise ValueError('missing decision context')

    @property
    def analysis_input_allowed(self):return False
    @property
    def verified_performance_allowed(self):return False
    @property
    def orders_allowed(self):return False


def _decision(reasons,target,time):
    codes=tuple(sorted(set(reasons)))
    return AuthenticityDecision(Status.BLOCK if set(codes)&BLOCK_REASONS else Status.UNVERIFIED,
                                codes,target,time)


def _inspect(target,evidences,trust_claims,evaluated_at,target_versions):
    reasons={'trust_registration_unimplemented','verification_unimplemented'}
    now=timestamp(evaluated_at)
    # Explicit version tuple budget, independent of the evidence-count budget.
    for version in target_versions:_target(version)
    for claim in trust_claims:
        if type(claim) is not TrustClaim:raise ValueError('invalid trust claim')
        claim.__post_init__()  # Still unapproved, including a claimed revocation.
    seen=set();total=0
    for evidence in evidences:
        if type(evidence) is not Evidence:raise ValueError('invalid evidence')
        evidence.__post_init__()
        size=evidence_size(evidence)
        total+=size
        if size>MAX_EVIDENCE_BYTES or total>MAX_TOTAL_BYTES:
            reasons.add('resource_limit')
        if evidence.target!=target:reasons.add('target_mismatch')
        if evidence.evidence_id in seen:reasons.add('duplicate_evidence')
        seen.add(evidence.evidence_id)
        if timestamp(evidence.issued_at)>now:reasons.add('evidence_time_conflict')
        if not timestamp(evidence.valid_from)<=now<timestamp(evidence.valid_until):
            reasons.add('evidence_not_current')
        for reference in (evidence.corrects,evidence.replaces):
            if reference==evidence.evidence_id:reasons.add('replacement_conflict')
            elif reference is not None:reasons.add('replacement_unverified')
    # Compare claims only after every evidence has passed structural/time checks.
    # Duplicate IDs already BLOCK; no chosen duplicate can make the result pass.
    by_id={e.evidence_id:e for e in evidences}
    for evidence in evidences:
        if (evidence.corrects is not None and evidence.replaces is not None
                and evidence.corrects != evidence.replaces):
            reasons.add('replacement_conflict')
        for reference in (evidence.corrects,evidence.replaces):
            predecessor=by_id.get(reference)
            if predecessor is not None and evidence.target == predecessor.target:
                if timestamp(evidence.issued_at) <= timestamp(predecessor.issued_at):
                    reasons.add('replacement_time_conflict')
    # A matching corrects/replaces pair is one edge, not two branching paths.
    # Detect reference cycles without unbounded recursion.
    edges={e.evidence_id:tuple(dict.fromkeys(
        x for x in (e.corrects,e.replaces) if x is not None)) for e in evidences}
    for node in edges:
        pending=[(node,frozenset())];steps=0
        while pending:
            current,path=pending.pop();steps+=1
            if current in path:
                reasons.add('replacement_conflict');break
            if steps>MAX_EVIDENCES*MAX_EVIDENCES:
                reasons.add('resource_limit');break
            pending.extend((n,path|{current}) for n in edges.get(current,()))
    if not evidences:reasons.add('evidence_missing')
    return _decision(reasons,target,evaluated_at)


def evaluate_authenticity(*,target,evidences,trust_claims,evaluated_at,target_versions=()):
    """No callbacks, signature verification, network, registration or global gate wiring."""
    try:validate_timestamp_text(evaluated_at)
    except Exception:return _decision(('invalid_evaluation_time',),None,None)
    try:
        # All count/payload budgets before child validation, encoding and datetime parsing.
        for values,limit in ((evidences,MAX_EVIDENCES),(trust_claims,MAX_EVIDENCES),
                             (target_versions,MAX_TARGET_VERSIONS)):
            if type(values) is not tuple:raise ValueError('exact tuple required')
            if len(values)>limit:return _decision(('resource_limit',),None,None)
        total_payload=0
        for e in evidences:
            if type(e) is not Evidence or type(e.payload) is not bytes:raise ValueError('invalid evidence')
            if len(e.payload)>MAX_EVIDENCE_BYTES:return _decision(('resource_limit',),None,None)
            total_payload+=len(e.payload)
        if total_payload>MAX_TOTAL_BYTES:return _decision(('resource_limit',),None,None)
        # Eager bounded text checks for all timestamps before parsing any of them.
        for e in evidences:
            for value in (e.issued_at,e.valid_from,e.valid_until):validate_timestamp_text(value)
        for c in trust_claims:
            if type(c) is not TrustClaim:raise ValueError('invalid trust claim')
            for value in (c.valid_from,c.valid_until):validate_timestamp_text(value)
        _target(target)
        timestamp(evaluated_at)
    except Exception:return _decision(('invalid_input',),None,None)
    try:return _inspect(target,evidences,trust_claims,evaluated_at,target_versions)
    except ValueError:return _decision(('invalid_input',),target,evaluated_at)
    except Exception:return _decision(('evaluation_error',),target,evaluated_at)


def revalidate(decision,*,target,evaluated_at):
    """Structural/contextual rejection only; no result becomes authenticated evidence."""
    try:
        validate_timestamp_text(evaluated_at)
        timestamp(evaluated_at)
        _target(target)
        if type(decision) is not AuthenticityDecision:raise ValueError('invalid decision')
        decision.__post_init__()
        if decision.target!=target or decision.evaluated_at is None or timestamp(decision.evaluated_at)!=timestamp(evaluated_at):
            return _decision(('context_mismatch',),target,evaluated_at)
        return decision
    except Exception:return _decision(('invalid_decision',),None,None)
