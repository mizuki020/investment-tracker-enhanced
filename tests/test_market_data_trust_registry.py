"""Synthetic trust claim tests. No real keys, trust registration or signature checks."""
import unittest
from dataclasses import replace
from unittest.mock import patch
from market_data import trust_registry as r
from market_data.quality_gates import Status

AT='2026-01-08T18:00:00+09:00'
START='2026-01-08T00:00:00+09:00'
END='2026-01-09T00:00:00+09:00'
def scope(**kw):return replace(r.KeyScope(r.KeyUse.PROVIDER,'TSE','daily','2026-01-05','2026-01-05',('SYNTH',)),**kw)
def request(**kw):return replace(r.RegistrationRequest('registration-request/1','request1','registrant','manager','issuer','key1','ed25519',b'\x01'*32,scope(),(r.KeyUse.PROVIDER,),START,START,END),**kw)
def approval(req=None,**kw):return replace(r.ApprovalRecord('approval-record/1','approval1','reviewer','manager',request() if req is None else req,1,AT,START,END,b'synthetic','unknown'),**kw)
def candidate(**kw):return replace(r.RegistryCandidate('registry-candidate/1','registry1',1,0,(request(),),(approval(),)),**kw)
def inspect(value=None,**kw):return r.inspect_registry(candidate() if value is None else value,evaluated_at=kw.get('evaluated_at',AT))

