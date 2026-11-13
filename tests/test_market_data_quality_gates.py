"""Synthetic gate metadata only: no prices, credentials, network, or storage."""
from dataclasses import FrozenInstanceError, replace
from itertools import permutations
import unittest

from market_data.quality_gates import (
    POLICY_VERSION, Action, Check, CheckResult, Purpose, RightClaim, Status,
    GateDecision, aggregate_checks, combine_statuses, evaluate_rights, required_checks,
    revalidate_decision,
)

AT = "2026-01-05T18:00:00+09:00"
TARGET = "synthetic-snapshot-id"


def result(check=Check.SCHEMA, status=Status.PASS, purpose=Purpose.HISTORICAL_RESEARCH):
    return CheckResult(check, status, "synthetic_result", TARGET,
                       ("synthetic-evidence",), AT, POLICY_VERSION, purpose)


def aggregate(results=(), purpose=Purpose.HISTORICAL_RESEARCH, **changes):
    args = dict(purpose=purpose, target=TARGET, evaluated_at=AT, results=results)
    args.update(changes)
    return aggregate_checks(**args)


class StatusTests(unittest.TestCase):
    def test_complete_pass_truth_table(self):
        self.assertIs(combine_statuses((Status.PASS, Status.PASS)), Status.PASS)

    def test_block_precedes_unverified_for_all_orders(self):
        for values in permutations((Status.PASS, Status.BLOCK, Status.UNVERIFIED)):
            self.assertIs(combine_statuses(values), Status.BLOCK)

    def test_unverified_precedes_pass(self):
        self.assertIs(combine_statuses((Status.PASS, Status.UNVERIFIED)), Status.UNVERIFIED)

    def test_empty_is_not_pass(self):
        self.assertIs(combine_statuses(()), Status.UNVERIFIED)

    def test_unknown_states_are_blocked(self):
        for value in ["PASS", "unknown", None, True]:
            self.assertIs(combine_statuses((value,)), Status.BLOCK)

    def test_iterable_exception_is_blocked(self):
        def broken():
            yield Status.PASS
            raise RuntimeError("synthetic failure")
        self.assertIs(combine_statuses(broken()), Status.BLOCK)


class ResultTests(unittest.TestCase):
    def test_required_audit_fields_and_immutability(self):
        r = result()
        self.assertEqual((r.target, r.evaluated_at, r.policy_version), (TARGET, AT, POLICY_VERSION))
        self.assertTrue(r.reason_code)
        with self.assertRaises(FrozenInstanceError):
            r.status = Status.PASS

    def test_mutable_blank_or_duplicate_evidence_rejected(self):
        for value in [["proof"], (" ",), ("x", "x")]:
            with self.subTest(value=value), self.assertRaises(ValueError):
                replace(result(), evidence_ids=value)

    def test_unknown_state_check_and_purpose_rejected(self):
        for changes in [dict(status="PASS"), dict(check="schema"), dict(purpose="unknown")]:
            with self.subTest(changes=changes), self.assertRaises(ValueError):
                replace(result(), **changes)

    def test_naive_time_or_blank_reason_rejected(self):
        for changes in [dict(evaluated_at="2026-01-05T18:00:00"), dict(reason_code=" ")]:
            with self.assertRaises(ValueError):
                replace(result(), **changes)


class PolicyTests(unittest.TestCase):
    def test_required_sets_are_immutable_and_internal(self):
        for purpose in Purpose:
            checks = required_checks(purpose)
            self.assertIs(type(checks), frozenset)
            self.assertTrue(checks)
            with self.assertRaises(AttributeError):
                checks.clear()

    def test_research_cannot_remove_backtest_requirements(self):
        research = required_checks(Purpose.HISTORICAL_RESEARCH)
        verified = required_checks(Purpose.VERIFIED_BACKTEST)
        self.assertLess(research, verified)
        self.assertIn(Check.TIME_AUTHENTICITY, verified)
        self.assertIn(Check.AS_OF, research)

    def test_action_rights_are_separate(self):
        self.assertIn(Check.RIGHTS_STORE, required_checks(Purpose.STORE))
        self.assertNotIn(Check.RIGHTS_ANALYZE, required_checks(Purpose.STORE))
        self.assertIn(Check.RIGHTS_EXTERNAL_AI, required_checks(Purpose.SEND_TO_EXTERNAL_AI))
        self.assertIn(Check.FRESHNESS, required_checks(Purpose.ANALYZE))

    def test_unknown_purpose_and_subset_override_rejected(self):
        self.assertIs(aggregate(purpose="unknown").status, Status.BLOCK)
        with self.assertRaises(TypeError):
            aggregate(required_checks=())


