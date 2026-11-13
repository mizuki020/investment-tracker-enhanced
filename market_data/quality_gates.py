"""Pure, fail-closed quality policy scaffold. No runtime authorization or I/O."""
from dataclasses import dataclass
from enum import Enum
from typing import Iterable

from market_data.snapshots import timestamp, validate_timestamp_text

POLICY_VERSION = "quality/1"


class Status(Enum):
    PASS = "PASS"
    BLOCK = "BLOCK"
    UNVERIFIED = "UNVERIFIED"


class Purpose(Enum):
    HISTORICAL_RESEARCH = "historical_research"
    VERIFIED_BACKTEST = "verified_backtest"
    ANALYZE = "analyze"
    STORE = "store"
    SEND_TO_EXTERNAL_AI = "send_to_external_ai"


class Action(Enum):
    ANALYZE = "analyze"
    STORE = "store"
    SEND_TO_EXTERNAL_AI = "send_to_external_ai"


class RightClaim(Enum):
    ALLOW = "allow"
    DENY = "deny"
    UNKNOWN = "unknown"


class Check(Enum):
    SCHEMA = "schema"
    COMPLETENESS = "completeness"
    CALENDAR = "calendar"
    MARKET_STATE = "market_state"
    FINALITY = "finality"
    FRESHNESS = "freshness"
    TIME_AUTHENTICITY = "time_authenticity"
    AS_OF = "as_of"
    RIGHTS_ANALYZE = "rights_analyze"
    RIGHTS_STORE = "rights_store"
    RIGHTS_EXTERNAL_AI = "rights_external_ai"


def required_checks(purpose: Purpose) -> frozenset[Check]:
    """No caller-supplied policy, subset override, or mutable public registry."""
    if type(purpose) is not Purpose:
        raise ValueError("unknown purpose")
    if purpose is Purpose.STORE:
        return frozenset((Check.SCHEMA, Check.COMPLETENESS, Check.RIGHTS_STORE))
    if purpose is Purpose.SEND_TO_EXTERNAL_AI:
        return frozenset((Check.SCHEMA, Check.COMPLETENESS, Check.RIGHTS_EXTERNAL_AI))
    common = frozenset((Check.SCHEMA, Check.COMPLETENESS, Check.CALENDAR,
                        Check.MARKET_STATE, Check.FINALITY, Check.AS_OF,
                        Check.RIGHTS_ANALYZE))
    if purpose is Purpose.HISTORICAL_RESEARCH:
        return common
    if purpose is Purpose.VERIFIED_BACKTEST:
        return common | frozenset((Check.TIME_AUTHENTICITY, Check.AS_OF))
    return common | frozenset((Check.FRESHNESS, Check.TIME_AUTHENTICITY, Check.AS_OF))


def _text(value):
    if type(value) is not str or not value.strip():
        raise ValueError("nonblank immutable string required")


@dataclass(frozen=True)
class CheckResult:
    check: Check
    status: Status
    reason_code: str
    target: str
    evidence_ids: tuple[str, ...]
    evaluated_at: str
    policy_version: str
    purpose: Purpose

    def __post_init__(self):
        validate_timestamp_text(self.evaluated_at)
        if type(self.check) is not Check or type(self.status) is not Status:
            raise ValueError("unknown check or status")
        if type(self.purpose) is not Purpose:
            raise ValueError("unknown purpose")
        for value in (self.reason_code, self.target, self.policy_version):
            _text(value)
        timestamp(self.evaluated_at)
        if type(self.evidence_ids) is not tuple:
            raise ValueError("evidence IDs must be immutable")
        for evidence in self.evidence_ids:
            _text(evidence)
        if len(set(self.evidence_ids)) != len(self.evidence_ids):
            raise ValueError("duplicate evidence IDs")


def combine_statuses(statuses: Iterable[Status]) -> Status:
    """Truth table only; PASS here is not a quality/rights authorization."""
    try:
        values = tuple(statuses)
        if any(type(s) is not Status for s in values):
            return Status.BLOCK
        if Status.BLOCK in values:
            return Status.BLOCK
        if not values or Status.UNVERIFIED in values:
            return Status.UNVERIFIED
        return Status.PASS
    except Exception:
        return Status.BLOCK


def _rights_check(action):
    if type(action) is not Action:
        raise ValueError("unknown action")
    return {Action.ANALYZE: Check.RIGHTS_ANALYZE,
            Action.STORE: Check.RIGHTS_STORE,
            Action.SEND_TO_EXTERNAL_AI: Check.RIGHTS_EXTERNAL_AI}[action]


