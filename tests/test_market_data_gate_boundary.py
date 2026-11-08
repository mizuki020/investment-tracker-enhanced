"""Synthetic shared-boundary regressions, with no network or market storage."""
import unittest
from dataclasses import replace, FrozenInstanceError
from unittest.mock import patch

from market_data import snapshots as s, quality_gates as q
from market_data import completeness as c
from market_data.gate_boundary import route_gate_result, BoundaryOutcome

AT = "2026-01-08T18:00:00+09:00"
LONG_TIME = "2026-01-08T18:00:00." + "0" * 257 + "+09:00"


def inspection(purpose=q.Purpose.ANALYZE, complete=True):
    span=c.DateRangeClaim("2026-01-05","2026-01-05")
    return c.inspect_completeness(code="TEST",requested=span,acquired=span,
        pages=(c.Page((c.RawBar("TEST",span.start,"100","110","90","105",1000),)),),
        pages_complete=complete,calendar=(c.CalendarDay(span.start,True,c.MarketState.NORMAL),),
        listing=span,entitlement=span,purpose=purpose,target="synthetic",evaluated_at=AT)


def route(value, purpose=q.Purpose.ANALYZE, **changes):
    context=dict(purpose=purpose,target="synthetic",evaluated_at=AT)
    context.update(changes)
    return route_gate_result(value,**context)


class InitialRegressions(unittest.TestCase):
    def test_diagnostic_reason_and_unknown_time_survive_revalidation(self):
        upstream = q.GateDecision(q.Status.BLOCK, ("invalid_evaluation_time",), (),
                                  "synthetic", None, q.Purpose.ANALYZE)
        downstream = q.revalidate_decision(upstream, purpose=q.Purpose.ANALYZE,
                                          target="synthetic", evaluated_at=AT)
        self.assertEqual(downstream, upstream)
        self.assertIsNone(downstream.evaluated_at)

    def test_direct_timestamp_rejects_overlong_before_parser(self):
        with patch.object(s, "datetime", wraps=s.datetime) as parser:
            with self.assertRaises(ValueError):
                s.timestamp(LONG_TIME)
            parser.fromisoformat.assert_not_called()

    def test_direct_aggregate_rejects_overlong_without_consuming_results(self):
        def never():
            self.fail("results must not be consumed")
            yield
        result = q.aggregate_checks(purpose=q.Purpose.ANALYZE, target="synthetic",
                                    evaluated_at=LONG_TIME, results=never())
        self.assertEqual(result.reason_codes, ("invalid_evaluation_time",))
        self.assertIsNone(result.evaluated_at)