class AggregationTests(unittest.TestCase):
    def test_empty_injects_all_missing_requirements(self):
        d = aggregate()
        self.assertIs(d.status, Status.UNVERIFIED)
        self.assertEqual({r.check for r in d.checks}, required_checks(d.purpose))
        self.assertEqual(set(d.reason_codes), {"required_check_missing"})

    def test_missing_check_is_unverified(self):
        d = aggregate((result(),))
        self.assertIs(d.status, Status.UNVERIFIED)
        self.assertIn("required_check_missing", d.reason_codes)

    def test_forged_all_pass_never_bypasses_unimplemented_checks(self):
        for purpose in Purpose:
            supplied = tuple(result(c, purpose=purpose) for c in required_checks(purpose))
            d = aggregate(supplied, purpose)
            self.assertIs(d.status, Status.UNVERIFIED)
            self.assertIn("check_not_implemented", d.reason_codes)
            self.assertIn("contract_authentication_not_implemented", d.reason_codes)

    def test_block_precedes_missing_and_unimplemented(self):
        self.assertIs(aggregate((result(status=Status.BLOCK),)).status, Status.BLOCK)

    def test_duplicate_check_blocks_even_identical_result(self):
        r = result()
        self.assertIs(aggregate((r, r)).status, Status.BLOCK)

    def test_policy_mismatch_blocks(self):
        self.assertIs(aggregate(policy_version="quality/2").status, Status.BLOCK)
        self.assertIs(aggregate((replace(result(), policy_version="quality/2"),)).status, Status.BLOCK)

    def test_scope_time_and_research_promotion_blocked(self):
        for r in [replace(result(), target="other-snapshot"),
                  replace(result(), evaluated_at="2026-01-05T18:00:01+09:00"),
                  replace(result(), evaluated_at="2026-01-05T17:59:59+09:00")]:
            self.assertIs(aggregate((r,)).status, Status.BLOCK)
        self.assertIs(aggregate((result(),), Purpose.VERIFIED_BACKTEST).status, Status.BLOCK)

    def test_equivalent_timezones_accepted_without_grant(self):
        d = aggregate((replace(result(), evaluated_at="2026-01-05T09:00:00Z"),))
        self.assertIs(d.status, Status.UNVERIFIED)

    def test_known_extra_check_cannot_replace_required_checks(self):
        d = aggregate((result(Check.RIGHTS_STORE),))
        self.assertIs(d.status, Status.UNVERIFIED)
        self.assertIn(Check.RIGHTS_ANALYZE, {r.check for r in d.checks})
        self.assertIn("required_check_missing", d.reason_codes)

    def test_malformed_inputs_and_iterator_exceptions_block(self):
        def broken():
            yield result()
            raise RuntimeError("do not echo this synthetic detail")
        for values, code in [((None,), "invalid_check_type"),
                             (("PASS",), "invalid_check_type"),
                             (broken(), "evaluation_error")]:
            d = aggregate(values)
            self.assertIs(d.status, Status.BLOCK)
            self.assertEqual(d.reason_codes, (code,))
        self.assertIs(aggregate(target=" ").status, Status.BLOCK)
        self.assertIs(aggregate(evaluated_at="invalid").status, Status.BLOCK)

    def test_results_are_order_independent_and_inputs_unchanged(self):
        a, b = result(), result(Check.COMPLETENESS, Status.BLOCK)
        self.assertEqual(aggregate((a, b)), aggregate((b, a)))
        self.assertIs(a.status, Status.PASS)

    def test_no_analysis_orders_or_verified_performance_permissions(self):
        for purpose in Purpose:
            d = aggregate(purpose=purpose)
            self.assertFalse(d.analysis_input_allowed)
            self.assertFalse(d.orders_allowed)
            self.assertFalse(d.verified_performance_allowed)
        with self.assertRaises((AttributeError, FrozenInstanceError)):
            d.orders_allowed = True


