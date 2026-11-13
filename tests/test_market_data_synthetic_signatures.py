"""Synthetic Ed25519 fixtures only. Private keys exist only in test memory."""
import copy
import hashlib
import unittest
from dataclasses import replace
from unittest.mock import patch
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey,Ed25519PublicKey
from cryptography.hazmat.primitives.serialization import Encoding,PublicFormat
from market_data import synthetic_signatures as s,trust_registry as r,authenticity as a
from market_data.quality_gates import Purpose,Status
from nacl.bindings import crypto_core as sodium_core
from nacl.bindings import crypto_core_ed25519_add
from nacl.exceptions import UnavailableError

AT='2026-01-08T18:00:00+09:00';START='2026-01-08T00:00:00+09:00';END='2026-01-09T00:00:00+09:00'
def fixture(raw=b'synthetic raw',normalized=b'synthetic normalized',key_id='key',key_use=r.KeyUse.PROVIDER):
    private=Ed25519PrivateKey.from_private_bytes(bytes(range(32)))
    public=private.public_key().public_bytes(Encoding.Raw,PublicFormat.Raw)
    scope=r.KeyScope(key_use,'TSE','daily','2026-01-01','2026-01-31',('SYNTH',))
    req=r.RegistrationRequest('registration-request/1','request','person','manager','issuer',key_id,'ed25519',public,scope,(key_use,),START,START,END)
    approval=r.ApprovalRecord('approval-record/1','approval','reviewer','manager',req,1,AT,START,END,b'opaque-claim','unknown')
    candidate=r.RegistryCandidate('registry-candidate/1','registry',1,0,(req,),(approval,))
    digest=r.inspect_registry(candidate,evaluated_at=AT).candidate_digest
    target=a.Target('SYNTH','TSE','2026-01-05','2026-01-05','unadjusted','v1',hashlib.sha256(raw).hexdigest(),hashlib.sha256(normalized).hexdigest(),'synthetic-bytes','1')
    statement=s.SigningStatement('signing-statement/1','synthetic','issuer',key_id,'ed25519',key_use,'daily',Purpose.HISTORICAL_RESEARCH,target,digest,AT,('synthetic-fixture',))
    context=s.VerificationContext('signature-context/1',Purpose.HISTORICAL_RESEARCH,AT,('synthetic-fixture',))
    signature=private.sign(s.signing_bytes(statement))
    return s.SignatureInput('signature-input/1',statement,public,signature,raw,normalized,candidate,context),private

