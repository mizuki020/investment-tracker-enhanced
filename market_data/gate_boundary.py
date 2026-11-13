"""Pure typed gate handoff; diagnostics are retained, not flattened into checks."""
from dataclasses import dataclass

from market_data.completeness import Inspection
from market_data.snapshots import timestamp
from market_data.quality_gates import (
    GateDecision, Status, Purpose, POLICY_VERSION, aggregate_checks, revalidate_decision,
)


@dataclass(frozen=True)
class BoundaryOutcome:
    decision: GateDecision
    upstream: Inspection | GateDecision | None

    def __post_init__(self):
        if type(self.decision) is not GateDecision:
            raise ValueError("validated decision required")
        self.decision.__post_init__()
        if self.upstream is None:
            if self.decision.status is not Status.BLOCK:
                raise ValueError("missing upstream must block")
        elif type(self.upstream) in (Inspection, GateDecision):
            self.upstream.__post_init__()
            blocked = (self.upstream.status is Status.BLOCK if type(self.upstream) is GateDecision
                       else any(c.status is Status.BLOCK for c in self.upstream.checks))
            if blocked and self.decision.status is not Status.BLOCK:
                raise ValueError("upstream BLOCK cannot be promoted")
            if self.decision.status is not Status.BLOCK:
                source = (self.upstream if type(self.upstream) is GateDecision
                          else self.upstream.checks[0])
                if (source.target != self.decision.target or source.purpose is not self.decision.purpose
                        or source.policy_version != self.decision.policy_version
                        or source.evaluated_at is None or self.decision.evaluated_at is None
                        or timestamp(source.evaluated_at) != timestamp(self.decision.evaluated_at)):
                    raise ValueError("unblocked boundary context must match upstream")
        else:
            raise ValueError("unvalidated or mutable upstream")

    @property
    def status(self):
        return self.decision.status

    @property
    def reason_codes(self):
        codes = set(self.decision.reason_codes)
        if type(self.upstream) is GateDecision and self.upstream.status is Status.BLOCK:
            codes.update(self.upstream.reason_codes)
        elif type(self.upstream) is Inspection:
            codes.update(f.reason for f in self.upstream.findings if f.status is Status.BLOCK)
        return tuple(sorted(codes))

    @property
    def analysis_input_allowed(self):
        return False

    @property
    def verified_performance_allowed(self):
        return False

    @property
    def orders_allowed(self):
        return False


def route_gate_result(upstream: Inspection | GateDecision, *, purpose: Purpose,
                      target: str, evaluated_at: str,
                      policy_version: str = POLICY_VERSION) -> BoundaryOutcome:
    """Require the complete typed object. Bare checks/iterators are invalid input.

    Expected context is guarded before inspecting upstream. Invalid context
    returns BLOCK without retaining unvalidated objects. No provenance flag or
    self-asserted PASS can grant permissions.
    """
    context = aggregate_checks(purpose=purpose, target=target, evaluated_at=evaluated_at,
                               results=(), policy_version=policy_version)
    if context.status is Status.BLOCK:
        return BoundaryOutcome(context, None)
    try:
        if type(upstream) not in (Inspection, GateDecision):
            raise ValueError("complete typed upstream required")
        upstream.__post_init__()
        if type(upstream) is GateDecision:
            decision = revalidate_decision(upstream, purpose=purpose, target=target,
                                           evaluated_at=evaluated_at, policy_version=policy_version)
        else:
            decision = aggregate_checks(purpose=purpose, target=target, evaluated_at=evaluated_at,
                                        results=upstream.checks, policy_version=policy_version)
            decision = revalidate_decision(decision, purpose=purpose, target=target,
                                           evaluated_at=evaluated_at, policy_version=policy_version)
        return BoundaryOutcome(decision, upstream)
    except Exception:
        decision = GateDecision(Status.BLOCK, ("invalid_decision",), (),
                                target, evaluated_at, purpose)
        return BoundaryOutcome(decision, None)
