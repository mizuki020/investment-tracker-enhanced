"""Synthetic-only tests. No API, persistence, or real market values."""
from dataclasses import FrozenInstanceError, replace
from copy import deepcopy
import json
import unittest

from market_data.snapshots import (
    AcquisitionManifest, BarVersion, Snapshot, TimeEvidence,
    compare_snapshots, select_as_of,
)


def bar(**changes):
    published = TimeEvidence("2026-01-05T16:00:00+09:00", "verified", "synthetic-publication")
    available = TimeEvidence("2026-01-05T17:00:00+09:00", "verified", "synthetic-contract")
    return replace(BarVersion(
        provider="synthetic", code="TEST", trade_date="2026-01-05",
        open="100", high="110", low="90", close="105", volume=1000,
        adjustment_factor="1", published_at=published, available_at=available,
        first_observed_at="2026-01-05T18:00:00+09:00",
        retrieved_at="2026-01-06T18:00:00+09:00"), **changes)


def snapshot(bars, **changes):
    manifest = replace(AcquisitionManifest(
        acquisition_id="synthetic-acquisition", provider="synthetic", code="TEST",
        requested_from="2026-01-05", requested_to="2026-01-06",
        retrieved_at="2026-01-10T18:00:00+09:00", complete=True), **changes)
    return Snapshot(manifest, tuple(bars))


class SchemaTests(unittest.TestCase):
    def test_versioned_json_and_detached_immutable_schema(self):
        s = snapshot([bar()])
        data = s.to_dict()
        self.assertEqual(json.loads(json.dumps(data))["schema_version"], "snapshot/1")
        self.assertEqual(data["manifest"]["schema_version"], "acquisition/1")
        data["bars"][0]["close"] = "999"
        self.assertEqual(s.bars[0].close, "105")
        with self.assertRaises(FrozenInstanceError):
            s.bars[0].close = "999"

    def test_unknown_times_stay_null(self):
        b = bar(published_at=TimeEvidence(), available_at=TimeEvidence())
        self.assertIsNone(b.published_at.value)
        self.assertIsNone(b.available_at.value)

    def test_evidence_requires_timezone_value_and_source(self):
        for args in [("2026-01-05T12:00:00", "unverified", None),
                     (None, "verified", "source"),
                     ("2026-01-05T12:00:00Z", "verified", None),
                     ("2026-01-05T12:00:00Z", "unknown", None)]:
            with self.subTest(args=args), self.assertRaises(ValueError):
                TimeEvidence(*args)

    def test_invalid_ohlcv_and_factor(self):
        for changes in [dict(close="NaN"), dict(high="99"), dict(volume=-1),
                        dict(volume=True), dict(adjustment_factor="0"),
                        dict(price_basis="mixed")]:
            with self.subTest(changes=changes), self.assertRaises(ValueError):
                bar(**changes)

    def test_invalid_time_order(self):
        for changes in [dict(first_observed_at="2026-01-07T18:00:00+09:00"),
                        dict(available_at=TimeEvidence("2026-01-05T15:00:00+09:00", "verified", "s")),
                        dict(published_at=TimeEvidence("2026-01-04T18:00:00+09:00", "verified", "s"))]:
            with self.subTest(changes=changes), self.assertRaises(ValueError):
                bar(**changes)

    def test_manifest_scope_version_and_completion_validation(self):
        for changes in [dict(code="OTHER"), dict(requested_to="2026-01-04"),
                        dict(retrieved_at="2026-01-05T18:00:00+09:00"),
                        dict(schema_version="acquisition/2"), dict(complete="yes")]:
            with self.subTest(changes=changes), self.assertRaises(ValueError):
                snapshot([bar()], **changes)
        with self.assertRaises(ValueError):
            Snapshot(snapshot([]).manifest, [])


