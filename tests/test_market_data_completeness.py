"""Synthetic-only pre-normalization completeness tests; no evidence trust bypass."""
from dataclasses import replace, FrozenInstanceError
from datetime import date, timedelta
from unittest.mock import patch
import unittest

from market_data.completeness import (
    RawBar, CalendarDay, MarketState, DateRangeClaim, Page,
    inspect_completeness, compare_dates, DateComparison, Finding,
    MAX_ROWS, MAX_PAGES, MAX_CALENDAR_DAYS, MAX_RANGE_DAYS,
    MAX_PRICE_CHARS, MAX_REFERENCE_CHARS,
)
from market_data.quality_gates import (
    Status, Check, Purpose, aggregate_checks, revalidate_decision,
)

DAYS = ("2026-01-05", "2026-01-06", "2026-01-07")
AT = "2026-01-08T18:00:00+09:00"


def raw(day=DAYS[0], **changes):
    return replace(RawBar("TEST", day, "100", "110", "90", "105", 1000), **changes)


def inspect(**changes):
    args = dict(code="TEST", requested=DateRangeClaim(DAYS[0], DAYS[-1]),
                acquired=DateRangeClaim(DAYS[0], DAYS[-1]),
                pages=(Page(tuple(raw(d) for d in DAYS)),), pages_complete=True,
                calendar=tuple(CalendarDay(d, True, MarketState.NORMAL, "synthetic-calendar") for d in DAYS),
                listing=DateRangeClaim("2026-01-01", "2026-12-31", "synthetic-listing"),
                entitlement=DateRangeClaim("2026-01-01", "2026-12-31", "synthetic-contract"),
                purpose=Purpose.HISTORICAL_RESEARCH, target="synthetic-target", evaluated_at=AT)
    args.update(changes)
    return inspect_completeness(**args)


def reasons(report):
    return {f.reason for f in report.findings}


class DateTests(unittest.TestCase):
    def test_matching_dates_under_synthetic_verified_fixture_assumption(self):
        # Mathematical oracle only; there is deliberately no trusted=True API.
        self.assertTrue(compare_dates(DAYS, DAYS).matches)
        self.assertTrue(all(c.status is Status.UNVERIFIED for c in inspect().checks))

    def test_one_and_multiple_missing_days(self):
        for observed in [DAYS[:2], DAYS[:1]]:
            diff = compare_dates(DAYS, observed)
            self.assertEqual(diff.missing, DAYS[len(observed):])
            r = inspect(pages=(Page(tuple(raw(d) for d in observed)),))
            self.assertIn("missing_expected_dates_unverified_calendar", reasons(r))

    def test_duplicate_observed_day(self):
        r = inspect(pages=(Page((raw(), raw())),))
        self.assertIn("duplicate_dates", reasons(r))
        self.assertTrue(any(c.status is Status.BLOCK for c in r.checks))

    def test_out_of_range_day_and_wrong_security(self):
        r = inspect(pages=(Page((raw("2026-01-08", code="OTHER"),)),))
        self.assertIn("row_outside_request", reasons(r))
        self.assertIn("wrong_security", reasons(r))

    def test_date_alias_invalid_date_and_mutable_comparison_input(self):
        for day in ["20260105", "2026-W02-1", "2026-02-30"]:
            with self.assertRaises(ValueError):
                raw(day)
        with self.assertRaises(ValueError):
            compare_dates(list(DAYS), DAYS)
        with self.assertRaises(ValueError):
            compare_dates((DAYS[0], DAYS[0]), DAYS)