class RegistryTests(unittest.TestCase):
    def test_valid_structure_unverified(self):self.assertIs(inspect().status,Status.UNVERIFIED)
    def test_self_approval(self):self.assertIs(inspect(candidate(approvals=(approval(approver='registrant'),))).status,Status.BLOCK)
    def test_binding_mismatch(self):
        for kw in (dict(key_id='other'),dict(issuer='other'),dict(public_key=b'\x02'*32),dict(scope=scope(market='OTHER')),dict(scope=scope(end='2026-01-06')),dict(scope=scope(use=r.KeyUse.COLLECTOR),permitted_uses=(r.KeyUse.COLLECTOR,))):
            self.assertIs(inspect(candidate(approvals=(approval(request(**kw)),))).status,Status.BLOCK)
    def test_duplicate_request_and_key(self):
        for req in (request(),request(request_id='other'),request(public_key=b'\x02'*32)):
            self.assertIs(inspect(candidate(requests=(request(),req))).status,Status.BLOCK)
    def test_state_mismatch_and_reversal(self):
        self.assertIs(inspect(candidate(approvals=(approval(state_version=2),))).status,Status.BLOCK)
        c=candidate();object.__setattr__(c,'previous_version',1)
        self.assertIs(inspect(c).status,Status.BLOCK)
    def test_unknown_root_and_revocation(self):
        for value in ('unknown','active','revoked'):
            out=inspect(candidate(approvals=(approval(revocation=value),)))
            self.assertIs(out.status,Status.UNVERIFIED);self.assertIn('revocation_unverified',out.reasons)
    def test_direct_pass_and_result_tamper(self):
        out=inspect()
        with self.assertRaises(ValueError):replace(out,status=Status.PASS)
        object.__setattr__(out,'status',Status.PASS)
        self.assertIs(r.revalidate_inspection(out,candidate=candidate(),evaluated_at=AT).status,Status.BLOCK)
    def test_child_tamper(self):
        c=candidate();object.__setattr__(c.requests[0].scope,'codes',[])
        self.assertIs(inspect(c).status,Status.BLOCK)
    def test_time_boundaries(self):
        prefix,suffix='2026-01-08T18:00:00.','+09:00'
        for size in (255,256,257):
            time=prefix+'0'*(size-len(prefix)-len(suffix))+suffix
            self.assertIs(inspect(evaluated_at=time).status,Status.BLOCK if size>256 else Status.UNVERIFIED)
    def test_generator_not_consumed(self):
        calls=[]
        def gen():calls.append(1);yield request()
        c=candidate();object.__setattr__(c,'requests',gen())
        self.assertIs(inspect(c).status,Status.BLOCK);self.assertEqual(calls,[])
    def test_late_block(self):
        req=request(request_id='r2',key_id='k2')
        c=candidate(requests=(request(),req),approvals=(approval(),approval(req,approval_id='a2',approver='registrant')))
        self.assertIs(inspect(c).status,Status.BLOCK)
    def test_fixed_exception(self):
        c=candidate()
        with patch.object(r,'_inspect',side_effect=RuntimeError('secret value')):
            out=inspect(c)
        self.assertEqual(out.reasons,('evaluation_error',));self.assertNotIn('secret',repr(out))
    def test_permissions_false(self):
        out=inspect()
        for prop in ('analysis_input_allowed','verified_performance_allowed','store_allowed','external_ai_allowed','orders_allowed'):
            self.assertFalse(getattr(out,prop))
    def test_missing(self):
        self.assertIs(inspect(candidate(requests=(),approvals=())).status,Status.UNVERIFIED)
        self.assertIn('approval_missing',inspect(candidate(approvals=())).reasons)
    def test_unknown_fields(self):
        with self.assertRaises(ValueError):r.candidate_from_mapping({'trusted':True})
        with self.assertRaises(TypeError):r.RegistryCandidate(trusted=True)

    def test_counts_minus_at_plus_limit(self):
        for count in (63,64):
            reqs=tuple(request(request_id='r'+str(i),key_id='k'+str(i)) for i in range(count))
            self.assertIs(inspect(candidate(requests=reqs,approvals=())).status,Status.UNVERIFIED)
        c=candidate();object.__setattr__(c,'requests',(object(),)*65)
        with patch.object(r,'_plain',side_effect=AssertionError('no expand')) as expand, \
             patch.object(r,'_semantic',side_effect=AssertionError('no semantic')) as semantic:
            out=inspect(c)
            self.assertEqual(out.reasons,('resource_limit',));expand.assert_not_called();semantic.assert_not_called()

    def test_text_and_time_early_guards(self):
        for size in (255,256):self.assertIs(inspect(candidate(registry_id='r'*size)).status,Status.UNVERIFIED)
        with self.assertRaises(ValueError):candidate(registry_id='r'*257)
        c=candidate()
        for bad in (None,[],True,'',' ','x'*257):
            with patch.object(r,'timestamp',side_effect=AssertionError('no parse')) as parser, \
                 patch.object(r,'_preflight',side_effect=AssertionError('no children')) as children:
                self.assertIs(inspect(c,evaluated_at=bad).status,Status.BLOCK)
                parser.assert_not_called();children.assert_not_called()

    def test_all_child_text_before_semantic_parsing(self):
        c=candidate();object.__setattr__(c.approvals[0],'issued_at','x'*257)
        with patch.object(r,'_semantic',side_effect=AssertionError('no semantic')) as semantic:
            self.assertIs(inspect(c).status,Status.BLOCK);semantic.assert_not_called()

    def test_permission_exclusion_and_management_mismatch(self):
        c=candidate();object.__setattr__(c.requests[0],'permitted_uses',())
        self.assertIn('use_outside_claim',inspect(c).reasons)
        self.assertIs(inspect(candidate(approvals=(approval(management_id='other'),))).status,Status.BLOCK)

    def test_subclasses_and_iterators_not_consumed(self):
        class Evil(tuple):
            def __iter__(self):raise AssertionError('iteration')
        class Never:
            def __iter__(self):raise AssertionError('iteration')
        for value in (Evil(),Never(),[]):
            c=candidate();object.__setattr__(c,'approvals',value)
            self.assertIs(inspect(c).status,Status.BLOCK)

    def test_record_byte_exact_boundaries(self):
        large=scope(codes=tuple(str(i).zfill(2)+'😀'*253 for i in range(60)))
        req=request(scope=large)
        base=approval(req,signature=b'')
        for size in (65535,65536,65537):
            extra=(size-r._size(base))%2
            sized=replace(base,approval_id=base.approval_id+'x'*extra)
            length=(size-r._size(sized))//2
            self.assertTrue(0<=length<=4096)
            if size>65536:
                with self.assertRaises(ValueError):replace(sized,signature=b'x'*length)
            else:
                record=replace(sized,signature=b'x'*length)
                self.assertEqual(r._size(record),size)
                self.assertIs(inspect(candidate(requests=(req,),approvals=(record,))).status,Status.UNVERIFIED)

    def test_total_byte_cap_before_semantics(self):
        # All record sizes remain below 64KiB, but full candidate exceeds 1MiB.
        reqs=tuple(request(request_id='r'+str(i),key_id='k'+str(i),
                           scope=scope(codes=tuple(str(j).zfill(2)+'😀'*253 for j in range(18)))) for i in range(64))
        c=candidate();object.__setattr__(c,'requests',reqs);object.__setattr__(c,'approvals',())
        self.assertTrue(all(r._size(v)<=65536 for v in reqs))
        self.assertGreater(r._size(c),1048576)
        with patch.object(r,'_semantic',side_effect=AssertionError('no semantic')) as semantic:
            self.assertEqual(inspect(c).reasons,('resource_limit',));semantic.assert_not_called()

    def test_duplicate_approval_and_actor(self):
        for second in (approval(),approval(approval_id='other')):
            self.assertIs(inspect(candidate(approvals=(approval(),second))).status,Status.BLOCK)

    def test_mutable_result_and_context_reuse(self):
        out=inspect()
        with self.assertRaises(ValueError):replace(out,reasons=list(out.reasons))
        other=candidate(registry_id='other')
        self.assertIs(r.revalidate_inspection(out,candidate=other,evaluated_at=AT).status,Status.BLOCK)
        other=candidate(approvals=(approval(approver='registrant'),))
        self.assertIs(r.revalidate_inspection(out,candidate=other,evaluated_at=AT).status,Status.BLOCK)

    def test_validity_and_future_claims(self):
        self.assertIs(inspect(evaluated_at=END).status,Status.BLOCK)
        c=candidate();object.__setattr__(c.requests[0],'submitted_at','2026-01-09T01:00:00+09:00')
        self.assertIs(inspect(c).status,Status.BLOCK)
        c=candidate();object.__setattr__(c.approvals[0],'valid_until',START)
        self.assertIs(inspect(c).status,Status.BLOCK)

    def test_total_byte_exact_boundaries(self):
        large=scope(codes=tuple(str(i).zfill(2)+'😀'*253 for i in range(60)))
        reqs=tuple(request(request_id='r'+str(i),key_id='k'+str(i),scope=large) for i in range(18))
        for limit in (1048575,1048576,1048577):
            c=candidate();object.__setattr__(c,'requests',reqs);object.__setattr__(c,'approvals',())
            excess=r._size(c)-limit
            self.assertGreater(excess,0)
            codes=list(large.codes)
            # Trim 4-byte emoji, then add 0..3 ASCII bytes to obtain exact size.
            remaining=(excess+3)//4
            for i in range(len(codes)):
                remove=min(253,remaining);remaining-=remove
                if remove:codes[i]=codes[i][:-remove]
            self.assertEqual(remaining,0)
            codes[0]+='x'*((-excess)%4)
            last=replace(reqs[-1],scope=replace(large,codes=tuple(codes)))
            object.__setattr__(c,'requests',reqs[:-1]+(last,))
            self.assertEqual(r._size(c),limit)
            self.assertIs(inspect(c).status,Status.BLOCK if limit>1048576 else Status.UNVERIFIED)

    def test_oversize_before_any_datetime_parse(self):
        c=candidate();object.__setattr__(c,'requests',(object(),)*65)
        with patch.object(r,'timestamp',side_effect=AssertionError('no parse')) as parser:
            self.assertEqual(inspect(c).reasons,('resource_limit',));parser.assert_not_called()

    def test_whitespace_identity_aliases_rejected(self):
        for name in ('registrant',' issuer','reviewer '):
            if name=='registrant':continue
            with self.assertRaises(ValueError):approval(approver=name)