class ComparisonTests(unittest.TestCase):
    def test_reacquisition_ignores_decimal_format_and_observation_metadata(self):
        old = snapshot([bar()])
        new = snapshot([bar(close="105.000", adjustment_factor="1.0",
                            retrieved_at="2026-01-07T18:00:00+09:00")], acquisition_id="next")
        result = compare_snapshots(old, new)
        self.assertEqual(len(result["unchanged"]), 1)
        self.assertEqual(result["revised"], [])

    def test_price_or_factor_revision(self):
        for changes in [dict(close="106"), dict(adjustment_factor="0.5")]:
            with self.subTest(changes=changes):
                result = compare_snapshots(snapshot([bar()]), snapshot([bar(**changes)]))
                self.assertEqual(len(result["revised"]), 1)

    def test_missing_is_not_deletion_and_incomplete_flag(self):
        result = compare_snapshots(snapshot([bar()]), snapshot([], complete=False))
        self.assertEqual(len(result["missing"]), 1)
        self.assertFalse(result["complete"])

    def test_added(self):
        self.assertEqual(len(compare_snapshots(snapshot([]), snapshot([bar()]))["added"]), 1)

    def test_high_precision_content_is_not_rounded_in_hash(self):
        a = bar(close="105.00000000000000000000000000001")
        b = bar(close="105.00000000000000000000000000002")
        self.assertNotEqual(a.content_hash, b.content_hash)

    def test_duplicates_in_either_input_are_reported(self):
        for old, new in [([bar(), bar()], [bar()]), ([bar()], [bar(), bar(close="106")])]:
            result = compare_snapshots(snapshot(old), snapshot(new))
            self.assertEqual(len(result["duplicates"]), 1)
            self.assertEqual(result["unchanged"], [])
            self.assertEqual(result["revised"], [])

    def test_different_ranges_rejected_without_mutation(self):
        old, new = snapshot([bar()]), snapshot([bar()], requested_to="2026-01-07")
        before = deepcopy((old, new))
        with self.assertRaises(ValueError):
            compare_snapshots(old, new)
        self.assertEqual((old, new), before)


class AsOfTests(unittest.TestCase):
    def select(self, bars, decision="2026-01-05T18:00:00+09:00", mode="verified_backtest"):
        return select_as_of(tuple(bars), decision_at=decision, mode=mode)

    def test_exact_boundary_and_utc_equivalence(self):
        a = self.select([bar()])
        self.assertEqual(a, self.select([bar()], decision="2026-01-05T09:00:00Z"))
        self.assertTrue(a.verified_backtest_eligible)
        self.assertEqual(len(a.bars), 1)

    def test_future_observation_blocked_despite_old_publication(self):
        result = self.select([bar()], decision="2026-01-05T17:59:59+09:00")
        self.assertEqual(result.bars, ())
        self.assertFalse(result.verified_backtest_eligible)
        self.assertEqual(result.excluded[0][1], "future_version")

    def test_unknown_availability_research_only(self):
        b = bar(available_at=TimeEvidence())
        research = self.select([b], mode="historical_research")
        self.assertEqual(research.bars, (b,))
        self.assertFalse(research.verified_backtest_eligible)
        verified = self.select([b])
        self.assertEqual(verified.bars, ())
        self.assertFalse(verified.verified_backtest_eligible)

    def test_unverified_claim_not_promoted(self):
        b = bar(available_at=TimeEvidence("2026-01-05T17:00:00+09:00", "unverified", "claim"))
        self.assertEqual(self.select([b]).bars, ())

    def test_research_mode_is_never_verified_performance(self):
        result = self.select([bar()], mode="historical_research")
        self.assertEqual(len(result.bars), 1)
        self.assertFalse(result.verified_backtest_eligible)

    def test_revision_never_leaks_backwards(self):
        old = bar()
        revised = bar(close="106", first_observed_at="2026-01-06T18:00:00+09:00")
        self.assertEqual(self.select([revised, old]).bars, (old,))
        later = self.select([old, revised], decision="2026-01-06T18:00:00+09:00")
        self.assertEqual(later.bars, (revised,))

    def test_unverified_revision_does_not_fall_back_to_old_price(self):
        revised = bar(close="106", first_observed_at="2026-01-06T18:00:00+09:00",
                      available_at=TimeEvidence())
        result = self.select([bar(), revised], decision="2026-01-06T18:00:00+09:00")
        self.assertEqual(result.bars, ())
        self.assertFalse(result.verified_backtest_eligible)

    def test_ambiguous_same_time_versions_rejected(self):
        with self.assertRaises(ValueError):
            self.select([bar(), bar(close="106")])

    def test_future_trade_date_and_empty_not_eligible(self):
        result = self.select([bar()], decision="2026-01-04T18:00:00+09:00")
        self.assertEqual(result.excluded[0][1], "future_trade_date")
        self.assertFalse(self.select([]).verified_backtest_eligible)

    def test_bad_mode_or_naive_decision_rejected(self):
        with self.assertRaises(ValueError):
            self.select([bar()], mode="latest")
        with self.assertRaises(ValueError):
            self.select([bar()], decision="2026-01-05T18:00:00")

    def test_input_unchanged_and_repeatable(self):
        versions = (bar(),)
        before = deepcopy(versions)
        self.assertEqual(self.select(versions), self.select(versions))
        self.assertEqual(versions, before)