class MarketTests(unittest.TestCase):
    def calendar(self, **changes):
        return (replace(CalendarDay(DAYS[0], True, MarketState.NORMAL,
                                    "synthetic-claim", "TEST"), **changes),
                CalendarDay(DAYS[1], True, MarketState.NORMAL),
                CalendarDay(DAYS[2], True, MarketState.NORMAL))

    def test_closed_day_with_and_without_row_remains_unverified(self):
        for rows in [tuple(raw(d) for d in DAYS), tuple(raw(d) for d in DAYS[1:])]:
            r = inspect(calendar=self.calendar(session=False), pages=(Page(rows),))
            self.assertIn("closed_day_claim", reasons(r))
            self.assertTrue(all(c.status is not Status.PASS for c in r.checks))

    def test_full_halt_does_not_authenticate_absence(self):
        r = inspect(calendar=self.calendar(state=MarketState.FULL_HALT),
                    pages=(Page(tuple(raw(d) for d in DAYS[1:])),))
        self.assertIn("full_halt_claim", reasons(r))
        self.assertIn("absence_requires_authenticated_evidence", reasons(r))

    def test_partial_halt_still_requires_bar(self):
        r = inspect(calendar=self.calendar(state=MarketState.PARTIAL_HALT),
                    pages=(Page(tuple(raw(d) for d in DAYS[1:])),))
        self.assertNotIn("full_halt_claim", reasons(r))
        self.assertIn("missing_expected_dates_unverified_calendar", reasons(r))

    def test_no_trades_does_not_become_zero_bar(self):
        r = inspect(calendar=self.calendar(state=MarketState.NO_TRADES),
                    pages=(Page(tuple(raw(d) for d in DAYS[1:])),))
        self.assertIn("no_trades_claim", reasons(r))
        self.assertIn("absence_requires_authenticated_evidence", reasons(r))

    def test_market_state_wrong_security_does_not_excuse_absence(self):
        r = inspect(calendar=self.calendar(state=MarketState.FULL_HALT, code="OTHER"),
                    pages=(Page(tuple(raw(d) for d in DAYS[1:])),))
        self.assertIn("market_state_scope_unverified", reasons(r))
        self.assertNotIn("full_halt_claim", reasons(r))
        self.assertIn("missing_expected_dates_unverified_calendar", reasons(r))

    def test_pre_listing_and_post_delisting_claims(self):
        r = inspect(listing=DateRangeClaim(DAYS[1], DAYS[1], "synthetic-listing"))
        self.assertIn("pre_listing_claim", reasons(r))
        self.assertIn("post_delisting_claim", reasons(r))

    def test_unknown_listing_calendar_or_market_state(self):
        self.assertIn("listing_unknown", reasons(inspect(listing=None)))
        self.assertIn("calendar_coverage_missing", reasons(inspect(calendar=())))
        self.assertIn("market_state_unknown", reasons(inspect(calendar=self.calendar(state=MarketState.UNKNOWN))))

    def test_reference_self_assertions_never_authenticate(self):
        for reference in [None, "verified=true", "official-calendar", "HTTP-200"]:
            r = inspect(calendar=self.calendar(evidence_id=reference))
            self.assertTrue(all(c.status is not Status.PASS for c in r.checks))

    def test_calendar_correction_duplicate_and_outside_scope(self):
        calendar=self.calendar()
        r = inspect(calendar=calendar+(replace(calendar[0], session=False),))
        self.assertIn("duplicate_or_revised_calendar_day", reasons(r))
        r = inspect(calendar=calendar+(CalendarDay("2026-01-08", True, MarketState.NORMAL),))
        self.assertIn("calendar_outside_request", reasons(r))


class AcquisitionTests(unittest.TestCase):
    def test_valid_two_page_chain_is_structurally_consistent_not_authenticated(self):
        r = inspect(pages=(Page((raw(),), next_cursor="next"),
                           Page(tuple(raw(d) for d in DAYS[1:]), requested_cursor="next")))
        self.assertNotIn("page_chain_invalid", reasons(r))
        self.assertNotIn("pages_incomplete", reasons(r))
        self.assertTrue(all(c.status is Status.UNVERIFIED for c in r.checks))

    def test_interruption_pending_cursor_and_empty_pages(self):
        for changes in [dict(pages_complete=False), dict(pages=()),
                        dict(pages=(Page((raw(),), next_cursor="next"),))]:
            self.assertIn("pages_incomplete", reasons(inspect(**changes)))

    def test_cursor_cycle(self):
        r = inspect(pages=(Page((raw(),), next_cursor="loop"),
                           Page((raw(DAYS[1]),), requested_cursor="loop", next_cursor="loop")))
        self.assertIn("page_cursor_cycle", reasons(r))

    def test_disconnected_and_premature_termination(self):
        for pages in [(Page((raw(),), requested_cursor="unexpected"),),
                      (Page((raw(),)), Page((raw(DAYS[1]),)))]:
            self.assertIn("page_chain_invalid", reasons(inspect(pages=pages)))

    def test_scope_truncation_not_silently_accepted(self):
        r = inspect(acquired=DateRangeClaim(DAYS[1], DAYS[-1]))
        self.assertIn("acquired_scope_mismatch", reasons(r))

    def test_contract_excluded_and_unknown_period(self):
        r = inspect(entitlement=DateRangeClaim(DAYS[1], DAYS[-1], "synthetic-contract"))
        self.assertIn("claimed_entitlement_excludes_request", reasons(r))
        self.assertIn("entitlement_unknown", reasons(inspect(entitlement=None)))


