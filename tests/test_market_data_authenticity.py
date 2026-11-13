"""Synthetic contract tests; no real credentials, market data or network."""
import unittest
from dataclasses import replace, FrozenInstanceError
from unittest.mock import patch
from market_data import authenticity as a, trust_policy as t
from market_data.quality_gates import Status

AT='2026-01-08T18:00:00+09:00'
def target(**kw):
    return replace(a.Target('TEST','TSE','2026-01-05','2026-01-05','unadjusted','v1','0'*64,'1'*64,'synthetic','1'),**kw)
def evidence(**kw):
    return replace(a.Evidence('evidence/1','e1','issuer','receipt',target(),AT,AT,'2026-01-09T18:00:00+09:00'),**kw)
def trust(**kw):
    return replace(t.TrustClaim('trust/1','issuer',('receipt',),'unapproved-registration',('synthetic-approval',),('ed25519',),'key1',AT,'2026-01-09T18:00:00+09:00','unknown','synthetic'),**kw)
def evaluate(ev=None,**kw):
    args=dict(target=target(),evidences=(evidence(),) if ev is None else ev,trust_claims=(),evaluated_at=AT)
    args.update(kw);return a.evaluate_authenticity(**args)

class AuthenticityTests(unittest.TestCase):
    def test_missing_unverified(self):
        self.assertIs(evaluate(()).status,Status.UNVERIFIED)
    def test_claim_never_trusted(self):
        self.assertIs(evaluate(trust_claims=(trust(),)).status,Status.UNVERIFIED)
    def test_unknown_fields_rejected(self):
        for extra in ('verified','trusted','public_key'):
            with self.assertRaises(ValueError):a.evidence_from_mapping({'schema_version':'evidence/1',extra:True})
    def test_scope_mismatch(self):
        for kw in (dict(code='OTHER'),dict(market='OTHER'),dict(start='2026-01-04'),dict(end='2026-01-06'),dict(price_basis='adjusted'),dict(data_version='v2'),dict(raw_digest='2'*64),dict(normalized_digest='3'*64),dict(normalization_version='2')):
            self.assertIs(evaluate((evidence(target=target(**kw)),)).status,Status.BLOCK)
    def test_time_invalid_and_early(self):
        args=dict(target=target(),evidences=(evidence(),),trust_claims=())
        for bad in ('','x'*257,[],None):
            with patch.object(a,'timestamp',side_effect=AssertionError('no parsing')) as parse:
                out=a.evaluate_authenticity(**args,evaluated_at=bad)
                self.assertIs(out.status,Status.BLOCK);parse.assert_not_called()
    def test_generator_not_consumed(self):
        def never():
            self.fail('consumed');yield
        self.assertIs(evaluate(never()).status,Status.BLOCK)
    def test_subclass_rejected(self):
        class Evil(tuple):
            def __iter__(self):raise AssertionError('consumed')
        self.assertIs(evaluate(Evil()).status,Status.BLOCK)
    def test_later_block_not_hidden(self):
        self.assertIs(evaluate((evidence(),evidence(evidence_id='e2',target=target(code='OTHER')))).status,Status.BLOCK)
    def test_exception_fixed(self):
        with patch.object(a,'_inspect',side_effect=RuntimeError('secret exception')):
            out=evaluate()
        self.assertEqual(out.reasons,('evaluation_error',));self.assertNotIn('secret',repr(out))
    def test_no_pass_and_permissions(self):
        out=evaluate()
        with self.assertRaises(ValueError):replace(out,status=Status.PASS)
        with self.assertRaises(FrozenInstanceError):out.status=Status.PASS
        object.__setattr__(out,'status',Status.PASS)
        self.assertIs(a.revalidate(out,target=target(),evaluated_at=AT).status,Status.BLOCK)
        for prop in ('analysis_input_allowed','verified_performance_allowed','orders_allowed'):
            self.assertFalse(getattr(out,prop))
    def test_reuse_context(self):
        self.assertIs(a.revalidate(evaluate(),target=target(code='OTHER'),evaluated_at=AT).status,Status.BLOCK)
    def test_count_limits_before_scan(self):
        for n in (63,64):
            ev=tuple(evidence(evidence_id='e'+str(i)) for i in range(n))
            self.assertIs(evaluate(ev).status,Status.UNVERIFIED)
        with patch.object(a.Evidence,'__post_init__',side_effect=AssertionError('no scan')):
            self.assertIs(evaluate((object(),)*65).status,Status.BLOCK)
    def test_payload_and_total_limits(self):
        e=evidence();size=a.evidence_size(e)
        for n in (65535-size,65536-size):
            self.assertIs(evaluate((replace(e,payload=b'x'*n),)).status,Status.UNVERIFIED)
        self.assertIs(evaluate((replace(e,payload=b'x'*(65537-size)),)).status,Status.BLOCK)
        ev=tuple(evidence(evidence_id='e'+str(i),payload=b'x'*60000) for i in range(18))
        self.assertIs(evaluate(ev).status,Status.BLOCK)
    def test_validity_half_open_and_future(self):
        self.assertIs(evaluate(evaluated_at='2026-01-09T18:00:00+09:00').status,Status.BLOCK)
        self.assertIs(evaluate((evidence(issued_at='2026-01-09T18:00:00+09:00'),)).status,Status.BLOCK)
    def test_conflicts_and_duplicate(self):
        self.assertIs(evaluate((evidence(),evidence())).status,Status.BLOCK)
        self.assertIs(evaluate((evidence(replaces='e1'),)).status,Status.BLOCK)
    def test_no_false_revocation_claim(self):
        out=evaluate(trust_claims=(trust(revocation='revoked'),))
        self.assertIs(out.status,Status.UNVERIFIED)
        self.assertNotIn('revoked_verified',out.reasons)
    def test_child_mutation_revalidated(self):
        e=evidence();object.__setattr__(e.target,'code',[])
        self.assertIs(evaluate((e,)).status,Status.BLOCK)
    def test_timestamp_boundaries(self):
        for n in (255,256,257):
            value='2026-01-08T18:00:00.'+'0'*(n-25)+'+09:00'
            if len(value)<=256:self.assertIs(evaluate(evaluated_at=value).status,Status.UNVERIFIED)
            else:self.assertIs(evaluate(evaluated_at=value).status,Status.BLOCK)

    def test_target_version_count_before_processing(self):
        expected=target()
        for size in (0,1,4095,4096):
            self.assertIs(evaluate((),target_versions=(expected,)*size).status,Status.UNVERIFIED)
        with patch.object(a,'timestamp',side_effect=AssertionError('no parse')) as parser:
            out=a.evaluate_authenticity(target=expected,evidences=(),trust_claims=(),evaluated_at=AT,target_versions=(object(),)*4097)
            self.assertIs(out.status,Status.BLOCK);self.assertEqual(out.reasons,('resource_limit',))
            parser.assert_not_called()

    def test_text_id_boundaries(self):
        for size in (255,256):self.assertIs(evaluate((evidence(evidence_id='e'*size),)).status,Status.UNVERIFIED)
        with self.assertRaises(ValueError):evidence(evidence_id='e'*257)

    def test_total_byte_exact_boundaries(self):
        prefix=tuple(evidence(evidence_id='e'+str(i),payload=b'x'*60000) for i in range(17))
        last=evidence(evidence_id='last')
        remaining=t.MAX_TOTAL_BYTES-sum(a.evidence_size(e) for e in prefix)-a.evidence_size(last)
        self.assertTrue(0<remaining<60000)
        for delta in (-1,0,1):
            out=evaluate(prefix+(replace(last,payload=b'x'*(remaining+delta)),))
            self.assertIs(out.status,Status.BLOCK if delta==1 else Status.UNVERIFIED)

    def test_invalid_child_time_before_any_parse(self):
        b=evidence();expected=target()
        object.__setattr__(b,'valid_until','x'*257)
        with patch.object(a,'timestamp',side_effect=AssertionError('no parse')) as parser:
            out=a.evaluate_authenticity(target=expected,evidences=(b,),trust_claims=(),evaluated_at=AT)
            self.assertIs(out.status,Status.BLOCK);parser.assert_not_called()

    def test_trust_self_assertion_and_mutable_claims(self):
        with self.assertRaises(TypeError):t.TrustClaim(trusted=True)
        with self.assertRaises(ValueError):trust(authorities=['receipt'])
        with self.assertRaises(ValueError):trust(environment='production')
        with self.assertRaises(ValueError):replace(evidence(),payload=bytearray())

    def test_invalid_result_context_and_mutable_collections(self):
        out=evaluate()
        with self.assertRaises(ValueError):replace(out,reasons=list(out.reasons))
        with self.assertRaises(ValueError):replace(out,status='UNVERIFIED')
        with self.assertRaises(ValueError):replace(out,status=Status.BLOCK)
        self.assertIs(a.revalidate(out,target=target(),evaluated_at='2026-01-08T19:00:00+09:00').status,Status.BLOCK)

    def test_replacement_cycle_and_missing_reference(self):
        self.assertIs(evaluate((evidence(replaces='missing'),)).status,Status.UNVERIFIED)
        ev=(evidence(replaces='e2'),evidence(evidence_id='e2',replaces='e1'))
        self.assertIs(evaluate(ev).status,Status.BLOCK)

    def test_raw_and_normalized_digests_not_interchangeable(self):
        e=evidence(target=target(raw_digest='1'*64,normalized_digest='0'*64))
        self.assertIs(evaluate((e,)).status,Status.BLOCK)

    def test_truthy_fields_do_not_enter_mapping(self):
        e=evidence()
        values={f.name:getattr(e,f.name) for f in a.fields(e)}
        self.assertEqual(a.evidence_from_mapping(values),e)
        for name in ('trusted','verified','public_key'):
            with self.assertRaises(ValueError):a.evidence_from_mapping(dict(values,**{name:True}))