class AuditRegressionTests(unittest.TestCase):
    def test_a_reject_date_aliases_and_nonexistent_dates(self):
        for value in ["20260105", "2026-W02-1", "2026-1-5", "2026-02-30"]:
            with self.subTest(value=value), self.assertRaises(ValueError):
                bar(trade_date=value)

    def test_b_reject_mutable_empty_and_whitespace_evidence(self):
        for value in [[], ["proof"], {}, {"id": "proof"}, "", " \t\n"]:
            with self.subTest(value=value), self.assertRaises(ValueError):
                TimeEvidence("2026-01-05T17:00:00+09:00", "verified", value)

    def test_c_identical_version_reacquired_without_ambiguity(self):
        original = bar()
        reacquired = bar(close="105.000", retrieved_at="2026-01-07T18:00:00+09:00")
        for versions in [(original, reacquired), (reacquired, original)]:
            result = select_as_of(versions, decision_at="2026-01-08T18:00:00+09:00",
                                  mode="verified_backtest")
            self.assertEqual(result.bars, (original,))
            self.assertTrue(result.verified_backtest_eligible)

    def test_d_duplicate_new_key_is_not_publishable(self):
        result = compare_snapshots(snapshot([]), snapshot([bar(), bar()]))
        self.assertFalse(result["complete"])
        self.assertEqual(result["added"], [])
        self.assertEqual(len(result["duplicates"]), 1)

    def test_manifest_dates_also_require_canonical_form(self):
        for name in ["requested_from", "requested_to"]:
            for value in ["20260105", "2026-W02-1", "2026-02-30"]:
                with self.subTest(name=name, value=value), self.assertRaises(ValueError):
                    snapshot([], **{name: value})

    def test_unknown_publication_blocks_verified_but_not_research(self):
        b = bar(published_at=TimeEvidence())
        for mode in ["historical_research", "verified_backtest"]:
            result = select_as_of((b,), decision_at=b.first_observed_at, mode=mode)
            self.assertFalse(result.verified_backtest_eligible)
            self.assertEqual(len(result.bars), int(mode == "historical_research"))

    def test_evidence_validation_for_all_states(self):
        for status in ["unknown", "unverified", "verified"]:
            for evidence in ["  ", ["proof"], {"proof": True}]:
                with self.subTest(status=status, evidence=evidence), self.assertRaises(ValueError):
                    TimeEvidence(None if status == "unknown" else "2026-01-05T17:00:00Z",
                                 status, evidence)

    def test_evidence_objects_and_values_cannot_be_mutable(self):
        with self.assertRaises(ValueError):
            bar(available_at={"status": "verified"})
        with self.assertRaises(ValueError):
            TimeEvidence(["2026-01-05T17:00:00Z"], "unverified", "proof")
        proof = TimeEvidence("2026-01-05T17:00:00+09:00", "verified", "proof")
        with self.assertRaises(FrozenInstanceError):
            proof.evidence = "changed"

    def test_utc_jst_midnight_boundary(self):
        proof = TimeEvidence("2026-01-04T15:00:00Z", "verified", "synthetic-boundary")
        b = bar(published_at=proof, available_at=proof,
                first_observed_at="2026-01-04T15:00:00Z")
        before = select_as_of((b,), decision_at="2026-01-04T14:59:59Z", mode="verified_backtest")
        boundary = select_as_of((b,), decision_at="2026-01-05T00:00:00+09:00", mode="verified_backtest")
        self.assertFalse(before.verified_backtest_eligible)
        self.assertTrue(boundary.verified_backtest_eligible)
        self.assertEqual(boundary.bars, (b,))

    def test_availability_equal_decision_and_one_microsecond_before(self):
        b = bar(first_observed_at="2026-01-05T17:00:00+09:00")
        accepted = select_as_of((b,), decision_at=b.available_at.value, mode="verified_backtest")
        rejected = select_as_of((b,), decision_at="2026-01-05T16:59:59.999999+09:00", mode="verified_backtest")
        self.assertTrue(accepted.verified_backtest_eligible)
        self.assertFalse(rejected.verified_backtest_eligible)

    def test_changed_evidence_same_observation_is_ambiguous(self):
        other = bar(available_at=replace(bar().available_at, evidence="different-proof"))
        with self.assertRaises(ValueError):
            select_as_of((bar(), other), decision_at=bar().first_observed_at,
                         mode="verified_backtest")

    def test_later_evidence_update_preserves_as_of_boundary(self):
        old = bar(available_at=TimeEvidence())
        new = bar(first_observed_at="2026-01-06T18:00:00+09:00")
        early = select_as_of((old, new), decision_at=old.first_observed_at, mode="verified_backtest")
        late = select_as_of((old, new), decision_at=new.first_observed_at, mode="verified_backtest")
        self.assertEqual(early.bars, ())
        self.assertFalse(early.verified_backtest_eligible)
        self.assertEqual(late.bars, (new,))
        self.assertTrue(late.verified_backtest_eligible)

    def test_correction_with_later_publication_cannot_leak(self):
        proof = TimeEvidence("2026-01-06T17:00:00+09:00", "verified", "synthetic-correction")
        revised = bar(close="106", published_at=proof, available_at=proof,
                      first_observed_at="2026-01-06T18:00:00+09:00")
        early = select_as_of((bar(), revised), decision_at=bar().first_observed_at, mode="verified_backtest")
        late = select_as_of((bar(), revised), decision_at=revised.first_observed_at, mode="verified_backtest")
        self.assertEqual(early.bars, (bar(),))
        self.assertEqual(late.bars, (revised,))

    def test_mixed_price_bases_rejected_in_both_modes(self):
        for mode in ["historical_research", "verified_backtest"]:
            with self.subTest(mode=mode), self.assertRaises(ValueError):
                select_as_of((bar(), bar(price_basis="adjusted")),
                             decision_at=bar().first_observed_at, mode=mode)

    def test_duplicate_old_or_new_blocks_all_commit_candidates(self):
        for old, new in [([bar(), bar()], []), ([], [bar(), bar()]),
                         ([bar(), bar()], [bar()])]:
            result = compare_snapshots(snapshot(old), snapshot(new))
            self.assertFalse(result["complete"])
            for category in ["added", "unchanged", "revised"]:
                self.assertEqual(result[category], [])

    def test_incomplete_acquisition_blocks_all_commit_candidates(self):
        result = compare_snapshots(snapshot([]), snapshot([bar()], complete=False))
        self.assertFalse(result["complete"])
        self.assertEqual(result["added"], [])


if __name__ == "__main__":
    unittest.main()
