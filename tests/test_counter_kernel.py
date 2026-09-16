import copy
from dataclasses import FrozenInstanceError, replace
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

from fantasy_world_generator.counter_kernel import initialize, evaluate, commit, dump_snapshot, load_snapshot, dump_candidate, load_candidate
from fantasy_world_generator.kernel_contract import KernelError, MAX_SAFE
from fantasy_world_generator.kernel_numeric import canonical_bytes, canonical_loads

ROOT=Path(__file__).resolve().parents[1]


class CounterKernelTests(unittest.TestCase):
    def setUp(self):
        self.fixture=json.loads((ROOT/'Fixtures/counter-kernel-v1.json').read_text())
        self.state=copy.deepcopy(self.fixture['initial'])

    def command(self, state=None, events=None, target=10, budget=64):
        state=self.state if state is None else state
        return dict(schema='mathlab.counter-command',schema_version=1,world_id=state['world_id'],
                    authority_epoch=state['authority_epoch'],expected_revision=state['revision'],
                    target_time_ms=target,budget=budget,events=[] if events is None else copy.deepcopy(events))

    def assertCode(self, code, function, *args):
        with self.assertRaises(KernelError) as error: function(*args)
        self.assertEqual(error.exception.code,code)

    def test_hand_authored_checkpoint_and_completion(self):
        self.assertEqual(initialize('world:demo'),self.state)
        command=copy.deepcopy(self.fixture['first_command'])
        candidate=evaluate(self.state,command)
        self.assertEqual(candidate.work_used,1)
        self.assertEqual(canonical_loads(candidate.next_state),self.fixture['checkpoint'])
        self.assertEqual(self.state,self.fixture['initial'])
        self.assertEqual(command,self.fixture['first_command'])
        with self.assertRaises(FrozenInstanceError): candidate.work_used=2
        checkpoint=commit(self.state,candidate)
        done=commit(checkpoint,evaluate(checkpoint,self.fixture['resume_command']))
        self.assertEqual(done,self.fixture['complete'])
        self.assertEqual(canonical_loads(candidate.effects),self.fixture['checkpoint']['receipts'])

    def test_failed_commit_retry_and_duplicate_commit_are_idempotent(self):
        request=self.fixture['first_command']
        first=evaluate(self.state,request)
        self.assertEqual(load_candidate(dump_candidate(first)),first)
        self.assertEqual(first,evaluate(self.state,request))
        next_state=commit(self.state,first)
        self.assertEqual(commit(next_state,first),next_state)
        tampered=replace(first,next_state=canonical_bytes(dict(next_state,counter=999)))
        self.assertCode('INVALID_CANDIDATE',commit,self.state,tampered)
        self.assertEqual(self.state,self.fixture['initial'])

    def test_reordered_and_repeated_inputs_have_identical_candidates(self):
        events=self.fixture['events']
        a=evaluate(self.state,self.command(events=events))
        b=evaluate(self.state,self.command(events=list(reversed(events))))
        c=evaluate(self.state,self.command(events=events+[events[0]]))
        self.assertEqual(a,b)
        self.assertEqual(a,c)

    def test_completed_event_retry_returns_noop_even_with_old_revision(self):
        request=self.command(events=self.fixture['events'])
        done=commit(self.state,evaluate(self.state,request))
        retry=evaluate(done,request)
        self.assertEqual(retry.work_used,0)
        self.assertEqual(canonical_loads(retry.effects),[])
        self.assertEqual(commit(done,retry),done)
        self.assertCode('STALE_REVISION',evaluate,done,dict(request,expected_revision=done['revision']+1))
        advanced=commit(done,evaluate(done,self.command(done,target=20)))
        self.assertEqual(commit(advanced,evaluate(advanced,request)),advanced)

    def test_conflicting_ids_reject_in_batch_receipts_and_pending(self):
        event=self.fixture['events'][0]
        changed=dict(event,delta=99)
        self.assertCode('CONFLICTING_EVENT',evaluate,self.state,self.command(events=[event,changed]))
        checkpoint=copy.deepcopy(self.fixture['checkpoint'])
        for changed in (dict(event,delta=99),dict(self.fixture['events'][1],actor_id='actor:other')):
            self.assertCode('CONFLICTING_EVENT',evaluate,checkpoint,self.command(checkpoint,[changed]))

    def test_revision_epoch_and_current_snapshot_are_fenced(self):
        request=self.command(events=self.fixture['events'])
        self.assertCode('STALE_REVISION',evaluate,self.state,dict(request,expected_revision=1))
        self.assertCode('AUTHORITY_MISMATCH',evaluate,self.state,dict(request,authority_epoch=1))
        self.assertCode('UNKNOWN_ID',evaluate,self.state,dict(request,world_id='world:other',events=[]))
        first=evaluate(self.state,request)
        other=commit(self.state,evaluate(self.state,self.command(target=1)))
        self.assertCode('STALE_REVISION',commit,other,first)

    def test_pending_interval_cannot_change_or_accept_late_insertions(self):
        checkpoint=copy.deepcopy(self.fixture['checkpoint'])
        self.assertEqual(checkpoint['time_ms'],0)
        self.assertCode('INTERVAL_CONFLICT',evaluate,checkpoint,self.command(checkpoint,target=20))
        new=dict(self.fixture['events'][0],event_id='event:new',time_ms=1)
        self.assertCode('INTERVAL_CONFLICT',evaluate,checkpoint,self.command(checkpoint,[new]))
        second=commit(checkpoint,evaluate(checkpoint,self.command(checkpoint,budget=1)))
        self.assertEqual((second['time_ms'],second['counter']),(0,8))
        third=commit(second,evaluate(second,self.command(second,budget=1)))
        self.assertEqual((third['time_ms'],third['counter']),(10,10))
        self.assertIsNone(third['pending'])

    def test_budget_partitions_preserve_effects_not_commit_count(self):
        states=[]
        for budget in (1,2,3):
            state=commit(self.state,evaluate(self.state,self.command(events=self.fixture['events'],budget=budget)))
            while state['pending'] is not None:
                state=commit(state,evaluate(state,self.command(state,budget=budget)))
            states.append(state)
        self.assertEqual([s['revision'] for s in states],[3,2,1])
        for state in states:
            self.assertEqual(state['receipts'],self.fixture['complete']['receipts'])
            self.assertEqual((state['counter'],state['time_ms']),(10,10))

    def test_full_interval_is_validated_before_partial_work(self):
        a=dict(self.fixture['events'][0],delta=MAX_SAFE)
        b=dict(self.fixture['events'][1],delta=1)
        self.assertCode('NUMERIC_OVERFLOW',evaluate,self.state,self.command(events=[a,b],budget=1))
        for time in (0,11):
            bad=dict(b,time_ms=time)
            self.assertCode('INTERVAL_CONFLICT',evaluate,self.state,self.command(events=[a,bad],budget=1))
        self.assertEqual(self.state,self.fixture['initial'])

    def test_receipts_are_never_evicted_at_capacity(self):
        state=self.state
        for batch in range(4):
            events=[dict(self.fixture['events'][0],event_id=f'event:e{batch*64+i:03d}',time_ms=batch+1,delta=1) for i in range(64)]
            state=commit(state,evaluate(state,self.command(state,events,target=batch+1)))
        self.assertEqual((state['counter'],len(state['receipts'])),(256,256))
        new=dict(self.fixture['events'][0],event_id='event:overflow',time_ms=5)
        self.assertCode('STATE_CAPACITY',evaluate,state,self.command(state,[new],target=5))
        duplicate=state['receipts'][0]['event']
        self.assertEqual(commit(state,evaluate(state,self.command(state,[duplicate],target=4))),state)

    def test_serialized_checkpoint_resumes_in_fresh_process(self):
        checkpoint=self.fixture['checkpoint']
        self.assertEqual(load_snapshot(dump_snapshot(checkpoint)),checkpoint)
        code='from fantasy_world_generator.counter_kernel import *; from fantasy_world_generator.kernel_numeric import canonical_loads; import sys; x=canonical_loads(sys.stdin.buffer.read()); sys.stdout.buffer.write(dump_snapshot(commit(x["state"],evaluate(x["state"],x["command"]))))'
        with tempfile.TemporaryDirectory() as directory:
            env=dict(os.environ,PYTHONPATH=str(ROOT/'Sim'))
            output=subprocess.check_output([sys.executable,'-c',code],cwd=directory,env=env,input=canonical_bytes({'state':checkpoint,'command':self.fixture['resume_command']}))
        self.assertEqual(load_snapshot(output),self.fixture['complete'])

    def test_corrupt_snapshots_and_unknown_versions_reject(self):
        for field,value in (('counter',99),('time_ms',20),('schema_version',2),('revision',True)):
            state=copy.deepcopy(self.fixture['checkpoint']); state[field]=value
            with self.subTest(field=field),self.assertRaises(KernelError): load_snapshot(canonical_bytes(state))
        state=copy.deepcopy(self.fixture['checkpoint']);state['pending']['events'].reverse()
        with self.assertRaises(KernelError): load_snapshot(canonical_bytes(state))
        state=copy.deepcopy(self.fixture['complete']);state['receipts'].append(state['receipts'][0])
        with self.assertRaises(KernelError): dump_snapshot(state)