class BoundaryTests(unittest.TestCase):
    def test_early_diagnostic_preserved_for_all_five_purposes(self):
        for purpose in q.Purpose:
            upstream=q.GateDecision(q.Status.BLOCK,("invalid_evaluation_time",),(),
                                     "synthetic",None,purpose)
            out=route(upstream,purpose)
            self.assertEqual(out.decision,upstream)
            self.assertEqual(out.upstream,upstream)
            self.assertEqual(out.reason_codes,upstream.reason_codes)
            self.assertIsNone(out.upstream.evaluated_at)
            self.assertFalse(out.analysis_input_allowed)
            self.assertFalse(out.verified_performance_allowed)
            self.assertFalse(out.orders_allowed)

    def test_inspection_block_and_unverified_paths(self):
        for complete in (True,False):
            upstream=inspection(complete=complete)
            out=route(upstream)
            self.assertEqual(out.upstream,upstream)
            self.assertIs(out.status,q.Status.UNVERIFIED if complete else q.Status.BLOCK)
            if not complete:self.assertIn("pages_incomplete",out.reason_codes)

    def test_bare_checks_and_empty_iterables_refused(self):
        for value in [inspection().checks,(),[],None,{"status":"PASS"}]:
            out=route(value)
            self.assertIs(out.status,q.Status.BLOCK)
            self.assertEqual(out.reason_codes,("invalid_decision",))

    def test_unknown_length_iterator_never_consumed(self):
        def never():
            self.fail("must not consume")
            yield
        self.assertIs(route(never()).status,q.Status.BLOCK)

    def test_scope_mismatch_keeps_original_diagnostic(self):
        upstream=q.GateDecision(q.Status.BLOCK,("invalid_evaluation_time",),(),
                                 "other-target",None,q.Purpose.STORE)
        out=route(upstream)
        self.assertIs(out.status,q.Status.BLOCK)
        self.assertIn("invalid_evaluation_time",out.reason_codes)
        self.assertIn("decision_context_mismatch",out.reason_codes)
        self.assertEqual(out.upstream.target,"other-target")
        self.assertIsNone(out.upstream.evaluated_at)

    def test_direct_constructed_pass_and_mutable_values_refused(self):
        out=route(inspection())
        with self.assertRaises(ValueError):replace(out,upstream=[])
        with self.assertRaises(FrozenInstanceError):out.decision=q.Status.PASS
        forged=inspection()
        object.__setattr__(forged.checks[0],"status",q.Status.PASS)
        self.assertIs(route(forged).status,q.Status.BLOCK)

    def test_upstream_block_cannot_be_directly_promoted(self):
        out=route(inspection())
        block=q.GateDecision(q.Status.BLOCK,("invalid_evaluation_time",),(),
                              "synthetic",None,q.Purpose.ANALYZE)
        with self.assertRaises(ValueError):BoundaryOutcome(out.decision,block)

    def test_upstream_validation_exception_is_safe(self):
        upstream=inspection()
        with patch.object(c.Inspection,"__post_init__",side_effect=RuntimeError("do not echo")):
            out=route(upstream)
        self.assertIs(out.status,q.Status.BLOCK)
        self.assertNotIn("do not echo",repr(out))

    def test_overlong_boundary_context_does_not_inspect_upstream(self):
        upstream=inspection()
        with patch.object(s,"datetime",wraps=s.datetime) as parser, \
             patch.object(c.Inspection,"__post_init__",side_effect=AssertionError("do not inspect")) as inspect:
            out=route(upstream,evaluated_at=LONG_TIME)
            self.assertIs(out.status,q.Status.BLOCK)
            self.assertEqual(out.reason_codes,("invalid_evaluation_time",))
            parser.fromisoformat.assert_not_called()
            inspect.assert_not_called()

    def test_unknown_purpose_and_policy_fail_closed(self):
        self.assertIs(route(inspection(),purpose="unknown").status,q.Status.BLOCK)
        self.assertIs(route(inspection(),policy_version="other").status,q.Status.BLOCK)