def evaluate_rights(*, action: Action, claim: RightClaim,
                    contract_reference: str | None, purpose: Purpose,
                    target: str, evaluated_at: str,
                    policy_version: str = POLICY_VERSION) -> CheckResult:
    """A contract claim/reference never authenticates itself. No allow path yet."""
    validate_timestamp_text(evaluated_at)
    check = _rights_check(action)
    if contract_reference is not None:
        _text(contract_reference)
    if type(claim) is not RightClaim:
        raise ValueError("unknown right claim")
    required = required_checks(purpose)
    if policy_version != POLICY_VERSION or check not in required:
        status, reason = Status.BLOCK, "rights_context_mismatch"
    elif claim is RightClaim.DENY:
        status, reason = Status.BLOCK, "rights_denied"
    elif claim is RightClaim.UNKNOWN or contract_reference is None:
        status, reason = Status.UNVERIFIED, "contract_unverified"
    else:
        status, reason = Status.UNVERIFIED, "contract_authentication_not_implemented"
    return CheckResult(check, status, reason, target,
                       () if contract_reference is None else (contract_reference,),
                       evaluated_at, policy_version, purpose)


_ERROR_CODES = frozenset((
    "invalid_target", "invalid_evaluation_time", "unknown_purpose",
    "policy_version_mismatch", "invalid_check_type", "invalid_check_fields",
    "check_policy_version_mismatch", "purpose_mismatch", "target_mismatch",
    "evaluation_time_mismatch", "duplicate_check", "evaluation_error",
    "invalid_decision", "decision_context_mismatch",
))


def _safe_context(purpose, target, evaluated_at):
    """Retain only fields whose runtime types/formats were checked independently."""
    errors = []
    if type(target) is not str or not target.strip():
        target = None
        errors.append("invalid_target")
    try:
        validate_timestamp_text(evaluated_at)
        timestamp(evaluated_at)
    except Exception:
        evaluated_at = None
        errors.append("invalid_evaluation_time")
    if type(purpose) is not Purpose:
        purpose = None
        errors.append("unknown_purpose")
    return purpose, target, evaluated_at, tuple(sorted(errors))


@dataclass(frozen=True)
class GateDecision:
    status: Status
    reason_codes: tuple[str, ...]
    checks: tuple[CheckResult, ...]
    target: str | None
    evaluated_at: str | None
    purpose: Purpose | None
    policy_version: str = POLICY_VERSION

    def __post_init__(self):
        if self.evaluated_at is not None:
            validate_timestamp_text(self.evaluated_at)
        if type(self.status) is not Status or self.policy_version != POLICY_VERSION:
            raise ValueError("invalid decision status or policy")
        _text(self.policy_version)
        if type(self.reason_codes) is not tuple or type(self.checks) is not tuple:
            raise ValueError("decision collections must be immutable tuples")
        for code in self.reason_codes:
            _text(code)
        if not self.reason_codes or len(set(self.reason_codes)) != len(self.reason_codes):
            raise ValueError("decision requires unique reason codes")
        if self.target is not None:
            _text(self.target)
        if self.evaluated_at is not None:
            timestamp(self.evaluated_at)
        if self.purpose is not None and type(self.purpose) is not Purpose:
            raise ValueError("invalid decision purpose")
        # No required evaluator currently authenticates PASS. This remains an
        # explicit invariant even for direct construction, not just a factory rule.
        if self.status is Status.PASS:
            raise ValueError("PASS unavailable while required gates are unimplemented")
        if not self.checks:
            if self.status is not Status.BLOCK or not set(self.reason_codes) <= _ERROR_CODES:
                raise ValueError("empty decisions must be structured safety stops")
            return
        if self.target is None or self.evaluated_at is None or self.purpose is None:
            raise ValueError("non-diagnostic decision requires complete context")
        seen = set()
        for check in self.checks:
            if type(check) is not CheckResult:
                raise ValueError("invalid decision check")
            check.__post_init__()
            if (check.check in seen or check.target != self.target
                    or check.purpose is not self.purpose
                    or check.policy_version != self.policy_version
                    or timestamp(check.evaluated_at) != timestamp(self.evaluated_at)):
                raise ValueError("inconsistent decision checks")
            if check.status is Status.PASS:
                raise ValueError("unimplemented check cannot assert PASS")
            seen.add(check.check)
        if not required_checks(self.purpose) <= seen:
            raise ValueError("decision missing mandatory checks")
        if combine_statuses(c.status for c in self.checks) is not self.status:
            raise ValueError("decision status disagrees with checks")
        if set(self.reason_codes) != {c.reason_code for c in self.checks}:
            raise ValueError("decision reasons disagree with checks")

    @property
    def analysis_input_allowed(self):
        return False

    @property
    def orders_allowed(self):
        return False

    @property
    def verified_performance_allowed(self):
        return False


