import copy
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
from fantasy_world_generator.hero_guild import calculate, policy_document

class HeroGuildTests(unittest.TestCase):
    def request(self, **changes):
        request=dict(civilization_id='human_heartland',city_block='small_city',population=100,
                     visiting_heroes_requested=0,available_jobs=0,
                     already_housed_resident_heroes=0,available_visitor_beds=0)
        request.update(changes)
        return request

    def policy(self, **changes):
        policy=dict(resident_rate_numerator=1,resident_rate_denominator=10,
                    max_resident_heroes=100,max_visiting_heroes=100,party_size=4,
                    max_active_parties=10,heroes_per_service_worker=5,max_additional_staff=10)
        policy.update(changes)
        return policy

    def test_defaults_have_no_automatic_heroes_and_no_extra_worker_beds(self):
        from fantasy_world_generator.capabilities import require_capabilities
        require_capabilities({'capability_version':1,'requires':{'hero_guild_planning':1}})
        for population in (0,1,1000000):
            result=calculate(self.request(population=population))
            self.assertEqual(result['heroes'],dict(resident=0,visiting=0,present=0,unserved_visitors=0))
            self.assertEqual(result['accommodation']['additional_permanent_beds'],0)
            self.assertEqual(result['service']['existing_workers_already_counted'],2)
            self.assertEqual(result['service']['additional_workers'],0)

    def test_independent_demographic_activity_service_and_bed_example(self):
        result=calculate(self.request(population=105,visiting_heroes_requested=7,
                         available_jobs=3,already_housed_resident_heroes=4,available_visitor_beds=2),self.policy())
        self.assertEqual(result['heroes'],dict(resident=10,visiting=7,present=17,unserved_visitors=0))
        self.assertEqual(result['activity'],dict(active_parties=3,active_heroes=12,inactive_heroes=5))
        self.assertEqual(result['service'],dict(existing_workers_already_counted=2,additional_workers=2,total_workers=4,unserved_heroes=0))
        self.assertEqual(result['accommodation'],dict(resident_hero_beds_needed=6,new_staff_beds=2,additional_permanent_beds=8,temporary_beds_required=7,temporary_bed_shortfall=5))

    def test_small_city_and_sole_capital_use_same_population_rates(self):
        small=calculate(self.request(population=9),self.policy())
        capital=calculate(self.request(population=9,city_block='capital_city'),self.policy())
        self.assertEqual(small['heroes'],capital['heroes'])
        self.assertEqual(capital['heroes']['resident'],0)
        self.assertEqual(capital['activity']['active_parties'],0)

    def test_caps_report_unserved_demand_and_partial_parties(self):
        result=calculate(self.request(population=100,visiting_heroes_requested=9,available_jobs=100),
                         self.policy(max_resident_heroes=3,max_visiting_heroes=6,max_active_parties=1,
                                     heroes_per_service_worker=2,max_additional_staff=1))
        self.assertEqual(result['heroes'],dict(resident=3,visiting=6,present=9,unserved_visitors=3))
        self.assertEqual(result['activity'],dict(active_parties=1,active_heroes=4,inactive_heroes=5))
        self.assertEqual(result['service']['unserved_heroes'],3)
        self.assertEqual(result['accommodation']['additional_permanent_beds'],4)
        self.assertEqual(result['accommodation']['temporary_beds_required'],6)
        large=calculate(self.request(population=999999999),self.policy(
            resident_rate_numerator=999999998,resident_rate_denominator=999999999,
            max_resident_heroes=1000000000))
        self.assertEqual(large['heroes']['resident'],999999998)

    def test_inputs_and_policies_are_strict_and_caller_owned(self):
        request=self.request();policy=self.policy(); original=copy.deepcopy((request,policy))
        self.assertEqual(calculate(request,policy),calculate(request,policy))
        self.assertEqual((request,policy),original)
        document=policy_document();document['revision']=999
        self.assertEqual(policy_document()['revision'],1)
        for bad in (True,1.0,'1',-1,1000000001):
            with self.assertRaises(ValueError): calculate(self.request(population=bad))
        for change in (dict(civilization_id='unknown'),dict(city_block='village'),dict(extra=0),dict(already_housed_resident_heroes=1)):
            with self.assertRaises(ValueError): calculate(self.request(**change))
        for change in (dict(party_size=0),dict(resident_rate_denominator=0),dict(resident_rate_numerator=11),dict(max_additional_staff=True),dict(extra=0)):
            with self.assertRaises(ValueError): calculate(request,self.policy(**change))
        for change in (dict(schema_version=2),dict(schema_version=True),dict(revision=0),dict(policies={})):
            document=policy_document();document.update(change)
            with tempfile.TemporaryDirectory() as directory:
                (Path(directory)/'hero_guild_policies.json').write_text(json.dumps(document))
                with patch('fantasy_world_generator.hero_guild.files',return_value=Path(directory)):
                    with self.assertRaises(ValueError): policy_document()

    def test_every_civilization_policy_resolves_core_hall_without_registry_changes(self):
        from icarus_sim.civilization_registry import load_registry
        registry=load_registry(); before=copy.deepcopy(registry)
        self.assertEqual(set(policy_document()['policies']),set(registry['entities']))
        for entity in registry['entities']:
            for block in ('small_city','medium_city','capital_city'):
                result=calculate(self.request(civilization_id=entity,city_block=block))
                self.assertEqual(result['service']['existing_workers_already_counted'],2)
        self.assertEqual(load_registry(),before)