class TimestampGuardTests(unittest.TestCase):
    def test_255_256_257_boundaries_and_invalid_types(self):
        prefix,suffix="2026-01-08T18:00:00.","+09:00"
        for size in (255,256,257):
            value=prefix+"0"*(size-len(prefix)-len(suffix))+suffix
            if size<=256:self.assertEqual(s.timestamp(value).year,2026)
            else:
                with self.assertRaises(ValueError):s.timestamp(value)
        for value in [None,[],{},True,""," ","invalid","2026-01-08T18:00:00"]:
            with self.assertRaises(ValueError):s.timestamp(value)

    def test_quality_direct_constructors_reject_before_datetime_parser(self):
        with patch.object(s,"datetime",wraps=s.datetime) as parser:
            for make in [
                lambda:q.CheckResult(q.Check.SCHEMA,q.Status.UNVERIFIED,"synthetic","synthetic",(),LONG_TIME,q.POLICY_VERSION,q.Purpose.ANALYZE),
                lambda:q.GateDecision(q.Status.BLOCK,("evaluation_error",),(),"synthetic",LONG_TIME,q.Purpose.ANALYZE),
                lambda:q.evaluate_rights(action=q.Action.ANALYZE,claim=q.RightClaim.UNKNOWN,contract_reference=None,purpose=q.Purpose.ANALYZE,target="synthetic",evaluated_at=LONG_TIME)]:
                with self.assertRaises(ValueError):make()
            parser.fromisoformat.assert_not_called()

    def test_snapshot_time_evidence_and_manifest_guard(self):
        with patch.object(s,"datetime",wraps=s.datetime) as parser:
            with self.assertRaises(ValueError):s.TimeEvidence(LONG_TIME,"unverified","synthetic")
            with self.assertRaises(ValueError):
                s.AcquisitionManifest("synthetic","synthetic","TEST","2026-01-05","2026-01-05",LONG_TIME,True)
            parser.fromisoformat.assert_not_called()

    def test_bar_overlong_observation_before_decimal_or_normalization(self):
        with patch.object(s,"Decimal",side_effect=AssertionError("do not convert")) as dec, \
             patch.object(s,"normalize_bars",side_effect=AssertionError("do not normalize")) as norm, \
             patch.object(s,"datetime",wraps=s.datetime) as parser:
            with self.assertRaises(ValueError):
                s.BarVersion("synthetic","TEST","2026-01-05","100","110","90","105",1000,"1",
                             s.TimeEvidence(),s.TimeEvidence(),LONG_TIME,AT)
            dec.assert_not_called();norm.assert_not_called();parser.fromisoformat.assert_not_called()

    def test_snapshot_rejects_overlong_manifest_time_before_bars(self):
        manifest=s.AcquisitionManifest("synthetic","synthetic","TEST",
                                       "2026-01-05","2026-01-05",AT,True)
        object.__setattr__(manifest,"retrieved_at",LONG_TIME)
        with patch.object(s,"datetime",wraps=s.datetime) as parser:
            with self.assertRaises(ValueError):s.Snapshot(manifest,())
            parser.fromisoformat.assert_not_called()

    def test_asof_overlong_decision_does_not_consume_versions(self):
        def never():
            self.fail("versions must not be consumed")
            yield
        with self.assertRaises(ValueError):
            s.select_as_of(never(),decision_at=LONG_TIME,mode="historical_research")

    def test_revalidation_overlong_expected_time_is_early_block(self):
        upstream=q.GateDecision(q.Status.BLOCK,("evaluation_error",),(),"synthetic",None,q.Purpose.ANALYZE)
        with patch.object(s,"datetime",wraps=s.datetime) as parser:
            result=q.revalidate_decision(upstream,purpose=q.Purpose.ANALYZE,target="synthetic",evaluated_at=LONG_TIME)
            self.assertIs(result.status,q.Status.BLOCK)
            parser.fromisoformat.assert_not_called()

    def test_future_time_parsing_is_not_authentication_or_permission(self):
        future="2099-01-08T18:00:00+09:00"
        self.assertEqual(s.timestamp(future).year,2099)
        out=route(inspection(),evaluated_at=future)
        self.assertIs(out.status,q.Status.BLOCK)  # original check evaluation time differs
        self.assertFalse(out.orders_allowed)


def synthetic_bar(**changes):
    return replace(s.BarVersion("synthetic","TEST","2026-01-05","100","110","90","105",1000,"1",
                                s.TimeEvidence(),s.TimeEvidence(),AT,AT),**changes)


def synthetic_manifest():
    return s.AcquisitionManifest("synthetic","synthetic","TEST","2026-01-05","2026-01-05",AT,True)