class RawAndBoundaryTests(unittest.TestCase):
    def test_null_and_missing_fields_not_imputed(self):
        b=raw(close=None)
        r=inspect(pages=(Page((b,)),))
        self.assertIn("raw_null_ohlcv", reasons(r))
        self.assertIsNone(b.close)

    def test_invalid_ohlcv(self):
        for changes in [dict(high="99"), dict(close="NaN"), dict(low="0"),
                        dict(volume=-1), dict(close="invalid")]:
            with self.subTest(changes=changes):
                self.assertIn("invalid_ohlcv", reasons(inspect(pages=(Page((raw(**changes),)),))))

    def test_original_order_inspected_before_normalizing(self):
        self.assertIn("raw_date_order_invalid", reasons(inspect(pages=(Page(tuple(raw(d) for d in reversed(DAYS))),))))

    def test_mutable_and_wrong_input_types_fail_closed(self):
        for changes in [dict(calendar=[]), dict(pages=[]), dict(pages_complete="true"),
                        dict(requested={}), dict(pages=(None,)), dict(calendar=(None,))]:
            r=inspect(**changes)
            self.assertTrue(all(c.status is Status.BLOCK for c in r.checks))
        with self.assertRaises(ValueError):
            Page([raw()])
        with self.assertRaises(ValueError):
            raw(volume=True)

    def test_context_errors_never_yield_pass(self):
        for changes in [dict(purpose="unknown"), dict(target=[]), dict(evaluated_at="naive")]:
            with self.assertRaises(ValueError):
                inspect(**changes)

    def test_constructor_bypassed_invalid_data_stops(self):
        b=raw()
        object.__setattr__(b, "day", "20260105")
        page=object.__new__(Page)
        object.__setattr__(page,"rows",(b,))
        object.__setattr__(page,"requested_cursor",None)
        object.__setattr__(page,"next_cursor",None)
        self.assertTrue(all(c.status is Status.BLOCK for c in inspect(pages=(page,)).checks))

    def test_deterministic_immutable_results_and_inputs(self):
        r=inspect()
        self.assertEqual(r,inspect())
        with self.assertRaises(FrozenInstanceError):
            r.checks=()
        with self.assertRaises(FrozenInstanceError):
            r.findings[0].reason="changed"
        self.assertFalse(r.analysis_input_allowed)
        self.assertFalse(r.verified_performance_allowed)
        self.assertFalse(r.orders_allowed)

    def test_quality_gate_integration_still_requires_other_gates(self):
        for purpose in Purpose:
            r=inspect(purpose=purpose)
            d=aggregate_checks(purpose=purpose,target="synthetic-target",evaluated_at=AT,results=r.checks)
            checked=revalidate_decision(d,purpose=purpose,target="synthetic-target",evaluated_at=AT)
            self.assertIsNot(checked.status,Status.PASS)
            self.assertFalse(checked.analysis_input_allowed)
            self.assertFalse(checked.verified_performance_allowed)
            self.assertFalse(checked.orders_allowed)

    def test_inspection_direct_pass_and_mutable_findings_rejected(self):
        r=inspect()
        with self.assertRaises(ValueError):
            replace(r, checks=(replace(r.checks[0],status=Status.PASS),)+r.checks[1:])
        with self.assertRaises(ValueError):
            replace(r, findings=list(r.findings))

    def test_output_cannot_hide_blocking_findings(self):
        r=inspect(pages_complete=False)
        checks=tuple(replace(c,status=Status.UNVERIFIED) if c.check is Check.COMPLETENESS else c
                     for c in r.checks)
        with self.assertRaises(ValueError):
            replace(r,checks=checks)
        with self.assertRaises(ValueError):
            replace(r,findings=())

    def test_comparison_rejects_mutable_or_alias_output(self):
        with self.assertRaises(ValueError):
            DateComparison([],(),())
        with self.assertRaises(ValueError):
            DateComparison(("20260105",),(),())

    def test_arithmetic_order_does_not_hide_raw_order_check(self):
        self.assertTrue(compare_dates(DAYS,tuple(reversed(DAYS))).matches)
        r=inspect(pages=(Page(tuple(raw(d) for d in reversed(DAYS))),))
        self.assertIn("raw_date_order_invalid",reasons(r))

    def test_nonfinite_and_exception_path_are_safe(self):
        self.assertIn("invalid_ohlcv", reasons(inspect(pages=(Page((raw(close="Infinity"),)),))))
        r=inspect(requested=DateRangeClaim("2026-01-01","9999-12-31"),
                  acquired=DateRangeClaim("2026-01-01","9999-12-31"))
        self.assertTrue(all(c.status is Status.BLOCK for c in r.checks))
        self.assertIn("range_day_limit",reasons(r))