class RightsTests(unittest.TestCase):
    def rights(self, action=Action.ANALYZE, purpose=Purpose.HISTORICAL_RESEARCH,
               claim=RightClaim.ALLOW, reference="synthetic-contract"):
        return evaluate_rights(action=action, claim=claim, contract_reference=reference,
                               purpose=purpose, target=TARGET, evaluated_at=AT)

    def test_all_action_allow_claims_remain_unverified(self):
        for action, purpose in [(Action.ANALYZE, Purpose.HISTORICAL_RESEARCH),
                                (Action.STORE, Purpose.STORE),
                                (Action.SEND_TO_EXTERNAL_AI, Purpose.SEND_TO_EXTERNAL_AI)]:
            r = self.rights(action, purpose)
            self.assertIs(r.status, Status.UNVERIFIED)
            self.assertEqual(r.reason_code, "contract_authentication_not_implemented")

    def test_denial_blocks_even_without_reference(self):
        r = self.rights(claim=RightClaim.DENY, reference=None)
        self.assertIs(r.status, Status.BLOCK)

    def test_unknown_or_missing_contract_never_permits(self):
        for claim, ref in [(RightClaim.UNKNOWN, "synthetic-contract"), (RightClaim.ALLOW, None)]:
            self.assertIs(self.rights(claim=claim, reference=ref).status, Status.UNVERIFIED)

    def test_cross_action_permission_does_not_transfer(self):
        self.assertIs(self.rights(Action.ANALYZE, Purpose.STORE).status, Status.BLOCK)
        self.assertIs(self.rights(Action.STORE, Purpose.SEND_TO_EXTERNAL_AI).status, Status.BLOCK)

    def test_unknown_action_claim_or_mutable_reference_rejected(self):
        for changes in [dict(action="analyze"), dict(claim="allow"), dict(reference=["contract"]),
                        dict(reference=" ")]:
            with self.assertRaises(ValueError):
                self.rights(**changes)

    def test_acquisition_success_is_not_contract_evidence(self):
        r = self.rights(reference="HTTP-200")
        self.assertIs(r.status, Status.UNVERIFIED)
        d = aggregate((r,))
        self.assertIsNot(d.status, Status.PASS)

    def test_rights_policy_version_mismatch_blocks(self):
        r = evaluate_rights(action=Action.ANALYZE, claim=RightClaim.ALLOW,
                            contract_reference="synthetic-contract", purpose=Purpose.ANALYZE,
                            target=TARGET, evaluated_at=AT, policy_version="quality/other")
        self.assertIs(r.status, Status.BLOCK)