class NestedTimestampRegressions(unittest.TestCase):
    def test_snapshot_rejects_283_character_child_observation(self):
        b=synthetic_bar()
        self.assertEqual(len(LONG_TIME),283)
        object.__setattr__(b,"first_observed_at",LONG_TIME)
        with self.assertRaises(ValueError):s.Snapshot(synthetic_manifest(),(b,))

    def test_research_unknown_publication_cannot_skip_bad_availability(self):
        b=synthetic_bar()
        object.__setattr__(b.available_at,"status","unverified")
        object.__setattr__(b.available_at,"value","x"*257)
        with self.assertRaises(ValueError):
            s.select_as_of((b,),decision_at=AT,mode="historical_research")

    def test_every_child_time_is_preflighted_in_both_parents(self):
        for field in ("first_observed_at","retrieved_at","published_at","available_at"):
            for mode in ("historical_research","verified_backtest"):
                b=synthetic_bar();manifest=synthetic_manifest()
                if field in ("published_at","available_at"):
                    evidence=getattr(b,field)
                    object.__setattr__(evidence,"status","unverified")
                    object.__setattr__(evidence,"value","x"*257)
                else:object.__setattr__(b,field,LONG_TIME)
                with self.subTest(field=field,mode=mode), \
                     patch.object(s,"datetime",wraps=s.datetime) as parser, \
                     patch.object(s,"Decimal",side_effect=AssertionError("must not convert")) as dec, \
                     patch.object(s,"normalize_bars",side_effect=AssertionError("must not normalize")) as norm:
                    with self.assertRaises(ValueError):s.Snapshot(manifest,(b,))
                    with self.assertRaises(ValueError):s.select_as_of((b,),decision_at=AT,mode=mode)
                    parser.fromisoformat.assert_not_called();dec.assert_not_called();norm.assert_not_called()

    def test_invalid_required_types_and_empty_times_rejected(self):
        for field in ("first_observed_at","retrieved_at"):
            for value in (None,[],{},True,""):
                b=synthetic_bar();object.__setattr__(b,field,value)
                with self.subTest(field=field,value=value),self.assertRaises(ValueError):
                    s.Snapshot(synthetic_manifest(),(b,))
                with self.assertRaises(ValueError):
                    s.select_as_of((b,),decision_at=AT,mode="historical_research")

    def test_255_256_boundaries_preserve_unknown_and_research_behavior(self):
        prefix,suffix="2026-01-08T18:00:00.","+09:00"
        for length in (255,256):
            value=prefix+"0"*(length-len(prefix)-len(suffix))+suffix
            for field in ("first_observed_at","retrieved_at","published_at","available_at"):
                b=synthetic_bar()
                if field in ("published_at","available_at"):
                    b=replace(b,**{field:s.TimeEvidence(value,"unverified","synthetic")})
                else:b=replace(b,**{field:value})
                snapshot=s.Snapshot(synthetic_manifest(),(b,))
                self.assertEqual(snapshot.bars,(b,))
                research=s.select_as_of((b,),decision_at=AT,mode="historical_research")
                self.assertEqual(research.bars,(b,))
                self.assertFalse(research.verified_backtest_eligible)
                verified=s.select_as_of((b,),decision_at=AT,mode="verified_backtest")
                self.assertEqual(verified.bars,())

    def test_unknown_publication_does_not_hide_invalid_iso_availability(self):
        b=synthetic_bar()
        object.__setattr__(b.available_at,"status","unverified")
        object.__setattr__(b.available_at,"value","invalid-ISO")
        with self.assertRaises(ValueError):s.Snapshot(synthetic_manifest(),(b,))
        with self.assertRaises(ValueError):s.select_as_of((b,),decision_at=AT,mode="historical_research")

    def test_child_chronology_and_future_observation_constraints(self):
        b=synthetic_bar()
        object.__setattr__(b.available_at,"status","unverified")
        object.__setattr__(b.available_at,"value","2026-01-09T18:00:00+09:00")
        with self.assertRaises(ValueError):s.Snapshot(synthetic_manifest(),(b,))
        with self.assertRaises(ValueError):s.select_as_of((b,),decision_at=AT,mode="historical_research")
        future=synthetic_bar(first_observed_at="2026-01-09T18:00:00+09:00",
                             retrieved_at="2026-01-10T18:00:00+09:00")
        selected=s.select_as_of((future,),decision_at=AT,mode="historical_research")
        self.assertEqual(selected.bars,())
        self.assertEqual(selected.excluded[0][1],"future_version")

    def test_serialization_revalidates_before_conversion(self):
        b=synthetic_bar();snapshot=s.Snapshot(synthetic_manifest(),(b,))
        object.__setattr__(b,"first_observed_at",LONG_TIME)
        with patch.object(s,"asdict",side_effect=AssertionError("must not serialize")) as convert:
            with self.assertRaises(ValueError):snapshot.to_dict()
            convert.assert_not_called()

    def test_comparison_revalidates_before_hashing(self):
        from unittest.mock import PropertyMock
        b=synthetic_bar();snapshot=s.Snapshot(synthetic_manifest(),(b,))
        object.__setattr__(b.available_at,"status","unverified")
        object.__setattr__(b.available_at,"value","x"*257)
        with patch.object(s.BarVersion,"content_hash",new_callable=PropertyMock,
                          side_effect=AssertionError("must not hash")) as hashed:
            with self.assertRaises(ValueError):s.compare_snapshots(snapshot,snapshot)
            hashed.assert_not_called()

    def test_first_bad_child_stops_before_later_items(self):
        b=synthetic_bar();object.__setattr__(b,"first_observed_at",LONG_TIME)
        manifest=synthetic_manifest()
        with patch.object(s,"_validate_bar_time_text",wraps=s._validate_bar_time_text) as guard:
            with self.assertRaises(ValueError):s.Snapshot(manifest,(b,object()))
            self.assertEqual(guard.call_count,1)

    def test_stream_bad_child_stops_without_consuming_remainder(self):
        b=synthetic_bar();object.__setattr__(b.available_at,"value","x"*257)
        def stream():
            yield b
            self.fail("must not consume remainder")
        with self.assertRaises(ValueError):
            s.select_as_of(stream(),decision_at=AT,mode="historical_research")

    def test_wrong_child_and_evidence_types_rejected(self):
        with self.assertRaises(ValueError):s.Snapshot(synthetic_manifest(),({},))
        with self.assertRaises(ValueError):s.select_as_of(({},),decision_at=AT,mode="historical_research")
        b=synthetic_bar();object.__setattr__(b,"available_at",{"value":AT})
        with self.assertRaises(ValueError):s.Snapshot(synthetic_manifest(),(b,))
        with self.assertRaises(ValueError):s.select_as_of((b,),decision_at=AT,mode="historical_research")