class AuditFixTests(unittest.TestCase):
    def test_fake_status_rejected(self):
        class Fake:
            def __eq__(self,other):return other is Status.UNVERIFIED
        with self.assertRaises(ValueError):
            Finding(Check.SCHEMA,Fake(),"synthetic")

    def test_maximum_date_no_internal_overflow(self):
        edge=DateRangeClaim("9999-12-31","9999-12-31")
        r=inspect(requested=edge,acquired=edge,listing=edge,entitlement=edge,
                  pages=(Page(()),),calendar=(CalendarDay(edge.start,False,MarketState.NORMAL),))
        self.assertTrue(all(c.status is Status.UNVERIFIED for c in r.checks))

    def test_input_size_regressions(self):
        self.assertIn("page_count_limit",reasons(inspect(pages=(Page(()),)*65)))
        calendar=(CalendarDay(DAYS[0],True,MarketState.NORMAL),)*4097
        self.assertIn("calendar_count_limit",reasons(inspect(calendar=calendar)))

    def test_oversized_price_and_evidence_rejected(self):
        with self.assertRaises(ValueError):
            raw(close="1"*65)
        with self.assertRaises(ValueError):
            CalendarDay(DAYS[0],True,MarketState.NORMAL,"e"*257)

    def test_valid_date_boundaries_and_reversed_range(self):
        for day in ["0001-01-01","2026-01-31","2024-02-29","9999-12-31"]:
            edge=DateRangeClaim(day,day)
            r=inspect(requested=edge,acquired=edge,listing=edge,entitlement=edge,
                      pages=(Page(()),),calendar=(CalendarDay(day,False,MarketState.NORMAL),))
            self.assertTrue(all(c.status is Status.UNVERIFIED for c in r.checks),day)
        with self.assertRaises(ValueError):
            DateRangeClaim(DAYS[1],DAYS[0])
        with self.assertRaises(ValueError):
            DateRangeClaim("2025-02-29","2025-02-29")

    def test_page_count_minus_at_plus_limit(self):
        for n in [MAX_PAGES-1,MAX_PAGES,MAX_PAGES+1]:
            r=inspect(pages=(Page(()),)*n)
            self.assertEqual("page_count_limit" in reasons(r), n>MAX_PAGES)

    def test_row_count_minus_at_plus_limit(self):
        for n in [MAX_ROWS-1,MAX_ROWS,MAX_ROWS+1]:
            if n<=MAX_ROWS:
                page=Page((raw(),)*n)
            else:
                page=object.__new__(Page)
                object.__setattr__(page,"rows",(raw(),)*n)
                object.__setattr__(page,"requested_cursor",None)
                object.__setattr__(page,"next_cursor",None)
            r=inspect(pages=(page,))
            self.assertEqual("row_count_limit" in reasons(r),n>MAX_ROWS)
        with self.assertRaises(ValueError):
            Page((raw(),)*(MAX_ROWS+1))

    def test_total_rows_across_pages_bounded(self):
        a=Page((raw(),)*(MAX_ROWS//2),next_cursor="next")
        b=Page((raw(),)*(MAX_ROWS//2+1),requested_cursor="next")
        self.assertIn("row_count_limit",reasons(inspect(pages=(a,b))))

    def test_calendar_count_minus_at_plus_limit(self):
        for n in [MAX_CALENDAR_DAYS-1,MAX_CALENDAR_DAYS,MAX_CALENDAR_DAYS+1]:
            calendar=(CalendarDay(DAYS[0],True,MarketState.NORMAL),)*n
            r=inspect(calendar=calendar)
            self.assertEqual("calendar_count_limit" in reasons(r),n>MAX_CALENDAR_DAYS)

    def test_range_minus_at_plus_limit_before_any_rows(self):
        for n in [MAX_RANGE_DAYS-1,MAX_RANGE_DAYS,MAX_RANGE_DAYS+1]:
            start=date(2020,1,1)
            claim=DateRangeClaim(start.isoformat(),(start+timedelta(days=n-1)).isoformat())
            r=inspect(requested=claim,acquired=claim,pages=(Page(()),),calendar=())
            self.assertEqual("range_day_limit" in reasons(r),n>MAX_RANGE_DAYS)
        huge=DateRangeClaim("0001-01-01","9999-12-31")
        self.assertIn("range_day_limit",reasons(inspect(requested=huge,acquired=huge,pages=(object(),))))

    def test_price_and_reference_length_boundaries(self):
        for n in [MAX_PRICE_CHARS-1,MAX_PRICE_CHARS,MAX_PRICE_CHARS+1]:
            if n<=MAX_PRICE_CHARS:
                b=raw(close="1"*n)
                self.assertNotIn("price_length_limit",reasons(inspect(pages=(Page((b,)),))))
            else:
                with self.assertRaises(ValueError):raw(close="1"*n)
        for n in [MAX_REFERENCE_CHARS-1,MAX_REFERENCE_CHARS,MAX_REFERENCE_CHARS+1]:
            if n<=MAX_REFERENCE_CHARS:
                CalendarDay(DAYS[0],True,MarketState.NORMAL,"e"*n)
            else:
                with self.assertRaises(ValueError):CalendarDay(DAYS[0],True,MarketState.NORMAL,"e"*n)

    def test_calendar_reference_limit_before_decimal(self):
        day=CalendarDay(DAYS[0],True,MarketState.NORMAL)
        object.__setattr__(day,"evidence_id","e"*(MAX_REFERENCE_CHARS+1))
        with patch("market_data.completeness.Decimal",side_effect=AssertionError("must not convert")) as convert:
            r=inspect(calendar=(day,))
            self.assertIn("reference_length_limit",reasons(r))
            convert.assert_not_called()

    def test_price_limit_before_decimal_and_flattening(self):
        b=raw()
        object.__setattr__(b,"close","1"*(MAX_PRICE_CHARS+1))
        page=object.__new__(Page)
        for name,value in [("rows",(b,)),("requested_cursor",None),("next_cursor",None)]:
            object.__setattr__(page,name,value)
        with patch("market_data.completeness.Decimal",side_effect=AssertionError("must not convert")) as convert:
            r=inspect(pages=(page,))
            self.assertIn("price_length_limit",reasons(r))
            convert.assert_not_called()

    def test_unknown_length_iterators_not_consumed(self):
        def never():
            self.fail("iterator must not be consumed")
            yield raw()
        for field in ["pages","calendar"]:
            r=inspect(**{field:never()})
            self.assertTrue(all(c.status is Status.BLOCK for c in r.checks))

    def test_fake_status_constructor_bypass_and_mutation_rejected(self):
        f=Finding(Check.SCHEMA,Status.UNVERIFIED,"synthetic")
        with self.assertRaises(FrozenInstanceError):f.status=Status.BLOCK
        class Fake:
            def __eq__(self,other):return other is Status.UNVERIFIED
        object.__setattr__(f,"status",Fake())
        r=inspect()
        with self.assertRaises(ValueError):replace(r,findings=r.findings+(f,))

    def test_size_failures_still_block_quality_boundary(self):
        r=inspect(pages=(Page(()),)*(MAX_PAGES+1))
        d=aggregate_checks(purpose=Purpose.HISTORICAL_RESEARCH,target="synthetic-target",
                           evaluated_at=AT,results=r.checks)
        checked=revalidate_decision(d,purpose=Purpose.HISTORICAL_RESEARCH,
                                    target="synthetic-target",evaluated_at=AT)
        self.assertIs(checked.status,Status.BLOCK)
        self.assertFalse(checked.analysis_input_allowed)
        self.assertFalse(checked.verified_performance_allowed)
        self.assertFalse(checked.orders_allowed)


class EvaluationTimeRegressionTests(unittest.TestCase):
    def test_overlong_time_rejected_before_parsing_or_decimal(self):
        from market_data.snapshots import timestamp
        long_time="2026-01-08T18:00:00."+"0"*257+"+09:00"
        with patch("market_data.completeness.timestamp",wraps=timestamp) as parser, \
             patch("market_data.completeness.Decimal",wraps=__import__('decimal').Decimal) as convert:
            try:
                blocked=inspect(evaluated_at=long_time)
            except ValueError:
                blocked=None
            self.assertEqual(parser.call_count,0)
            self.assertEqual(convert.call_count,0)
            self.assertIsNotNone(blocked)
            self.assertIs(blocked.status,Status.BLOCK)
            self.assertEqual(blocked.reason_codes,("invalid_evaluation_time",))
            self.assertIsNone(blocked.evaluated_at)
            self.assertEqual(blocked.target,"synthetic-target")
            self.assertIs(blocked.purpose,Purpose.HISTORICAL_RESEARCH)
            self.assertFalse(blocked.analysis_input_allowed)
            self.assertFalse(blocked.verified_performance_allowed)
            self.assertFalse(blocked.orders_allowed)

    def test_time_length_minus_at_plus_limit(self):
        prefix,suffix="2026-01-08T18:00:00.","+09:00"
        for length in [MAX_REFERENCE_CHARS-1,MAX_REFERENCE_CHARS,MAX_REFERENCE_CHARS+1]:
            value=prefix+"0"*(length-len(prefix)-len(suffix))+suffix
            self.assertEqual(len(value),length)
            r=inspect(evaluated_at=value)
            if length>MAX_REFERENCE_CHARS:
                self.assertIs(r.status,Status.BLOCK)
                self.assertIsNone(r.evaluated_at)
            else:
                self.assertTrue(all(c.status is Status.UNVERIFIED for c in r.checks))
                self.assertTrue(all(c.evaluated_at==value for c in r.checks))

    def test_early_block_does_not_touch_supplied_pages_or_rows(self):
        # Preconstruct inputs before installing spies: fixture construction is not inspection.
        claim=DateRangeClaim(DAYS[0],DAYS[-1])
        pages=(Page((raw(),)),)
        args=dict(code="TEST",requested=claim,acquired=claim,pages=pages,pages_complete=True,
                  calendar=(),listing=None,entitlement=None,purpose=Purpose.HISTORICAL_RESEARCH,
                  target="synthetic-target",evaluated_at="x"*(MAX_REFERENCE_CHARS+1))
        with patch("market_data.completeness.timestamp",side_effect=AssertionError("parse forbidden")) as parser, \
             patch("market_data.quality_gates.timestamp",side_effect=AssertionError("consumer parse forbidden")) as consumer_parser, \
             patch("market_data.completeness.Decimal",side_effect=AssertionError("decimal forbidden")) as convert, \
             patch.object(Page,"__post_init__",side_effect=AssertionError("pages forbidden")) as page_check, \
             patch.object(RawBar,"__post_init__",side_effect=AssertionError("rows forbidden")) as row_check:
            r=inspect_completeness(**args)
            self.assertIs(r.status,Status.BLOCK)
            for spy in (parser,consumer_parser,convert,page_check,row_check):spy.assert_not_called()

    def test_normal_iso_times_preserve_existing_behavior(self):
        for value in [AT,"2026-01-08T09:00:00Z","2026-01-08T09:00:00.123456+00:00"]:
            r=inspect(evaluated_at=value)
            self.assertTrue(all(c.status is Status.UNVERIFIED for c in r.checks))
            self.assertTrue(all(c.evaluated_at==value for c in r.checks))

    def test_wrong_type_empty_and_malformed_time_fail_closed(self):
        for value in [None,[],{},True,0,"", " ","invalid","2026-01-08T18:00:00"]:
            with self.subTest(value=value),self.assertRaises(ValueError):
                inspect(evaluated_at=value)

    def test_overlong_time_does_not_consume_iterators(self):
        def never():
            self.fail("must not consume")
            yield
        r=inspect(pages=never(),calendar=never(),evaluated_at="x"*(MAX_REFERENCE_CHARS+1))
        self.assertIs(r.status,Status.BLOCK)
        self.assertEqual(r.checks,())

    def test_early_block_is_immutable_and_not_promoted_by_consumer(self):
        r=inspect(evaluated_at="x"*(MAX_REFERENCE_CHARS+1))
        with self.assertRaises(FrozenInstanceError):r.status=Status.PASS
        checked=revalidate_decision(r,purpose=Purpose.HISTORICAL_RESEARCH,
                                    target="synthetic-target",evaluated_at=AT)
        self.assertIs(checked.status,Status.BLOCK)
        self.assertFalse(checked.analysis_input_allowed)
        self.assertFalse(checked.verified_performance_allowed)
        self.assertFalse(checked.orders_allowed)


if __name__ == "__main__":
    unittest.main()