def aggregate_checks(*, purpose: Purpose, target: str, evaluated_at: str,
                     results: Iterable[CheckResult],
                     policy_version: str = POLICY_VERSION) -> GateDecision:
    """Validate context, add mandatory gates, and refuse unimplemented PASS claims.

    Calendar/schema/as-of adapters are not wired here. Rights claim handling is
    implemented, but contract authentication is not. Therefore no real purpose
    can currently return PASS, even if every caller-supplied result says PASS.
    """
    safe_purpose, safe_target, safe_time, errors = _safe_context(purpose, target, evaluated_at)
    def stop(*codes):
        return GateDecision(Status.BLOCK, tuple(sorted(set(codes))), (),
                            safe_target, safe_time, safe_purpose)
    if type(policy_version) is not str or policy_version != POLICY_VERSION:
        errors += ("policy_version_mismatch",)
    if errors:
        return stop(*errors)
    try:
        evaluation = timestamp(safe_time)
        required = required_checks(safe_purpose)
        supplied = tuple(results)
        seen = set()
        effective = []
        for result in supplied:
            if type(result) is not CheckResult:
                return stop("invalid_check_type")
            try:
                result.__post_init__()
            except Exception:
                return stop("invalid_check_fields")
            if result.policy_version != POLICY_VERSION:
                return stop("check_policy_version_mismatch")
            if result.purpose is not purpose:
                return stop("purpose_mismatch")
            if result.target != target:
                return stop("target_mismatch")
            if timestamp(result.evaluated_at) != evaluation:
                return stop("evaluation_time_mismatch")
            if result.check in seen:
                return stop("duplicate_check")
            seen.add(result.check)
            # Non-PASS assertions may conservatively stop work, but cannot grant it.
            if result.status is Status.PASS:
                reason = ("contract_authentication_not_implemented" if result.check in
                          {Check.RIGHTS_ANALYZE, Check.RIGHTS_STORE, Check.RIGHTS_EXTERNAL_AI}
                          else "check_not_implemented")
                result = CheckResult(result.check, Status.UNVERIFIED, reason, target,
                                     result.evidence_ids, evaluated_at, POLICY_VERSION, purpose)
            effective.append(result)
        for check in sorted(required - seen, key=lambda c: c.value):
            effective.append(CheckResult(check, Status.UNVERIFIED, "required_check_missing",
                                         target, (), evaluated_at, POLICY_VERSION, purpose))
        effective.sort(key=lambda r: r.check.value)
        status = combine_statuses(r.status for r in effective)
        return GateDecision(status, tuple(sorted({r.reason_code for r in effective})),
                            tuple(effective), target, evaluated_at, purpose)
    except Exception:
        # Never echo exception details or unvalidated caller metadata.
        return stop("evaluation_error")


def revalidate_decision(decision: GateDecision, *, purpose: Purpose, target: str,
                        evaluated_at: str,
                        policy_version: str = POLICY_VERSION) -> GateDecision:
    """Consumer boundary: validate structure/context and recompute, never trust status.

    Still grants no permissions. Future PASS support must use authenticated
    evaluators, not merely remove constructor restrictions or trust a marker.
    """
    context = aggregate_checks(purpose=purpose, target=target, evaluated_at=evaluated_at,
                               results=(), policy_version=policy_version)
    if context.status is Status.BLOCK:
        return context
    def stop(code):
        return GateDecision(Status.BLOCK, (code,), (), target, evaluated_at, purpose)
    try:
        if type(decision) is not GateDecision:
            return stop("invalid_decision")
        decision.__post_init__()
        if (decision.purpose is not purpose or decision.target != target
                or decision.policy_version != policy_version):
            return stop("decision_context_mismatch")
        # A validated diagnostic may deliberately omit a rejected timestamp.
        # Preserve that absence and its original reason; do not fill it with now.
        if not decision.checks and decision.evaluated_at is None:
            return decision
        if (decision.evaluated_at is None
                or timestamp(decision.evaluated_at) != timestamp(evaluated_at)):
            return stop("decision_context_mismatch")
        if not decision.checks:
            return decision  # Validated diagnostic BLOCK; never promote to UNVERIFIED.
        return aggregate_checks(purpose=purpose, target=target, evaluated_at=evaluated_at,
                                results=decision.checks, policy_version=policy_version)
    except Exception:
        return stop("invalid_decision")