class IteratorTOCTOURegressions(unittest.TestCase):
    def test_generator_future_observation_rejected_without_yield(self):
        proof=s.TimeEvidence(AT,"verified","synthetic-proof")
        b=synthetic_bar(published_at=proof,available_at=proof,
                        retrieved_at="2026-01-10T18:00:00+09:00")
        calls=[]
        def stream():
            calls.append("yield")
            yield b
            object.__setattr__(b,"first_observed_at","2026-01-09T18:00:00+09:00")
        with self.assertRaises(ValueError):
            s.select_as_of(stream(),decision_at=AT,mode="verified_backtest")
        self.assertEqual(calls,[])

    def test_generator_overlong_availability_rejected_without_yield(self):
        b=synthetic_bar();calls=[]
        def stream():
            calls.append("yield")
            yield b
            object.__setattr__(b.available_at,"status","unverified")
            object.__setattr__(b.available_at,"value",LONG_TIME)
        with self.assertRaises(ValueError):
            s.select_as_of(stream(),decision_at=AT,mode="historical_research")
        self.assertEqual(calls,[])

    def test_custom_iterator_and_container_subclasses_never_iterated(self):
        class Never:
            def __iter__(self):
                raise AssertionError("must not iterate")
            def __next__(self):
                raise AssertionError("must not advance")
        class TupleSubclass(tuple):
            def __iter__(self):
                raise AssertionError("must not iterate")
            def __len__(self):
                raise AssertionError("must not size")
        class ListSubclass(list):
            def __iter__(self):
                raise AssertionError("must not iterate")
        for mode in ("historical_research","verified_backtest"):
            for value in (Never(),TupleSubclass(),ListSubclass(),[],{},None,"",42):
                with self.subTest(mode=mode,type=type(value)),self.assertRaises(ValueError):
                    s.select_as_of(value,decision_at=AT,mode=mode)

    def test_empty_tuple_is_not_eligible(self):
        for mode in ("historical_research","verified_backtest"):
            out=s.select_as_of((),decision_at=AT,mode=mode)
            self.assertEqual(out.bars,())
            self.assertFalse(out.verified_backtest_eligible)

    def test_count_boundary_preserves_normal_verified_semantics(self):
        proof=s.TimeEvidence(AT,"verified","synthetic-proof")
        b=synthetic_bar(published_at=proof,available_at=proof)
        for size in (s.MAX_SELECTION_VERSIONS-1,s.MAX_SELECTION_VERSIONS):
            for mode in ("historical_research","verified_backtest"):
                out=s.select_as_of((b,)*size,decision_at=AT,mode=mode)
                self.assertEqual(out.bars,(b,))
                self.assertEqual(out.verified_backtest_eligible,mode=="verified_backtest")

    def test_over_limit_precedes_child_scan_parse_conversion_and_hash(self):
        from unittest.mock import PropertyMock
        versions=(object(),)*(s.MAX_SELECTION_VERSIONS+1)
        with patch.object(s,"_validate_bar_time_text",side_effect=AssertionError("no scan")) as scan, \
             patch.object(s,"datetime",wraps=s.datetime) as parser, \
             patch.object(s,"Decimal",side_effect=AssertionError("no conversion")) as decimal, \
             patch.object(s.BarVersion,"content_hash",new_callable=PropertyMock) as hashed:
            for mode in ("historical_research","verified_backtest"):
                with self.assertRaisesRegex(ValueError,"too many"):
                    s.select_as_of(versions,decision_at=AT,mode=mode)
            scan.assert_not_called();parser.fromisoformat.assert_not_called()
            decimal.assert_not_called();hashed.assert_not_called()

    def test_tuple_unknown_and_bad_child_remain_fail_closed(self):
        b=synthetic_bar()
        self.assertEqual(s.select_as_of((b,),decision_at=AT,mode="historical_research").bars,(b,))
        self.assertFalse(s.select_as_of((b,),decision_at=AT,mode="verified_backtest").verified_backtest_eligible)
        object.__setattr__(b.available_at,"value",LONG_TIME)
        for mode in ("historical_research","verified_backtest"):
            with self.assertRaises(ValueError):s.select_as_of((b,),decision_at=AT,mode=mode)

    def test_future_observation_tuple_never_eligible(self):
        proof=s.TimeEvidence(AT,"verified","synthetic-proof")
        b=synthetic_bar(published_at=proof,available_at=proof,
                        first_observed_at="2026-01-09T18:00:00+09:00",
                        retrieved_at="2026-01-10T18:00:00+09:00")
        for mode in ("historical_research","verified_backtest"):
            out=s.select_as_of((b,),decision_at=AT,mode=mode)
            self.assertEqual(out.bars,())
            self.assertFalse(out.verified_backtest_eligible)

    def test_rejected_generator_both_modes_no_parse_or_consumption(self):
        for mode in ("historical_research","verified_backtest"):
            calls=[]
            def stream():
                calls.append("yield")
                yield synthetic_bar()
            with patch.object(s,"datetime",wraps=s.datetime) as parser:
                with self.assertRaises(ValueError):s.select_as_of(stream(),decision_at=AT,mode=mode)
                parser.fromisoformat.assert_not_called()
            self.assertEqual(calls,[])

    def test_all_operational_permissions_remain_false(self):
        for purpose in q.Purpose:
            out=route(inspection(purpose=purpose),purpose=purpose)
            self.assertFalse(out.analysis_input_allowed)
            self.assertFalse(out.verified_performance_allowed)
            self.assertFalse(out.orders_allowed)


if __name__ == "__main__":
    unittest.main()