class ERR014Regressions(unittest.TestCase):
    def test_A_older_correction_is_block(self):
        old=evidence(evidence_id='old',issued_at='2026-01-08T17:00:00+09:00')
        new=evidence(evidence_id='new',issued_at='2026-01-08T16:00:00+09:00',corrects='old')
        self.assertIs(evaluate((old,new)).status,Status.BLOCK)

    def test_B_distinct_double_reference_is_block(self):
        values=(evidence(evidence_id='old1'),evidence(evidence_id='old2'),
                evidence(evidence_id='new',corrects='old1',replaces='old2'))
        self.assertIs(evaluate(values).status,Status.BLOCK)

    def test_C_long_expected_time_never_inspects_target(self):
        out=evaluate();expected=target()
        with patch.object(a,'_target',wraps=a._target) as inspect, \
             patch.object(a,'timestamp',wraps=a.timestamp) as parse:
            result=a.revalidate(out,target=expected,evaluated_at='x'*257)
            self.assertIs(result.status,Status.BLOCK)
            inspect.assert_not_called();parse.assert_not_called()

    def test_both_relations_strict_time_matrix(self):
        old=evidence(evidence_id='old',issued_at='2026-01-08T17:00:00+09:00')
        for relation in ('corrects','replaces'):
            for instant,blocked in (
                ('2026-01-08T16:59:59+09:00',True),
                ('2026-01-08T17:00:00+09:00',True),
                ('2026-01-08T08:00:00Z',True),
                ('2026-01-08T08:00:00.000001Z',False),
                ('2026-01-08T17:00:01+09:00',False)):
                new=evidence(evidence_id='new',issued_at=instant,**{relation:'old'})
                for values in ((old,new),(new,old)):
                    with self.subTest(relation=relation,instant=instant):
                        result=evaluate(values)
                        self.assertIs(result.status,Status.BLOCK if blocked else Status.UNVERIFIED)
                        self.assertEqual('replacement_time_conflict' in result.reasons,blocked)

    def test_same_double_reference_is_single_valid_edge(self):
        old=evidence(evidence_id='old',issued_at='2026-01-08T16:00:00+09:00')
        new=evidence(evidence_id='new',issued_at='2026-01-08T17:00:00+09:00',corrects='old',replaces='old')
        result=evaluate((old,new))
        self.assertIs(result.status,Status.UNVERIFIED)
        self.assertNotIn('replacement_conflict',result.reasons)

    def test_missing_reference_not_given_invented_time(self):
        for relation in ('corrects','replaces'):
            result=evaluate((evidence(**{relation:'missing'}),))
            self.assertIs(result.status,Status.UNVERIFIED)
            self.assertNotIn('replacement_time_conflict',result.reasons)
        self.assertIs(evaluate((evidence(corrects='missing',replaces='missing'),)).status,Status.UNVERIFIED)
        self.assertIs(evaluate((evidence(corrects='missing1',replaces='missing2'),)).status,Status.BLOCK)

    def test_late_conflict_not_short_circuited(self):
        base=evidence(evidence_id='base',issued_at='2026-01-08T16:00:00+09:00')
        good=evidence(evidence_id='good',issued_at='2026-01-08T17:00:00+09:00',corrects='base')
        bad=evidence(evidence_id='bad',issued_at='2026-01-08T16:30:00+09:00',replaces='good')
        out=evaluate((evidence(evidence_id='unknown',corrects='absent'),base,good,bad))
        self.assertIs(out.status,Status.BLOCK)
        self.assertIn('replacement_time_conflict',out.reasons)
        self.assertIn('trust_registration_unimplemented',out.reasons)

    def test_constructed_child_changed_to_older_or_invalid_time(self):
        old=evidence(evidence_id='old',issued_at='2026-01-08T16:00:00+09:00')
        for instant in ('2026-01-08T15:00:00+09:00','invalid','x'*257,[],None):
            new=evidence(evidence_id='new',issued_at='2026-01-08T17:00:00+09:00',corrects='old')
            object.__setattr__(new,'issued_at',instant)
            self.assertIs(evaluate((old,new)).status,Status.BLOCK)

    def test_early_revalidation_type_blank_length_and_iso_guards(self):
        out=evaluate();expected=target()
        for bad in (None,[],True,'',' ','x'*257,'invalid-ISO'):
            with self.subTest(value=bad),patch.object(a,'_target',wraps=a._target) as child:
                result=a.revalidate(out,target=expected,evaluated_at=bad)
                self.assertIs(result.status,Status.BLOCK);child.assert_not_called()
        for size in (255,256):
            prefix,suffix='2026-01-08T18:00:00.','+09:00'
            time=prefix+'0'*(size-len(prefix)-len(suffix))+suffix
            self.assertEqual(len(time),size)
            self.assertEqual(a.revalidate(out,target=expected,evaluated_at=time),out)

    def test_matching_double_edges_do_not_expand_exponentially(self):
        from datetime import datetime,timedelta
        start=datetime.fromisoformat('2026-01-08T16:00:00+09:00')
        values=tuple(evidence(evidence_id='e'+str(i),issued_at=(start+timedelta(seconds=i)).isoformat(),
                             corrects='e'+str(i-1) if i else None,
                             replaces='e'+str(i-1) if i else None) for i in range(64))
        result=evaluate(values)
        self.assertIs(result.status,Status.UNVERIFIED)
        self.assertNotIn('resource_limit',result.reasons)

    def test_new_conflicts_never_pass_or_authorize(self):
        out=evaluate((evidence(corrects='a',replaces='b'),))
        self.assertIs(out.status,Status.BLOCK)
        with self.assertRaises(ValueError):replace(out,status=Status.PASS)
        for property in ('analysis_input_allowed','verified_performance_allowed','orders_allowed'):
            self.assertFalse(getattr(out,property))
        object.__setattr__(out,'status',Status.PASS)
        self.assertIs(a.revalidate(out,target=target(),evaluated_at=AT).status,Status.BLOCK)
