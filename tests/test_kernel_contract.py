import copy
import json
from pathlib import Path
import unittest

from fantasy_world_generator.kernel_contract import KernelError, validate_event, validate_command

ROOT=Path(__file__).resolve().parents[1]


class KernelContractTests(unittest.TestCase):
    def test_independent_valid_and_failure_fixtures(self):
        cases=json.loads((ROOT/'Fixtures/kernel-contract-v1.json').read_text())
        for event in cases['events']:
            self.assertEqual(validate_event(event, 'world:demo'), event)
        for command in cases['commands']:
            self.assertEqual(validate_command(command), command)
        for case in cases['invalid']:
            function=validate_command if case['kind']=='command' else lambda value: validate_event(value, 'world:demo')
            with self.subTest(case=case), self.assertRaises(KernelError) as failure:
                function(case['value'])
            self.assertEqual(failure.exception.code, case['code'])
            doc=failure.exception.document()
            self.assertEqual(doc['schema'], 'mathlab.failure')
            self.assertEqual(doc['schema_version'], 1)

    def test_types_ids_and_budget_fail_explicitly(self):
        source=json.loads((ROOT/'Fixtures/kernel-contract-v1.json').read_text())
        event=source['events'][0]
        for field in ('time_ms','delta','schema_version'):
            for value in (True, 1., '1', None):
                bad=dict(event, **{field:value})
                with self.assertRaises(KernelError): validate_event(bad, 'world:demo')
        for key in ('event_id','actor_id'):
            for value in ('', 'DISPLAY NAME', '../escape', 'event:UPPER', 'event:'+'a'*65):
                with self.assertRaises(KernelError): validate_event(dict(event, **{key:value}), 'world:demo')
        for budget in (0,65,True,1.,'1'):
            command=copy.deepcopy(source['commands'][0]); command['budget']=budget
            with self.assertRaises(KernelError) as failure: validate_command(command)
            self.assertEqual(failure.exception.code,'WORK_BUDGET')
        for events,code in ((None,'INVALID_INPUT'),([event]*65,'STATE_CAPACITY')):
            command=copy.deepcopy(source['commands'][0]);command['events']=events
            with self.assertRaises(KernelError) as failure: validate_command(command)
            self.assertEqual(failure.exception.code,code)
