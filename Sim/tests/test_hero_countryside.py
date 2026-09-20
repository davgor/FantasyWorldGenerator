"""The countryside, ports and shrines wells: reeves, castellans, harbourmasters, keepers and cult heresiarchs.

Built on the hand-built cast world with hamlets, a fortress, a port and two religion sites
added, so the wells are exercised without generating a world.
"""
import json
import pathlib
import sys
import unittest

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[2] / 'tests'))

import hero_generator
from hero_generator.wells import countryside, ports, shrines

import test_hero_generator as cast_fixture

ROOT = pathlib.Path(__file__).resolve().parents[2]


def countryside_world(**kwargs):
    world = cast_fixture.world(**kwargs)
    alder, dunlin = world['settlements']['sites'][0], world['settlements']['sites'][1]
    world['spacing_m'] = 1000.
    world['humans']['hamlets'] = [
        # hamlet-0 sits one node from the ashen wyrm's nest (node 151) and belongs to starving Alder; hamlet-1 is far and fed
        {'id': 'hamlet-0', 'kind': 'hamlet', 'node': 150, 'x': 150 % 17, 'z': 150 // 17, 'core_id': alder['id'], 'role': 'farming', 'delivered_food': 40.},
        {'id': 'hamlet-1', 'kind': 'hamlet', 'node': 1, 'x': 1, 'z': 0, 'core_id': dunlin['id'], 'role': 'resource'},
        {'id': 'coastal-0-0', 'kind': 'hamlet', 'node': 12, 'x': 12, 'z': 0, 'core_id': alder['id'], 'role': 'harbor + fishing'},
        {'id': 'hamlet-9', 'kind': 'hamlet', 'node': 5, 'x': 5, 'z': 0, 'core_id': 999, 'role': 'farming'},
    ]
    world['humans']['fortresses'] = [{'id': 'fortress-0', 'kind': 'fortress', 'node': 13, 'x': 13, 'z': 0, 'core_id': alder['id'], 'defence_score': 3.}]
    world['humans']['cores'] = [{'site_id': alder['id'], 'food_supply': 10., 'food_demand': 30., 'food_deficit': 20., 'hamlet_ids': ['hamlet-0', 'coastal-0-0'], 'fortress_ids': ['fortress-0']},
                                {'site_id': dunlin['id'], 'food_supply': 30., 'food_demand': 20., 'food_deficit': 0., 'hamlet_ids': ['hamlet-1'], 'fortress_ids': []}]
    world['threat_assessments'] = {'cities': [{'city_uid': alder['uid'], 'war_pressure': .15, 'regional_threat': .2}]}
    world['fisheries'] = {'ports': [{'id': 'coastal-0-0', 'kind': 'hamlet', 'role': 'harbor + fishing', 'node': 12, 'sea_node': 29, 'x': 12, 'z': 0,
                                     'core_id': alder['id'], 'trade_terminal': True}]}
    world['transport'] = {'routes': [{'mode': 'sea', 'from': 'coastal-0-0', 'to': 'coastal-9-9'}, {'mode': 'air', 'from': 'x', 'to': 'y'}]}
    ember_ruin = next(r for r in world['ruins'] if r['name'] == 'Ember City')
    cedar_ruin = next(r for r in world['ruins'] if r['name'] == 'Cedar City')
    world['religion'] = {'gods': [{'id': 'god_red_field', 'name': 'The Red Field'}, {'id': 'god_umbral', 'name': 'The Umbral'}],
                         'sites': [{'id': 'shrine-' + ember_ruin['id'], 'kind': 'shrine', 'god_id': 'god_red_field', 'ruin_id': ember_ruin['id'], 'node': ember_ruin['node']},
                                   {'id': 'cult-' + cedar_ruin['id'], 'kind': 'cult', 'god_id': 'god_umbral', 'ruin_id': cedar_ruin['id'], 'node': cedar_ruin['node'], 'born_under_surge': True},
                                   {'id': 'theophany-1-god_umbral', 'kind': 'theophany', 'god_id': 'god_umbral', 'node': 3}]}
    return world


def by_uid(block, uid):
    return next(p for p in block['people'] if p['uid'] == uid)


class CountrysideWellTests(unittest.TestCase):
    def test_every_site_precipitates_the_right_person_with_the_right_facts(self):
        world = countryside_world()
        block = hero_generator.generate(world, cast_fixture.certain())
        self.assertEqual(block['status'], 'ok')
        reeve = by_uid(block, 'hero-reeve-hamlet-0')
        self.assertEqual((reeve['role'], reeve['well'], reeve['home']['name'], reeve['presence']), ('reeve', 'hamlets', 'Alder City', {'site_kind': 'hamlet', 'uid': 'hamlet-0', 'situation': 'reeve'}))
        self.assertTrue({'role:reeve', 'hamlet:farming', 'hamlet:starving', 'hamlet:threatened', 'seat:none'} <= set(reeve['selectable']), reeve['selectable'])
        self.assertEqual(reeve['claim'], {'verb': 'protect', 'target_uid': 'hamlet-0', 'target_name': 'the farmstead below Alder'})
        self.assertEqual(reeve['deeds'], [{'event_kind': 'hamlet', 'event_id': 'hamlet-0', 'age': 2, 'role': 'keeper'}])
        self.assertIn('ashen wyrm', reeve['log'][0]['text'].lower())
        self.assertIn('granary is short', reeve['situation'])
        quarry = by_uid(block, 'hero-reeve-hamlet-1')
        self.assertTrue({'hamlet:resource'} <= set(quarry['selectable']))
        self.assertNotIn('hamlet:starving', quarry['selectable'])
        self.assertNotIn('hamlet:threatened', quarry['selectable'], 'Dunlin is far from the wyrm on the grid')
        self.assertFalse([p for p in block['people'] if p['uid'] in ('hero-reeve-coastal-0-0', 'hero-reeve-hamlet-9')], 'harbours are ports; orphan hamlets are skipped')
        castellan = by_uid(block, 'hero-castellan-fortress-0')
        self.assertTrue({'role:castellan', 'order:member', 'warden:post', 'fortress:pressed'} <= set(castellan['selectable']))
        self.assertEqual(castellan['claim']['verb'], 'hold')
        self.assertEqual(castellan['presence']['site_kind'], 'fortress')
        master = by_uid(block, 'hero-harbourmaster-coastal-0-0')
        self.assertTrue({'role:harbourmaster', 'seat:trade', 'routes:2', 'port:terminal'} <= set(master['selectable']))
        self.assertEqual((master['claim']['verb'], master['presence']['situation']), ('exploit', 'quay'))
        keeper = next(p for p in block['people'] if p['role'] == 'keeper')
        self.assertEqual((keeper['well'], keeper['presence']['site_kind'], keeper['presence']['situation']), ('shrines', 'shrine', 'altar'))
        self.assertEqual(keeper['home']['name'], 'Dunlin City', 'the nearest surviving dwarven city shelters the keeper of Ember\'s shrine')
        self.assertIn('Red Field', keeper['claim']['target_name'])
        cult = next(p for p in block['people'] if p['role'] == 'heresiarch' and p['well'] == 'shrines')
        self.assertTrue({'shrine:cult', 'school:dark'} <= set(cult['selectable']))
        self.assertEqual(cult['claim']['verb'], 'convert')
        self.assertIsNone(cult['home'], 'no elven city survives to shelter the cult of Cedar')
        self.assertFalse([p for p in block['people'] if 'theophany' in p['uid']])
        kinds = {r['kind'] for r in block['rolls']}
        self.assertTrue({'reeve', 'castellan', 'harbourmaster', 'keeper', 'cult'} <= kinds)
        for person in block['people']:
            self.assertTrue(person['situation'] and person['archetype'] and person['display_name'].strip(), person['uid'])
            if person['well'] in ('hamlets', 'fortresses', 'ports', 'shrines'):
                self.assertTrue(person['log'], person['uid'])
                self.assertEqual(person['log'][0]['event_kind'], person['deeds'][0]['event_kind'])
        kinds_by_giver = {}
        for hook in block['quest_hooks']:
            kinds_by_giver.setdefault(hook['giver_uid'], set()).add(hook['actual_effect']['kind'])
        self.assertEqual(kinds_by_giver[reeve['uid']], {'hamlet', 'nest'}, 'the reeve asks for the season and for the wyrm')
        self.assertEqual(kinds_by_giver[castellan['uid']], {'fortress'})
        self.assertEqual(kinds_by_giver[master['uid']], {'port'})
        self.assertEqual(kinds_by_giver[keeper['uid']], {'shrine'})
        self.assertEqual(kinds_by_giver[cult['uid']], {'city'}, 'a cult heresiarch carries the word to the nearest city')

    def test_block_validates_against_the_schema_and_replays(self):
        from schema_subset import validate
        world = countryside_world()
        first = hero_generator.generate(world, cast_fixture.certain())
        validate(first, json.loads((ROOT / 'Contracts/schemas/hero-generator.schema.json').read_text(encoding='utf-8')))
        second = hero_generator.generate(countryside_world(), cast_fixture.certain())
        self.assertEqual(json.dumps(first, sort_keys=True), json.dumps(second, sort_keys=True))
        json.dumps(first, allow_nan=False)

    def test_wells_are_silent_on_a_world_without_their_sites(self):
        world = cast_fixture.world()
        for well in (countryside, ports, shrines):
            people, rolls = well.candidates(world, {}, 1, cast_fixture.certain()['wells'])
            self.assertEqual((people, rolls), ([], []))
        block = hero_generator.generate(world, cast_fixture.certain())
        self.assertFalse([p for p in block['people'] if p['well'] in ('hamlets', 'fortresses', 'ports', 'shrines')])

    def test_precipitation_reads_the_site(self):
        policies = hero_generator.policy.load_all() if hasattr(hero_generator, 'policy') else None
        from hero_generator.policy import load_all
        world = countryside_world()
        block = hero_generator.generate(world, load_all())
        rolls = {r['candidate_uid']: r for r in block['rolls']}
        self.assertGreater(rolls['hero-reeve-hamlet-0']['chance'], rolls['hero-reeve-hamlet-1']['chance'], 'a starving, threatened hamlet is likelier to have a named reeve')
        self.assertGreater(rolls['hero-castellan-fortress-0']['chance'], 0.35, 'war pressure and defence raise the castellan')
        self.assertLessEqual(max(r['chance'] for r in rolls.values()), .95)

    def test_story_web_weaves_the_countryside_onto_its_own_spokes(self):
        import story_web
        world = countryside_world()
        world['heroes'] = hero_generator.generate(world, cast_fixture.certain())
        block = story_web.generate(world)
        webs = {w['uid']: w for w in block['webs']}
        reeve_spokes = [s['trope_id'] for s in webs['hero-reeve-hamlet-0']['spokes']]
        self.assertIn(webs['hero-reeve-hamlet-0']['offered'], ('the_famine', 'the_hunt'), 'a starving hamlet hunted by a wyrm')
        self.assertTrue({'the_famine', 'the_hunt'} <= set(reeve_spokes), reeve_spokes)
        self.assertEqual(webs['hero-reeve-hamlet-1']['offered'], 'the_founding', 'a fed, unthreatened quarry camp can grow')
        self.assertIn(webs['hero-castellan-fortress-0']['offered'], ('the_siege', 'the_wardens_line', 'the_vow'))
        self.assertIn('the_skim', [s['trope_id'] for s in webs['hero-harbourmaster-coastal-0-0']['spokes']])
        keeper_uid = next(u for u in webs if 'keeper' in u)
        self.assertIn(webs[keeper_uid]['offered'], ('the_vow', 'the_blight', 'crusade'))
        cult_uid = next(u for u in webs if u.startswith('hero-heresiarch-cult'))
        self.assertIn('the_schism', [s['trope_id'] for s in webs[cult_uid]['spokes']])


if __name__ == '__main__':
    unittest.main()
