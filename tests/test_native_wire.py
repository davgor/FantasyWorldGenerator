"""Native wire/numeric conformance against independent fixtures and Python oracle."""
import copy
import hashlib
import json
import os
from pathlib import Path
import random
import shlex
import shutil
import subprocess
import sys
import tempfile
import unittest

from fantasy_world_generator.kernel_numeric import canonical_bytes, canonical_loads, random_word
from fantasy_world_generator.counter_kernel import evaluate, dump_candidate, commit, load_candidate
from fantasy_world_generator.kernel_contract import KernelError

ROOT=Path(__file__).resolve().parents[1]

class NativeWireTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        compiler=shutil.which('clang++') or shutil.which('g++')
        if not compiler: raise unittest.SkipTest('native wire conformance requires a C++17 compiler')
        cls.directory=tempfile.TemporaryDirectory(prefix='fantasy-world-generator-wire-')
        cls.addClassCleanup(cls.directory.cleanup)
        cls.binary=Path(cls.directory.name)/'wire'
        flags=shlex.split(os.environ.get('FANTASY_WORLD_GENERATOR_CXXFLAGS',''))
        if sys.platform=='darwin':
            sdk=subprocess.check_output(['xcrun','--show-sdk-path'],text=True).strip()
            headers=Path(sdk)/'usr/include/c++/v1'
            if headers.is_dir(): flags+=['-isystem',str(headers)]
        sources=['counter.cpp','json.cpp','numeric.cpp','wire.cpp','tests/wire_driver.cpp']
        built=subprocess.run([compiler,'-std=c++17','-Wall','-Wextra','-Werror','-pedantic',*flags,'-I',str(ROOT/'Core'),
                              *(str(ROOT/'Core'/s) for s in sources),'-o',str(cls.binary)],capture_output=True,text=True,timeout=60)
        if built.returncode: raise AssertionError(built.stdout+built.stderr)
        cls.fixture=json.loads((ROOT/'Fixtures/counter-kernel-v1.json').read_text())

    def run_native(self,operation,value,raw=False):
        payload=value if raw else canonical_bytes(value)
        result=subprocess.run([str(self.binary),operation],input=payload,capture_output=True,timeout=10)
        if result.returncode:
            self.assertEqual(result.returncode,2,result.stderr)
            failure=json.loads(result.stdout)
            self.assertEqual(failure['schema'],'fantasy-world-generator.failure')
            raise KernelError(failure['code'])
        return result.stdout

    def test_independent_numeric_and_stream_vectors(self):
        f=json.loads((ROOT/'Fixtures/kernel-numeric-v1.json').read_text())
        for case in f['canonical']:
            self.assertEqual(self.run_native('canonical',case['value']),case['ascii'].encode())
            self.assertEqual(self.run_native('digest',case['value']).decode(),case['sha256'])
        for case in f['streams']:
            request={key:case[key] for key in ('seed','stream','index')}
            self.assertEqual(self.run_native('stream',request).decode(),case['word'])
        for word,expected in [('0000000000000000',0.),('8000000000000000',.5),('ffffffffffffffff',1.-2**-53)]:
            self.assertEqual(float(self.run_native('unit',word)),expected)
        for size in (0,1,55,56,63,64,65,127,128,4096,1000000):
            raw=bytes(i%251 for i in range(size))
            self.assertEqual(self.run_native('sha256',raw,raw=True).decode(),hashlib.sha256(raw).hexdigest())

    def test_json_unicode_numbers_order_and_limits(self):
        values=[{'\U0010ffff':False,'\ue000':1,'\U00010000':2},'"\\\b\f\n\r\t\x00\x1f/é😀',[-(2**53-1),2**53-1], 'é'*2048]
        for value in values:
            raw=json.dumps(value,ensure_ascii=False,indent=2).encode()
            self.assertEqual(self.run_native('canonical',raw,raw=True),canonical_bytes(value))
        self.assertEqual(self.run_native('canonical',b' \n-0\t',raw=True),b'0')
        malformed=[b'',b'01',b'+1',b'1.',b'1e0',b'NaN',b'Infinity',b'9007199254740992',b'-9007199254740992',
                   b'{"a":1,"\\u0061":2}',b'[1,]',b'{"a":1,}',b'{}x',b'"\x00"',b'"\\ud800"',b'"\\udc00"',
                   b'"\\ud800x"',b'"\\ud800\\u0041"',b'"\xc0\x80"',b'"\xed\xa0\x80"',b'"\xf4\x90\x80\x80"',
                   b'"\x80"',b'"\xe2\x82"',b'\xef\xbb\xbf{}',b'"'+b'a'*4097+b'"',b'['*33+b'0'+b']'*33,
                   b'['+b'0,'*16384+b'0]',b' '*1048577]
        for raw in malformed:
            with self.subTest(raw=raw[:30]):
                with self.assertRaises(KernelError) as error: self.run_native('canonical',raw,raw=True)
                self.assertEqual(error.exception.code,'INVALID_INPUT')
        for raw in [b'['*32+b'0'+b']'*32, b'['+b'0,'*16382+b'0]']:
            self.assertEqual(self.run_native('canonical',raw,raw=True),canonical_bytes(canonical_loads(raw)))

    def test_json_differential_corpus(self):
        rng=random.Random(3103)
        def value(depth=0):
            choice=rng.randrange(4 if depth>3 else 6)
            if choice==0:return rng.randint(-(2**53-1),2**53-1)
            if choice==1:return rng.choice([True,False,None])
            if choice==2:return ''.join(chr(rng.choice([0,9,34,92,127,233,0xe000,0x10000,0x10ffff])) for _ in range(rng.randrange(15)))
            if choice==3:return ''
            if choice==4:return [value(depth+1) for _ in range(rng.randrange(5))]
            return {str(i)+'é':value(depth+1) for i in range(rng.randrange(5))}
        for _ in range(80):
            sample=value();raw=json.dumps(sample,ensure_ascii=rng.choice([True,False]),indent=1).encode()
            self.assertEqual(self.run_native('canonical',raw,raw=True),canonical_bytes(sample))
        seeds=[b'{"a":[true,null,-1,"\\u00e9"]}',b'"utf8:\xf0\x9f\x98\x80"',b'9007199254740991',b'[[[]]]']
        for _ in range(200):
            raw=bytearray(rng.choice(seeds))
            for _ in range(rng.randrange(1,4)):
                if raw:raw[rng.randrange(len(raw))]=rng.randrange(256)
            raw=bytes(raw)
            try: expected=canonical_bytes(canonical_loads(raw))
            except KernelError:
                with self.assertRaises(KernelError) as error:self.run_native('canonical',raw,raw=True)
                self.assertEqual(error.exception.code,'INVALID_INPUT')
            else:self.assertEqual(self.run_native('canonical',raw,raw=True),expected)

    def test_stream_versions_and_invalid_requests(self):
        request=dict(seed='000000000000002a',stream='ecology',index=0,version=1)
        self.assertEqual(self.run_native('stream',request).decode(),random_word(request['seed'],request['stream'],0))
        for changes,code in [(dict(version=2),'UNSUPPORTED_VERSION'),(dict(version=True),'INVALID_INPUT'),
                             (dict(version=-1),'INVALID_INPUT'),(dict(seed='FFFFFFFFFFFFFFFF'),'INVALID_INPUT'),
                             (dict(stream='Terrain'),'INVALID_INPUT'),(dict(stream='x'*65),'INVALID_INPUT'),
                             (dict(index=-1),'INVALID_INPUT'),(dict(index=True),'INVALID_INPUT')]:
            with self.assertRaises(KernelError) as error:self.run_native('stream',dict(request,**changes))
            self.assertEqual(error.exception.code,code)

    def test_wire_candidate_roundtrip_and_fresh_process_resume(self):
        f=self.fixture
        for key in ('initial','checkpoint','complete'):
            self.assertEqual(self.run_native('snapshot',f[key]),canonical_bytes(f[key]))
        request={'state':f['initial'],'command':f['first_command']}
        first=self.run_native('evaluate',request)
        self.assertEqual(first,dump_candidate(evaluate(f['initial'],f['first_command'])))
        checkpoint=json.loads(self.run_native('commit',{'state':f['initial'],'candidate':json.loads(first)}))
        self.assertEqual(checkpoint,f['checkpoint'])
        self.assertEqual(self.run_native('commit',{'state':checkpoint,'candidate':json.loads(first)}),canonical_bytes(checkpoint))
        resumed=self.run_native('evaluate',{'state':checkpoint,'command':f['resume_command']})
        self.assertEqual(commit(checkpoint,load_candidate(resumed)),f['complete'])
        self.assertEqual(self.run_native('candidate',json.loads(resumed)),resumed)

    def test_invalid_envelopes_match_reference_codes(self):
        f=self.fixture
        for key,value in [('schema_version',True),('schema_version',2),('rules_version',-1),('counter',99),('extra',0),('world_id','world:bad/')]:
            state=dict(f['checkpoint'],**{key:value})
            from fantasy_world_generator.counter_kernel import validate_snapshot
            with self.assertRaises(KernelError) as reference: validate_snapshot(state)
            with self.assertRaises(KernelError) as native: self.run_native('snapshot',state)
            self.assertEqual(native.exception.code,reference.exception.code)
        cases=json.loads((ROOT/'Fixtures/kernel-contract-v1.json').read_text())
        for case in cases['invalid']:
            if case['kind']=='command':
                op='evaluate';request={'state':f['initial'],'command':case['value']}
            else: op='event';request=case['value']
            with self.assertRaises(KernelError) as error:self.run_native(op,json.dumps(request).encode(),raw=True)
            self.assertEqual(error.exception.code,case['code'])
        candidate=json.loads(dump_candidate(evaluate(f['initial'],f['first_command'])))
        for key,value in [('work_used',False),('work_used',65),('effects',[]),('next_state',dict(f['checkpoint'],counter=999))]:
            bad=dict(candidate,**{key:value})
            with self.assertRaises(KernelError) as error:self.run_native('candidate',bad)
            self.assertEqual(error.exception.code,'INVALID_CANDIDATE')

    def test_multiple_intervals_and_budget_partitions_match_python(self):
        for budget in (1,3,64):
            state=copy.deepcopy(self.fixture['initial'])
            for interval in range(1,5):
                command=dict(self.fixture['first_command'],expected_revision=state['revision'],target_time_ms=interval*10,budget=budget,
                             events=[dict(self.fixture['events'][0],event_id=f'event:e{interval}-{i}',time_ms=(interval-1)*10+i+1,delta=i+1) for i in reversed(range(7))])
                while True:
                    native=self.run_native('evaluate',{'state':state,'command':command})
                    self.assertEqual(native,dump_candidate(evaluate(state,command)))
                    state=json.loads(self.run_native('commit',{'state':state,'candidate':json.loads(native)}))
                    if state['pending'] is None:break
                    command=dict(command,events=[],expected_revision=state['revision'])
            self.assertEqual(state['counter'],112)
        state=copy.deepcopy(self.fixture['initial'])
        for batch in range(4):
            command=dict(self.fixture['first_command'],expected_revision=state['revision'],target_time_ms=batch+1,budget=64,
                         events=[dict(self.fixture['events'][0],event_id=f'event:{batch}-{i:02}',time_ms=batch+1,delta=1) for i in range(64)])
            candidate=self.run_native('evaluate',{'state':state,'command':command})
            self.assertEqual(candidate,dump_candidate(evaluate(state,command)))
            state=json.loads(self.run_native('commit',{'state':state,'candidate':json.loads(candidate)}))
        self.assertEqual(state['counter'],256)
        self.assertEqual(self.run_native('snapshot',state),canonical_bytes(state))