class DecisionAuditRegressionTests(unittest.TestCase):
    def test_direct_empty_pass_is_rejected(self):
        with self.assertRaises(ValueError):
            GateDecision(Status.PASS, (), (), TARGET, AT, Purpose.ANALYZE)

    def test_mutable_decision_collections_are_rejected(self):
        for reasons, checks in [([], ()), ((), []), ([], [])]:
            with self.subTest(reasons=reasons, checks=checks), self.assertRaises(ValueError):
                GateDecision(Status.UNVERIFIED, reasons, checks, TARGET, AT, Purpose.ANALYZE)

    def test_valid_context_survives_invalid_check(self):
        d = aggregate((None,))
        self.assertIs(d.status, Status.BLOCK)
        self.assertEqual((d.target, d.evaluated_at, d.purpose),
                         (TARGET, AT, Purpose.HISTORICAL_RESEARCH))

    def test_duplicate_and_scope_errors_have_distinct_safe_codes(self):
        r = result()
        duplicate = aggregate((r, r))
        mismatch = aggregate((replace(r, target="other"),))
        self.assertEqual(duplicate.reason_codes, ("duplicate_check",))
        self.assertEqual(mismatch.reason_codes, ("target_mismatch",))

    def test_direct_unknown_types_states_and_metadata_rejected(self):
        d = aggregate()
        for changes in [dict(status="PASS"), dict(purpose="analyze"),
                        dict(target=[]), dict(evaluated_at="invalid"),
                        dict(policy_version="quality/other"), dict(reason_codes=(" ",))]:
            with self.subTest(changes=changes), self.assertRaises(ValueError):
                replace(d, **changes)

    def test_direct_missing_required_checks_rejected(self):
        r = result(status=Status.UNVERIFIED)
        with self.assertRaises(ValueError):
            GateDecision(Status.UNVERIFIED, (r.reason_code,), (r,), TARGET, AT, r.purpose)

    def test_direct_complete_self_asserted_pass_still_rejected(self):
        checks = tuple(result(c) for c in required_checks(Purpose.HISTORICAL_RESEARCH))
        with self.assertRaises(ValueError):
            GateDecision(Status.PASS, ("synthetic_result",), checks, TARGET, AT,
                         Purpose.HISTORICAL_RESEARCH)

    def test_direct_status_or_reason_mismatch_rejected(self):
        d = aggregate()
        for changes in [dict(status=Status.BLOCK), dict(reason_codes=("invented_reason",))]:
            with self.assertRaises(ValueError):
                replace(d, **changes)

    def test_direct_duplicates_and_context_mix_rejected(self):
        d = aggregate()
        with self.assertRaises(ValueError):
            replace(d, checks=d.checks + (d.checks[0],))
        for changes in [dict(target="other"), dict(purpose=Purpose.ANALYZE),
                        dict(evaluated_at="2026-01-05T18:00:01+09:00"),
                        dict(policy_version="quality/other")]:
            with self.subTest(changes=changes), self.assertRaises(ValueError):
                replace(d, checks=(replace(d.checks[0], **changes),) + d.checks[1:])

    def test_normal_result_collections_and_evidence_cannot_change(self):
        d = aggregate()
        self.assertIs(type(d.checks), tuple)
        self.assertIs(type(d.reason_codes), tuple)
        with self.assertRaises(AttributeError):
            d.reason_codes.append("changed")
        with self.assertRaises(FrozenInstanceError):
            d.checks[0].evidence_ids = ("changed",)

    def test_invalid_context_fields_are_independently_redacted(self):
        invalid_target = aggregate((None,), target={"unsafe": "value"})
        self.assertIsNone(invalid_target.target)
        self.assertEqual(invalid_target.evaluated_at, AT)
        self.assertIs(invalid_target.purpose, Purpose.HISTORICAL_RESEARCH)
        invalid_time = aggregate((None,), evaluated_at="invalid")
        self.assertEqual(invalid_time.target, TARGET)
        self.assertIsNone(invalid_time.evaluated_at)
        invalid_purpose = aggregate((None,), purpose="unknown")
        self.assertIsNone(invalid_purpose.purpose)
        self.assertEqual(invalid_purpose.target, TARGET)
        self.assertEqual(invalid_purpose.evaluated_at, AT)

    def test_safe_error_codes_for_version_purpose_time_and_type(self):
        for r, code in [(replace(result(), policy_version="quality/other"), "check_policy_version_mismatch"),
                        (replace(result(), purpose=Purpose.ANALYZE), "purpose_mismatch"),
                        (replace(result(), evaluated_at="2026-01-05T09:00:01Z"), "evaluation_time_mismatch")]:
            self.assertEqual(aggregate((r,)).reason_codes, (code,))
        self.assertEqual(aggregate(policy_version="unknown").reason_codes,
                         ("policy_version_mismatch",))

    def test_iterator_failure_keeps_valid_context_without_exception_text(self):
        def broken():
            raise RuntimeError("unsafe exception text")
            yield
        d = aggregate(broken())
        self.assertEqual((d.target, d.evaluated_at, d.purpose),
                         (TARGET, AT, Purpose.HISTORICAL_RESEARCH))
        self.assertEqual(d.reason_codes, ("evaluation_error",))
        self.assertNotIn("unsafe", repr(d))

    def test_boundary_recomputes_normal_block_and_unverified(self):
        for d in [aggregate(), aggregate((result(status=Status.BLOCK),))]:
            checked = revalidate_decision(d, purpose=d.purpose, target=TARGET, evaluated_at=AT)
            self.assertEqual(checked, d)
            self.assertFalse(checked.analysis_input_allowed)
            self.assertFalse(checked.verified_performance_allowed)
            self.assertFalse(checked.orders_allowed)

    def test_boundary_refuses_constructor_bypass_and_wrong_result_type(self):
        d = aggregate()
        object.__setattr__(d, "status", Status.PASS)
        for invalid in [d, {"status": "PASS"}, None]:
            checked = revalidate_decision(invalid, purpose=Purpose.HISTORICAL_RESEARCH,
                                           target=TARGET, evaluated_at=AT)
            self.assertIs(checked.status, Status.BLOCK)
            self.assertEqual(checked.reason_codes, ("invalid_decision",))

    def test_boundary_rejects_context_transfer_and_unknown_policy(self):
        d = aggregate()
        for args in [dict(purpose=Purpose.VERIFIED_BACKTEST), dict(target="other"),
                     dict(evaluated_at="2026-01-05T18:00:01+09:00"),
                     dict(policy_version="quality/other")]:
            context = dict(purpose=d.purpose, target=TARGET, evaluated_at=AT)
            context.update(args)
            self.assertIs(revalidate_decision(d, **context).status, Status.BLOCK)

    def test_boundary_preserves_diagnostic_block_without_promotion(self):
        d = aggregate((None,))
        checked = revalidate_decision(d, purpose=d.purpose, target=TARGET, evaluated_at=AT)
        self.assertEqual(checked, d)
        self.assertIs(checked.status, Status.BLOCK)

    def test_direct_empty_diagnostic_requires_allowlisted_error(self):
        with self.assertRaises(ValueError):
            GateDecision(Status.BLOCK, ("caller_invented_error",), (), TARGET, AT, Purpose.ANALYZE)


if __name__ == "__main__":
    unittest.main()