class SyntheticSignatureTests(unittest.TestCase):
    def test_valid_is_unverified_not_permission(self):
        value,_=fixture();out=s.evaluate_signature(value)
        self.assertIs(out.crypto_state,s.CryptoState.VALID);self.assertIs(out.status,Status.UNVERIFIED)
        for prop in ('analysis_input_allowed','verified_performance_allowed','store_allowed','external_ai_allowed','orders_allowed'):
            self.assertFalse(getattr(out,prop))
    def test_rfc8032_vector1(self):
        pub=bytes.fromhex('d75a980182b10ab7d54bfed3c964073a0ee172f3daa62325af021a68f707511a')
        sig=bytes.fromhex('e5564300c360ac729086e2cc806e828a84877f1eb8e5d974d873e065224901555fb8821590a33bacc61e39701cf9b46bd25bf5f0595bbe24655141438e7a100b')
        Ed25519PublicKey.from_public_bytes(pub).verify(sig,b'')
    def test_payload_and_signature_one_byte_mutation(self):
        value,_=fixture()
        self.assertIs(s.evaluate_signature(replace(value,raw=b'X'+value.raw[1:])).status,Status.BLOCK)
        bad=bytes([value.signature[0]^1])+value.signature[1:]
        out=s.evaluate_signature(replace(value,signature=bad))
        self.assertIs(out.crypto_state,s.CryptoState.INVALID);self.assertIn('signature_invalid',out.reasons)
    def test_different_signing_key(self):
        value,_=fixture();other=Ed25519PrivateKey.from_private_bytes(b'\x02'*32)
        self.assertIs(s.evaluate_signature(replace(value,signature=other.sign(s.signing_bytes(value.statement)))).crypto_state,s.CryptoState.INVALID)
    def test_unknown_key_not_checked(self):
        value,key=fixture();statement=replace(value.statement,key_id='unknown')
        out=s.evaluate_signature(replace(value,statement=statement,signature=key.sign(s.signing_bytes(statement))))
        self.assertIs(out.crypto_state,s.CryptoState.NOT_CHECKED);self.assertIs(out.status,Status.UNVERIFIED)
    def test_key_issuer_and_scope_mismatch(self):
        value,key=fixture()
        for changes in (dict(issuer='other'),dict(key_use=r.KeyUse.COLLECTOR),dict(dataset='other'),dict(target=replace(value.statement.target,market='OTHER'))):
            statement=replace(value.statement,**changes)
            out=s.evaluate_signature(replace(value,statement=statement,signature=key.sign(s.signing_bytes(statement))))
            self.assertIs(out.status,Status.BLOCK)
        self.assertIs(s.evaluate_signature(replace(value,public_key=b'\x02'*32)).status,Status.BLOCK)
    def test_key_signature_lengths(self):
        value,_=fixture()
        for field,sizes in (('public_key',(31,33)),('signature',(63,65))):
            for length in sizes:
                bad=copy.copy(value);object.__setattr__(bad,field,b'x'*length)
                self.assertIs(s.evaluate_signature(bad).status,Status.BLOCK)
    def test_algorithm_rejected_before_crypto(self):
        value,_=fixture();object.__setattr__(value.statement,'algorithm','none')
        with patch.object(s,'_verify_ed25519',side_effect=AssertionError('no crypto')) as crypto:
            self.assertIs(s.evaluate_signature(value).status,Status.BLOCK);crypto.assert_not_called()
    def test_hash_roles_not_interchangeable(self):
        value,key=fixture();target=replace(value.statement.target,raw_digest=value.statement.target.normalized_digest,normalized_digest=value.statement.target.raw_digest)
        st=replace(value.statement,target=target)
        self.assertIs(s.evaluate_signature(replace(value,statement=st,signature=key.sign(s.signing_bytes(st)))).status,Status.BLOCK)
    def test_different_candidate_result_reuse(self):
        value,_=fixture();out=s.evaluate_signature(value)
        changed=replace(value,candidate=replace(value.candidate,registry_id='other'))
        self.assertIs(s.revalidate_signature(out,value=changed).status,Status.BLOCK)
    def test_different_purpose_time_result_reuse(self):
        value,_=fixture();out=s.evaluate_signature(value)
        for changes in (dict(purpose=Purpose.ANALYZE),dict(evaluated_at='2026-01-08T19:00:00+09:00')):
            changed=replace(value,context=replace(value.context,**changes))
            self.assertIs(s.revalidate_signature(out,value=changed).status,Status.BLOCK)
    def test_direct_pass_and_tampered_result(self):
        value,_=fixture();out=s.evaluate_signature(value)
        with self.assertRaises(ValueError):replace(out,status=Status.PASS)
        object.__setattr__(out,'status',Status.PASS)
        self.assertIs(s.revalidate_signature(out,value=value).status,Status.BLOCK)
    def test_resource_failures_zero_expensive_calls(self):
        value,_=fixture();bad=copy.copy(value);object.__setattr__(bad,'raw',b'x'*65537)
        with patch.object(s,'timestamp',side_effect=AssertionError('no parse')) as parse, \
             patch.object(s.hashlib,'sha256',side_effect=AssertionError('no hash')) as hashed, \
             patch.object(s,'_verify_ed25519',side_effect=AssertionError('no crypto')) as crypto:
            self.assertIs(s.evaluate_signature(bad).status,Status.BLOCK)
            parse.assert_not_called();hashed.assert_not_called();crypto.assert_not_called()
    def test_generator_not_consumed(self):
        value,_=fixture();calls=[]
        def g():calls.append(1);yield 'label'
        object.__setattr__(value.statement,'context',g())
        self.assertIs(s.evaluate_signature(value).status,Status.BLOCK);self.assertEqual(calls,[])
    def test_equal_independent_input(self):
        value,_=fixture();out=s.evaluate_signature(value)
        self.assertEqual(s.revalidate_signature(out,value=copy.deepcopy(value)),out)

    def test_every_target_field_change_is_rejected(self):
        value,_=fixture();target=value.statement.target
        changes=(dict(code='OTHER'),dict(market='OTHER'),dict(start='2026-01-04'),dict(end='2026-01-06'),
                 dict(price_basis='adjusted'),dict(data_version='v2'),dict(raw_digest='0'*64),
                 dict(normalized_digest='1'*64),dict(normalization_id='other'),dict(normalization_version='2'))
        for change in changes:
            st=replace(value.statement,target=replace(target,**change))
            self.assertIs(s.evaluate_signature(replace(value,statement=st)).status,Status.BLOCK)

    def test_order_unicode_and_field_boundaries_are_signed(self):
        value,key=fixture()
        statements=(replace(value.statement,issuer='ab',key_id='c'),
                    replace(value.statement,issuer='a',key_id='bc'),
                    replace(value.statement,context=('é',)),replace(value.statement,context=('e\u0301',)),
                    replace(value.statement,context=('one','two')),replace(value.statement,context=('two','one')))
        encoded=[s.signing_bytes(st) for st in statements]
        self.assertEqual(len(set(encoded)),len(encoded))
        for st in statements[2:]:
            changed=replace(value,statement=st,context=replace(value.context,context=st.context))
            self.assertIs(s.evaluate_signature(changed).status,Status.BLOCK)
            signed=replace(changed,signature=key.sign(s.signing_bytes(st)))
            self.assertIs(s.evaluate_signature(signed).crypto_state,s.CryptoState.VALID)

    def test_unknown_fields_json_and_surrogates_refused(self):
        value,_=fixture()
        with self.assertRaises(ValueError):s.statement_from_mapping({'trusted':True})
        with self.assertRaises(ValueError):s.statement_from_mapping('{"issuer":"x","issuer":"y"}')
        with self.assertRaises(ValueError):replace(value.statement,issuer='\ud800')
        with self.assertRaises(ValueError):replace(value.statement,issuer=' issuer')

    def test_wrong_purpose_and_future_or_invalid_time(self):
        value,key=fixture()
        self.assertIs(s.evaluate_signature(replace(value,context=replace(value.context,purpose=Purpose.ANALYZE))).status,Status.BLOCK)
        st=replace(value.statement,issued_at='2026-01-08T19:00:00+09:00')
        self.assertIn('time_conflict',s.evaluate_signature(replace(value,statement=st,signature=key.sign(s.signing_bytes(st)))).reasons)
        wrong=copy.deepcopy(value);object.__setattr__(wrong.context,'evaluated_at','2026-01-08T18:00:00')
        result=s.evaluate_signature(wrong)
        self.assertIs(result.status,Status.BLOCK)
        self.assertIsNone(result.evaluated_at)
        self.assertIsNone(result.registry_result.evaluated_at)

    def test_unknown_key_does_not_hide_later_payload_block(self):
        value,_=fixture();st=replace(value.statement,key_id='unknown')
        result=s.evaluate_signature(replace(value,statement=st,raw=b'corrupt'))
        self.assertIs(result.status,Status.BLOCK);self.assertIn('raw_digest_mismatch',result.reasons)

    def test_collector_valid_is_not_provider_authentication(self):
        value,_=fixture(key_use=r.KeyUse.COLLECTOR)
        result=s.evaluate_signature(value)
        self.assertIs(result.crypto_state,s.CryptoState.VALID)
        self.assertIs(result.status,Status.UNVERIFIED)
        self.assertIn('trust_root_unverified',result.reasons)

    def test_metadata_early_rejection_direct_and_revalidation(self):
        value,_=fixture();out=s.evaluate_signature(value)
        cases=(dict(input_digest='x'*257),dict(evaluated_at='x'*257),dict(policy_version='x'*257),
               dict(reasons=('x'*257,)),dict(context=('x'*257,)),dict(status=Status.PASS),
               dict(crypto_state='VALID'),dict(purpose='analyze'),dict(registry_result=[]))
        for changes in cases:
            mutated=copy.copy(out)
            for name,v in changes.items():object.__setattr__(mutated,name,v)
            with patch.object(s,'timestamp',wraps=s.timestamp) as parse, \
                 patch.object(s.hashlib,'sha256',wraps=s.hashlib.sha256) as hashed, \
                 patch.object(s,'_verify_ed25519',wraps=s._verify_ed25519) as crypto:
                self.assertIs(s.revalidate_signature(mutated,value=value).status,Status.BLOCK)
                with self.assertRaises(ValueError):replace(out,**changes)
                parse.assert_not_called();hashed.assert_not_called();crypto.assert_not_called()
        nested=copy.deepcopy(out);object.__setattr__(nested.registry_result,'registry_id','x'*257)
        with patch.object(s.hashlib,'sha256',wraps=s.hashlib.sha256) as hashed,patch.object(r,'timestamp',wraps=r.timestamp) as parse:
            self.assertIs(s.revalidate_signature(nested,value=value).status,Status.BLOCK)
            parse.assert_not_called();hashed.assert_not_called()

    def test_registry_budgets_before_parse_hash_crypto(self):
        value,_=fixture();out=s.evaluate_signature(value)
        bads=[]
        for field in ('requests','approvals'):
            b=copy.deepcopy(value);object.__setattr__(b.candidate,field,(object(),)*65);bads.append(b)
        b=copy.deepcopy(value);object.__setattr__(b.candidate.approvals[0],'signature',b'x'*4097);bads.append(b)
        b=copy.deepcopy(value);object.__setattr__(b.context,'context',('x',)*17);bads.append(b)
        for bad in bads:
            with patch.object(s,'timestamp',wraps=s.timestamp) as parse, \
                 patch.object(r,'timestamp',wraps=r.timestamp) as registry_parse, \
                 patch.object(s.hashlib,'sha256',wraps=s.hashlib.sha256) as hashed, \
                 patch.object(s,'_verify_ed25519',wraps=s._verify_ed25519) as crypto:
                self.assertIs(s.evaluate_signature(bad).status,Status.BLOCK)
                self.assertIs(s.revalidate_signature(out,value=bad).status,Status.BLOCK)
                parse.assert_not_called();registry_parse.assert_not_called();hashed.assert_not_called();crypto.assert_not_called()

    def test_payload_size_minus_at_plus(self):
        for size in (65535,65536):
            value,_=fixture(raw=b'x'*size,normalized=b'y'*size)
            self.assertIs(s.evaluate_signature(value).crypto_state,s.CryptoState.VALID)
        value,_=fixture();object.__setattr__(value,'normalized',b'x'*65537)
        self.assertIs(s.evaluate_signature(value).status,Status.BLOCK)

    def test_text_and_time_minus_at_plus(self):
        value,key=fixture()
        for size in (255,256):
            text='x'*size
            st=replace(value.statement,context=(text,))
            changed=replace(value,statement=st,context=replace(value.context,context=(text,)),signature=key.sign(s.signing_bytes(st)))
            self.assertIs(s.evaluate_signature(changed).crypto_state,s.CryptoState.VALID)
            prefix,suffix='2026-01-08T18:00:00.','+09:00'
            time=prefix+'0'*(size-len(prefix)-len(suffix))+suffix
            changed=replace(value,context=replace(value.context,evaluated_at=time))
            self.assertIs(s.evaluate_signature(changed).crypto_state,s.CryptoState.VALID)
        for field in ('issued_at','issuer'):
            bad=copy.deepcopy(value);object.__setattr__(bad.statement,field,'x'*257)
            self.assertIs(s.evaluate_signature(bad).status,Status.BLOCK)

    def test_snapshot_immune_to_mutation_during_crypto_use(self):
        value,_=fixture();original=copy.deepcopy(value)
        verifier=s._verify_ed25519
        def mutate_after_capture(public,signature,message):
            object.__setattr__(value.statement,'issuer','corrupted-after-capture')
            object.__setattr__(value,'raw',b'corrupted')
            return verifier(public,signature,message)
        with patch.object(s,'_verify_ed25519',side_effect=mutate_after_capture):
            result=s.evaluate_signature(value)
        self.assertIs(result.crypto_state,s.CryptoState.VALID)
        self.assertEqual(result.input_digest,s.evaluate_signature(original).input_digest)
        self.assertIs(s.revalidate_signature(result,value=value).status,Status.BLOCK)

    def test_result_digest_tamper_and_backend_exception(self):
        value,_=fixture();out=s.evaluate_signature(value)
        changed=replace(out,input_digest='0'*64)
        self.assertIs(s.revalidate_signature(changed,value=value).status,Status.BLOCK)
        with patch.object(s,'_verify_ed25519',side_effect=RuntimeError('secret text')):
            result=s.evaluate_signature(value)
            self.assertEqual(result.reasons,('verification_error',));self.assertNotIn('secret text',repr(result))

    def test_container_subclasses_and_object_types_refused(self):
        class Evil(tuple):
            def __iter__(self):raise AssertionError('must not iterate')
        value,_=fixture()
        for bad in (Evil(('label',)),['label'],None):
            clone=copy.deepcopy(value);object.__setattr__(clone.statement,'context',bad)
            self.assertIs(s.evaluate_signature(clone).status,Status.BLOCK)
        clone=copy.deepcopy(value);object.__setattr__(clone,'statement',{})
        self.assertIs(s.evaluate_signature(clone).status,Status.BLOCK)

    def test_issue_time_must_be_inside_declared_key_validity(self):
        value,key=fixture();st=replace(value.statement,issued_at='2026-01-07T23:59:59+09:00')
        changed=replace(value,statement=st,signature=key.sign(s.signing_bytes(st)))
        result=s.evaluate_signature(changed)
        self.assertIs(result.status,Status.BLOCK)
        self.assertIn('time_conflict',result.reasons)

    def test_full_input_exact_byte_budget_boundaries(self):
        value,key=fixture(raw=b'',normalized=b'')
        req=value.candidate.requests[0]
        scope=replace(req.scope,codes=('SYNTH',)+tuple(str(j).zfill(2)+'😀'*253 for j in range(15)))
        reqs=tuple(replace(req,request_id='r'+str(i),key_id=req.key_id if i==0 else 'k'+str(i),scope=scope) for i in range(64))
        candidate=replace(value.candidate,requests=reqs,approvals=())
        digest=r.inspect_registry(candidate,evaluated_at=AT).candidate_digest
        st=replace(value.statement,candidate_digest=digest)
        baseline=replace(value,candidate=candidate,statement=st)
        for size in (1048575,1048576,1048577):
            context=baseline.context
            if (size-len(s._encode(baseline)))%2:
                context=replace(context,evaluated_at='2026-01-08T18:00:00.00+09:00')
            counted=copy.copy(baseline);object.__setattr__(counted,'context',context)
            remaining=size-len(s._encode(counted))
            self.assertTrue(0<=remaining//2<=65536);self.assertEqual(remaining%2,0)
            raw=b'x'*(remaining//2)
            target=replace(st.target,raw_digest=hashlib.sha256(raw).hexdigest())
            statement=replace(st,target=target)
            signature=key.sign(s.signing_bytes(statement))
            # Copy only for the +1 case; normal constructor must reject it too.
            changed=copy.copy(counted)
            for name,v in dict(raw=raw,statement=statement,signature=signature).items():object.__setattr__(changed,name,v)
            self.assertEqual(len(s._encode(changed)),size)
            if size>1048576:
                with patch.object(s,'timestamp',wraps=s.timestamp) as parse, \
                     patch.object(s.hashlib,'sha256',wraps=s.hashlib.sha256) as hashed, \
                     patch.object(sodium_core,'crypto_core_ed25519_is_valid_point',wraps=sodium_core.crypto_core_ed25519_is_valid_point) as point, \
                     patch.object(s,'_verify_ed25519',wraps=s._verify_ed25519) as crypto:
                    self.assertIs(s.evaluate_signature(changed).status,Status.BLOCK)
                    parse.assert_not_called();hashed.assert_not_called();point.assert_not_called();crypto.assert_not_called()
                with self.assertRaises(ValueError):replace(changed)
            else:
                self.assertIs(s.evaluate_signature(replace(changed)).crypto_state,s.CryptoState.VALID)

    def test_forged_internal_valid_result_cannot_certify_bad_signature(self):
        value,_=fixture();out=s.evaluate_signature(value)
        bad=replace(value,signature=b'x'*64)
        # Self-consistent claimed input identity does not replace fresh verification.
        forged=replace(out,input_digest=s._input_digest(bad))
        self.assertIs(s.revalidate_signature(forged,value=bad).status,Status.BLOCK)
        self.assertFalse(forged.orders_allowed)


# Public fixtures only; never a validation blacklist. The seven torsion cosets
# follow libsodium test/default/core_ed25519.c, stable commit
# db1238f0a509de16b4bc323def5e68fdee78adda (j=1..7 repeated torsion8 addition).
TORSION8=bytes.fromhex('26e8958fc2b227b045c3f489f2ef98f0d5dfac05d3c63339b13802886d53fc05')
IDENTITY=b'\x01'+bytes(31)


def with_public_key(value,public):
    request=replace(value.candidate.requests[0],public_key=public)
    candidate=replace(value.candidate,requests=(request,),
                      approvals=(replace(value.candidate.approvals[0],request=request),))
    statement=replace(value.statement,candidate_digest=r.inspect_registry(candidate,evaluated_at=AT).candidate_digest)
    return replace(value,candidate=candidate,statement=statement,public_key=public,
                   signature=b'\x01'+bytes(63))


class StrictPublicKeyTests(unittest.TestCase):
    def assert_denied(self,result):
        self.assertIsNot(result.status,Status.PASS)
        for prop in ('analysis_input_allowed','verified_performance_allowed','store_allowed','external_ai_allowed','orders_allowed'):
            self.assertIs(getattr(result,prop),False)

    def identity_attack(self,payload):
        value,_=fixture(raw=payload,normalized=payload)
        attack=with_public_key(value,IDENTITY)
        with patch.object(s,'_verify_ed25519',wraps=s._verify_ed25519) as verify:
            result=s.evaluate_signature(attack)
            self.assertIs(result.status,Status.BLOCK)
            self.assertEqual(result.reasons,('invalid_public_key',))
            self.assertIs(result.crypto_state,s.CryptoState.NOT_CHECKED)
            verify.assert_not_called()
        self.assert_denied(result)

    def test_err018_identity_fixed_signature_message_A(self):
        self.identity_attack(b'synthetic message A')

    def test_err018_identity_fixed_signature_message_B(self):
        self.identity_attack(b'different synthetic message B')

    def test_low_order_and_noncanonical_points_stop_before_verify(self):
        value,_=fixture()
        points=(bytes(32),IDENTITY,TORSION8,
                bytes.fromhex('c7176a703d4dd84fba3c0b760d10670f2a2053fa2c39ccc64ec7fd7792ac037a'),
                *(bytes.fromhex(x+'ff'*30+'7f') for x in ('ec','ed','ee')))
        for point in points:
            for sign in (0,128):
                public=point[:-1]+bytes([point[-1]^sign])
                with self.subTest(public=public.hex()),patch.object(s,'_verify_ed25519') as verify:
                    result=s.evaluate_signature(with_public_key(value,public))
                    self.assertEqual(result.reasons,('invalid_public_key',))
                    self.assertIs(result.status,Status.BLOCK);verify.assert_not_called()
                    self.assert_denied(result)

    def test_official_non_subgroup_and_noncanonical_fixtures(self):
        value,_=fixture()
        for public in (bytes.fromhex('95'+'99'*31),bytes.fromhex('f5'+'ff'*30+'7f'),bytes.fromhex('f6'+'ff'*30+'7f')):
            with patch.object(s,'_verify_ed25519') as verify:
                result=s.evaluate_signature(with_public_key(value,public))
                self.assertEqual(result.reasons,('invalid_public_key',));verify.assert_not_called()

    def test_all_seven_mixed_order_cosets_official_regression(self):
        value,_=fixture()
        for seed in range(8):
            key=Ed25519PrivateKey.from_private_bytes(bytes([seed])*32)
            public=key.public_key().public_bytes(Encoding.Raw,PublicFormat.Raw);mixed=public
            for j in range(1,8):
                mixed=crypto_core_ed25519_add(mixed,TORSION8)
                with self.subTest(seed=seed,torsion=j),patch.object(s,'_verify_ed25519') as verify:
                    result=s.evaluate_signature(with_public_key(value,mixed))
                    self.assertEqual(result.reasons,('invalid_public_key',));verify.assert_not_called()
            self.assertEqual(crypto_core_ed25519_add(mixed,TORSION8),public)

    def test_fixed_order_two_residue_regression_vector(self):
        # j=4 of the official torsion8 construction: [l]P has X=0 but Y!=Z.
        # This catches the old main-subgroup test that checked only X=0.
        value,_=fixture()
        public=bytes.fromhex('b295d84331495bd29d5c572fd590f28c9acdea88e21dbc59c53fb75e74a625d6')
        result=s.evaluate_signature(with_public_key(value,public))
        self.assertEqual(result.reasons,('invalid_public_key',));self.assert_denied(result)

    def test_normal_generated_keys_valid_but_untrusted(self):
        value,_=fixture()
        for seed in range(32):
            key=Ed25519PrivateKey.from_private_bytes(bytes([seed])*32)
            public=key.public_key().public_bytes(Encoding.Raw,PublicFormat.Raw)
            changed=with_public_key(value,public)
            changed=replace(changed,signature=key.sign(s.signing_bytes(changed.statement)))
            result=s.evaluate_signature(changed)
            self.assertIs(result.crypto_state,s.CryptoState.VALID)
            self.assertIs(result.status,Status.UNVERIFIED);self.assert_denied(result)

    def test_strict_check_preserves_two_rfc8032_vectors(self):
        vectors=(
            ('d75a980182b10ab7d54bfed3c964073a0ee172f3daa62325af021a68f707511a',
             'e5564300c360ac729086e2cc806e828a84877f1eb8e5d974d873e065224901555fb8821590a33bacc61e39701cf9b46bd25bf5f0595bbe24655141438e7a100b',b''),
            ('3d4017c3e843895a92b70aa74d1b7ebc9c982ccf2ec4968cc0cd55f12af4660c',
             '92a009a9f0d4cab8720e820b5f642540a2b27b5416503f8fb3762223ebdb69da085ac1e43e15996e458f3613d0f11d8c387b2eaeb4302aeeb00d291612bb0c00',b'\x72'))
        for public,signature,message in vectors:
            public=bytes.fromhex(public)
            s._validate_public_key(public)
            s._verify_ed25519(public,bytes.fromhex(signature),message)

    def test_minimal_feature_unavailable_fails_closed(self):
        value,_=fixture()
        with patch.object(sodium_core,'has_crypto_core_ed25519',False),patch.object(s,'_verify_ed25519') as verify:
            result=s.evaluate_signature(value)
            self.assertEqual(result.reasons,('verification_error',));verify.assert_not_called()
            self.assert_denied(result)

    def test_api_unavailable_exception_fails_closed(self):
        value,_=fixture()
        with patch.object(sodium_core,'crypto_core_ed25519_is_valid_point',side_effect=UnavailableError('not for diagnostics')),patch.object(s,'_verify_ed25519') as verify:
            result=s.evaluate_signature(value)
            self.assertEqual(result.reasons,('verification_error',));verify.assert_not_called()
            self.assertNotIn('not for diagnostics',repr(result));self.assert_denied(result)

    def test_api_runtime_exception_fails_closed(self):
        value,_=fixture()
        with patch.object(sodium_core,'crypto_core_ed25519_is_valid_point',side_effect=RuntimeError('do not disclose')),patch.object(s,'_verify_ed25519') as verify:
            result=s.evaluate_signature(value)
            self.assertEqual(result.reasons,('verification_error',));verify.assert_not_called()
            self.assertNotIn('do not disclose',repr(result));self.assert_denied(result)

    def test_missing_module_has_no_cryptography_fallback(self):
        value,_=fixture()
        with patch.object(s,'_ed25519_core',None),patch.object(s,'_verify_ed25519') as verify:
            result=s.evaluate_signature(value)
            self.assertEqual(result.reasons,('verification_error',));verify.assert_not_called()

    def test_non_bool_predicate_result_fails_closed(self):
        value,_=fixture()
        for invalid in (0,1,None,[],object()):
            with patch.object(sodium_core,'crypto_core_ed25519_is_valid_point',return_value=invalid),patch.object(s,'_verify_ed25519') as verify:
                result=s.evaluate_signature(value)
                self.assertEqual(result.reasons,('verification_error',));verify.assert_not_called()

    def test_unknown_key_cannot_hide_ineligible_public_key(self):
        value,_=fixture();attack=with_public_key(value,IDENTITY)
        attack=replace(attack,statement=replace(attack.statement,key_id='unknown'))
        self.assertEqual(s.evaluate_signature(attack).reasons,('invalid_public_key',))

    def test_limits_precede_parse_hash_point_and_signature_both_entries(self):
        value,_=fixture();record=s.evaluate_signature(value);bad_inputs=[]
        for owner,field,bad in ((None,'raw',b'x'*65537),(None,'normalized',b'x'*65537),
                               (None,'public_key',b'x'*33),(None,'signature',b'x'*65),
                               ('statement','issuer','x'*257),('context','evaluated_at','x'*257),
                               ('candidate','requests',(object(),)*65)):
            item=copy.deepcopy(value);object.__setattr__(item if owner is None else getattr(item,owner),field,bad);bad_inputs.append(item)
        item=copy.deepcopy(value);object.__setattr__(item.candidate.approvals[0],'signature',b'x'*4097);bad_inputs.append(item)
        # Bounded fixtures exceed the record and aggregate budgets without
        # exceeding any primitive field/count cap; never construct huge inputs.
        item=copy.deepcopy(value);req=item.candidate.requests[0]
        scope=replace(req.scope,codes=tuple(str(i).zfill(2)+'😀'*253 for i in range(60)))
        req=replace(req,scope=scope)
        approval=copy.copy(item.candidate.approvals[0])
        object.__setattr__(approval,'request',req);object.__setattr__(approval,'signature',b'x'*4096)
        self.assertGreater(r._size(approval),65536)
        object.__setattr__(item.candidate,'requests',(req,));object.__setattr__(item.candidate,'approvals',(approval,));bad_inputs.append(item)
        item=copy.deepcopy(value);req=item.candidate.requests[0]
        scope=replace(req.scope,codes=tuple(str(i).zfill(2)+'😀'*253 for i in range(32)))
        requests=tuple(replace(req,request_id='r'+str(i),key_id='k'+str(i),scope=scope) for i in range(64))
        object.__setattr__(item.candidate,'requests',requests);object.__setattr__(item.candidate,'approvals',())
        self.assertGreater(r._size(item.candidate),1048576);bad_inputs.append(item)
        yielded=[]
        def unknown_iterator():
            yielded.append(1)
            yield 'label'
        item=copy.deepcopy(value);object.__setattr__(item.statement,'context',unknown_iterator());bad_inputs.append(item)
        for item in bad_inputs:
            with patch.object(s,'timestamp') as parse,patch.object(r,'timestamp') as rparse, \
                 patch.object(s.hashlib,'sha256') as hashed,patch.object(sodium_core,'crypto_core_ed25519_is_valid_point') as point, \
                 patch.object(s,'_verify_ed25519') as verify:
                self.assertIs(s.evaluate_signature(item).status,Status.BLOCK)
                self.assertIs(s.revalidate_signature(record,value=item).status,Status.BLOCK)
                for call in (parse,rparse,hashed,point,verify):call.assert_not_called()
        self.assertEqual(yielded,[])
        bad=copy.deepcopy(record);object.__setattr__(bad,'context',('x'*257,))
        with patch.object(s,'timestamp') as parse,patch.object(s.hashlib,'sha256') as hashed, \
             patch.object(sodium_core,'crypto_core_ed25519_is_valid_point') as point,patch.object(s,'_verify_ed25519') as verify:
            self.assertIs(s.revalidate_signature(bad,value=value).status,Status.BLOCK)
            for call in (parse,hashed,point,verify):call.assert_not_called()

    def test_binding_time_and_issuer_rejections_remain_before_signature(self):
        value,_=fixture()
        changes=(dict(issuer='other'),dict(issued_at='2026-01-07T18:00:00+09:00'),
                 dict(issued_at=END),dict(key_id='unknown'))
        for change in changes:
            item=replace(value,statement=replace(value.statement,**change))
            with patch.object(s,'_verify_ed25519') as verify:
                result=s.evaluate_signature(item);verify.assert_not_called()
                if 'key_id' in change:
                    self.assertIs(result.status,Status.UNVERIFIED);self.assertIn('key_unresolved',result.reasons)
                else:self.assertIs(result.status,Status.BLOCK)
                self.assert_denied(result)

    def test_forged_valid_result_for_identity_reverified_not_trusted(self):
        value,_=fixture();record=s.evaluate_signature(value);attack=with_public_key(value,IDENTITY)
        forged=replace(record,input_digest=s._input_digest(attack))
        with patch.object(s,'_verify_ed25519') as verify:
            result=s.revalidate_signature(forged,value=attack)
            self.assertIs(result.status,Status.BLOCK);verify.assert_not_called();self.assert_denied(result)

    def test_point_validation_uses_detached_captured_public_key(self):
        value,_=fixture();saved=copy.deepcopy(value)
        predicate=sodium_core.crypto_core_ed25519_is_valid_point
        def mutate_source(public):
            object.__setattr__(value,'public_key',IDENTITY)
            object.__setattr__(value.candidate.requests[0],'public_key',IDENTITY)
            return predicate(public)
        with patch.object(sodium_core,'crypto_core_ed25519_is_valid_point',side_effect=mutate_source):
            result=s.evaluate_signature(value)
        self.assertIs(result.crypto_state,s.CryptoState.VALID)
        self.assertEqual(result.input_digest,s.evaluate_signature(saved).input_digest)
        self.assertIs(s.revalidate_signature(result,value=value).status,Status.BLOCK)
        self.assert_denied(result)