class BindingRegressions(unittest.TestCase):
    def test_ERR016_consistently_changed_public_key_rejected(self):
        first=candidate();out=inspect(first)
        changed=request(public_key=b'\x02'*32)
        second=candidate(requests=(changed,),approvals=(approval(changed),))
        self.assertIs(inspect(second).status,Status.UNVERIFIED)
        self.assertIs(r.revalidate_inspection(out,candidate=second,evaluated_at=AT).status,Status.BLOCK)

    def test_ERR017_count_rejects_before_datetime(self):
        first=candidate();out=inspect(first)
        object.__setattr__(first,'requests',(object(),)*65)
        with patch.object(r,'timestamp',wraps=r.timestamp) as parser:
            result=r.revalidate_inspection(out,candidate=first,evaluated_at=AT)
            self.assertIs(result.status,Status.BLOCK)
            parser.assert_not_called()

    def test_all_request_fields_bind_even_when_approval_matches(self):
        out=inspect(candidate())
        changes=(dict(request_id='other'),dict(registrant='another'),dict(management_id='other'),
                 dict(issuer='other'),dict(key_id='other'),dict(public_key=b'\x02'*32),
                 dict(scope=scope(market='OTHER')),dict(scope=scope(dataset='other')),
                 dict(scope=scope(start='2026-01-04')),dict(scope=scope(end='2026-01-06')),
                 dict(scope=scope(codes=('OTHER',))),
                 dict(scope=scope(use=r.KeyUse.COLLECTOR),permitted_uses=(r.KeyUse.COLLECTOR,)),
                 dict(permitted_uses=(r.KeyUse.PROVIDER,r.KeyUse.TIME)),
                 dict(submitted_at='2026-01-08T01:00:00+09:00'),
                 dict(valid_from='2026-01-07T00:00:00+09:00'),
                 dict(valid_until='2026-01-10T00:00:00+09:00'))
        for change in changes:
            req=request(**change)
            c=candidate(requests=(req,),approvals=(approval(req,management_id=req.management_id),))
            self.assertIs(inspect(c).status,Status.UNVERIFIED)
            result=r.revalidate_inspection(out,candidate=c,evaluated_at=AT)
            self.assertIs(result.status,Status.BLOCK)
            self.assertEqual(result.reasons,('candidate_mismatch',))

    def test_approval_candidate_fields_and_schema_are_bound(self):
        base=candidate();out=inspect(base)
        for changes in (dict(approval_id='other'),dict(approver='other'),dict(signature=b'other'),
                        dict(revocation='active'),dict(issued_at='2026-01-08T17:00:00+09:00'),
                        dict(valid_from='2026-01-08T01:00:00+09:00'),
                        dict(valid_until='2026-01-08T23:00:00+09:00')):
            c=candidate(approvals=(approval(**changes),))
            self.assertIs(inspect(c).status,Status.UNVERIFIED)
            self.assertIs(r.revalidate_inspection(out,candidate=c,evaluated_at=AT).status,Status.BLOCK)
        for changes in (dict(registry_id='other'),dict(state_version=2,previous_version=1,approvals=(approval(state_version=2),))):
            self.assertIs(r.revalidate_inspection(out,candidate=candidate(**changes),evaluated_at=AT).status,Status.BLOCK)
        for obj,field in ((base,'schema_version'),(base.requests[0],'schema_version'),(base.approvals[0],'schema_version')):
            c=candidate()
            target=c if obj is base else c.requests[0] if obj is base.requests[0] else c.approvals[0]
            object.__setattr__(target,field,'unsupported')
            self.assertIs(r.revalidate_inspection(out,candidate=c,evaluated_at=AT).status,Status.BLOCK)

    def test_independent_equal_candidate_and_order_contract(self):
        import copy
        c=candidate();out=inspect(c)
        self.assertEqual(r.revalidate_inspection(out,candidate=copy.deepcopy(c),evaluated_at=AT),out)
        req2=request(request_id='r2',key_id='k2')
        ordered=candidate(requests=(request(),req2),approvals=(approval(),approval(req2,approval_id='a2')))
        reordered=replace(ordered,requests=tuple(reversed(ordered.requests)))
        self.assertNotEqual(inspect(ordered).candidate_digest,inspect(reordered).candidate_digest)

    def test_binding_distinguishes_boundaries_unicode_and_bytes(self):
        variants=(request(registrant='ab',issuer='c'),request(registrant='a',issuer='bc'),
                  request(registrant='é'),request(registrant='e\u0301'),
                  request(public_key=b'a'*32),request(public_key=b'b'*32))
        digests=[]
        for req in variants:
            digests.append(inspect(candidate(requests=(req,),approvals=(approval(req),))).candidate_digest)
        self.assertEqual(len(set(digests)),len(variants))
        import hashlib,json
        c=candidate()
        # Domain is explicit and schema/policy-scoped, rather than a plain JSON hash.
        raw=json.dumps(r._binding_value(c),sort_keys=True,separators=(',',':'),ensure_ascii=False).encode('utf-8')
        self.assertEqual(inspect(c).candidate_digest,hashlib.sha256(r.BINDING_DOMAIN+raw).hexdigest())
        self.assertNotEqual(inspect(c).candidate_digest,hashlib.sha256(raw).hexdigest())

    def test_bad_result_binding_direct_construction_and_tampering(self):
        c=candidate();out=inspect(c)
        for bad in (None,'x','g'*64,[],True):
            with self.assertRaises(ValueError):replace(out,candidate_digest=bad)
        changed=replace(out,candidate_digest='0'*64)
        self.assertIs(r.revalidate_inspection(changed,candidate=c,evaluated_at=AT).status,Status.BLOCK)
        object.__setattr__(out,'candidate_digest',[])
        self.assertIs(r.revalidate_inspection(out,candidate=c,evaluated_at=AT).status,Status.BLOCK)
        out=inspect(c);object.__setattr__(out,'status',Status.PASS)
        self.assertIs(r.revalidate_inspection(out,candidate=c,evaluated_at=AT).status,Status.BLOCK)

    def test_all_size_failures_before_parse_or_hash_in_both_entries(self):
        out=inspect(candidate())
        over_count=candidate();object.__setattr__(over_count,'requests',(object(),)*65)
        over_signature=candidate();object.__setattr__(over_signature.approvals[0],'signature',b'x'*4097)
        large=scope(codes=tuple(str(i).zfill(2)+'😀'*253 for i in range(60)))
        req=request(scope=large);record=approval(req,signature=b'')
        # Exact 65537-byte record, kept within the primitive signature limit.
        parity=(65537-r._size(record))%2
        record=replace(record,approval_id=record.approval_id+'x'*parity)
        object.__setattr__(record,'signature',b'x'*((65537-r._size(record))//2))
        self.assertEqual(r._size(record),65537)
        over_record=candidate();object.__setattr__(over_record,'requests',(req,));object.__setattr__(over_record,'approvals',(record,))
        over_total=candidate()
        reqs=tuple(request(request_id='r'+str(i),key_id='k'+str(i),scope=large) for i in range(18))
        object.__setattr__(over_total,'requests',reqs);object.__setattr__(over_total,'approvals',())
        self.assertGreater(r._size(over_total),1048576)
        for c in (over_count,over_signature,over_record,over_total):
            with patch.object(r,'timestamp',side_effect=AssertionError('no parse')) as parse, \
                 patch.object(r.hashlib,'sha256',side_effect=AssertionError('no hash')) as hashed:
                self.assertIs(r.inspect_registry(c,evaluated_at=AT).status,Status.BLOCK)
                self.assertIs(r.revalidate_inspection(out,candidate=c,evaluated_at=AT).status,Status.BLOCK)
                parse.assert_not_called();hashed.assert_not_called()

    def test_bad_result_time_text_precedes_candidate_scan(self):
        c=candidate();out=inspect(c);object.__setattr__(out,'evaluated_at','x'*257)
        with patch.object(r,'_bounded_candidate',side_effect=AssertionError('no scan')) as scan, \
             patch.object(r,'timestamp',side_effect=AssertionError('no parse')) as parse:
            self.assertIs(r.revalidate_inspection(out,candidate=c,evaluated_at=AT).status,Status.BLOCK)
            scan.assert_not_called();parse.assert_not_called()

    def test_exception_fixed_and_permissions_stay_false(self):
        c=candidate();out=inspect(c)
        with patch.object(r,'_candidate_digest',side_effect=RuntimeError('secret-key-material')):
            failed=r.inspect_registry(c,evaluated_at=AT)
            self.assertEqual(failed.reasons,('evaluation_error',));self.assertNotIn('secret-key-material',repr(failed))
            self.assertIs(r.revalidate_inspection(out,candidate=c,evaluated_at=AT).status,Status.BLOCK)
        blocked=inspect(candidate(approvals=(approval(approver='registrant'),)))
        self.assertIs(blocked.status,Status.BLOCK)
        for value in (out,blocked):
            for prop in ('analysis_input_allowed','verified_performance_allowed','store_allowed','external_ai_allowed','orders_allowed'):
                self.assertFalse(getattr(value,prop))

class ResultMetadataRegressions(unittest.TestCase):
    def test_registry257_rejects_before_datetime_and_hash(self):
        c=candidate();out=inspect(c);object.__setattr__(out,'registry_id','x'*257)
        with patch.object(r,'timestamp',wraps=r.timestamp) as parser, \
             patch.object(r.hashlib,'sha256',wraps=r.hashlib.sha256) as hashed:
            result=r.revalidate_inspection(out,candidate=c,evaluated_at=AT)
            self.assertEqual(result.reasons,('invalid_decision',))
            parser.assert_not_called();hashed.assert_not_called()

    def test_state_overflow_rejects_before_datetime_and_hash(self):
        c=candidate();out=inspect(c);object.__setattr__(out,'state_version',2147483648)
        with patch.object(r,'timestamp',wraps=r.timestamp) as parser, \
             patch.object(r.hashlib,'sha256',wraps=r.hashlib.sha256) as hashed:
            result=r.revalidate_inspection(out,candidate=c,evaluated_at=AT)
            self.assertEqual(result.reasons,('invalid_decision',))
            parser.assert_not_called();hashed.assert_not_called()

    def test_direct_constructor_metadata_failures_are_early(self):
        out=inspect(candidate())
        for changes in (dict(registry_id='x'*257),dict(state_version=2147483648)):
            with patch.object(r,'timestamp',wraps=r.timestamp) as parse, \
                 patch.object(r.hashlib,'sha256',wraps=r.hashlib.sha256) as hashed:
                with self.assertRaises(ValueError):replace(out,**changes)
                parse.assert_not_called();hashed.assert_not_called()

    def test_valid_registry_length_and_version_boundaries(self):
        for length in (255,256):
            c=candidate(registry_id='r'*length);out=inspect(c)
            self.assertEqual(r.revalidate_inspection(out,candidate=c,evaluated_at=AT),out)
        out=inspect(candidate())
        self.assertEqual(replace(out,state_version=2147483647).state_version,2147483647)
        for bad in (2147483648,-1,0,True,'1',[],None):
            with patch.object(r,'timestamp',wraps=r.timestamp) as parse:
                with self.assertRaises(ValueError):replace(out,state_version=bad)
                parse.assert_not_called()

    def test_every_lightweight_result_field_precedes_candidate_walk(self):
        c=candidate();original=inspect(c)
        violations=(dict(status='UNVERIFIED'),dict(status=Status.PASS),dict(policy_version='x'*257),
                    dict(policy_version='other'),dict(registry_id=''),dict(registry_id=' '),
                    dict(registry_id=' registry'),dict(registry_id=[]),dict(registry_id=None),
                    dict(state_version=True),dict(state_version=-1),dict(state_version='1'),
                    dict(candidate_digest='x'*257),dict(candidate_digest='g'*64),dict(candidate_digest=[]),
                    dict(candidate_digest=None),dict(reasons=[]),dict(reasons=()),
                    dict(reasons=('x'*257,)),dict(reasons=('unrecognized',)),
                    dict(reasons=original.reasons+original.reasons),
                    dict(evaluated_at='x'*257),dict(evaluated_at=''),dict(evaluated_at=[]),dict(evaluated_at=None))
        import copy
        for changes in violations:
            out=copy.copy(original)
            for name,value in changes.items():object.__setattr__(out,name,value)
            with self.subTest(changes=changes), \
                 patch.object(r,'timestamp',wraps=r.timestamp) as parse, \
                 patch.object(r.hashlib,'sha256',wraps=r.hashlib.sha256) as hashed, \
                 patch.object(r,'_bounded_candidate',side_effect=AssertionError('no scan')) as scan:
                result=r.revalidate_inspection(out,candidate=c,evaluated_at=AT)
                self.assertEqual(result.reasons,('invalid_decision',))
                parse.assert_not_called();hashed.assert_not_called();scan.assert_not_called()
            with patch.object(r,'timestamp',wraps=r.timestamp) as parse:
                with self.assertRaises(ValueError):replace(original,**changes)
                parse.assert_not_called()

    def test_result_iterator_not_consumed(self):
        out=inspect(candidate());c=candidate();calls=[]
        def gen():calls.append(1);yield 'invalid_decision'
        object.__setattr__(out,'reasons',gen())
        with patch.object(r,'timestamp',wraps=r.timestamp) as parse:
            self.assertIs(r.revalidate_inspection(out,candidate=c,evaluated_at=AT).status,Status.BLOCK)
            parse.assert_not_called()
        self.assertEqual(calls,[])

    def test_invalid_result_and_candidate_fail_before_processing(self):
        c=candidate();out=inspect(c)
        object.__setattr__(out,'registry_id','x'*257)
        object.__setattr__(c,'requests',(object(),)*65)
        with patch.object(r,'timestamp',wraps=r.timestamp) as parse, \
             patch.object(r.hashlib,'sha256',wraps=r.hashlib.sha256) as hashed:
            result=r.revalidate_inspection(out,candidate=c,evaluated_at=AT)
            self.assertEqual(result.reasons,('invalid_decision',))
            parse.assert_not_called();hashed.assert_not_called()

    def test_equal_copies_binding_and_permissions_unchanged(self):
        import copy
        c=candidate();out=inspect(c)
        self.assertEqual(r.revalidate_inspection(out,candidate=copy.deepcopy(c),evaluated_at=AT),out)
        altered=request(public_key=b'\x02'*32)
        other=candidate(requests=(altered,),approvals=(approval(altered),))
        result=r.revalidate_inspection(out,candidate=other,evaluated_at=AT)
        self.assertEqual(result.reasons,('candidate_mismatch',))
        for value in (out,result):
            for prop in ('analysis_input_allowed','verified_performance_allowed','store_allowed','external_ai_allowed','orders_allowed'):
                self.assertFalse(getattr(value,prop))
