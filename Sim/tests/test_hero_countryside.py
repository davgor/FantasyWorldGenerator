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
        # Keyed on the terrain node, not the ordinal site id: `hamlet-0` stands on node 150 and
        # `fortress-0` on node 13, and only the node survives an age advance. See SiteAnchorTests.
        reeve = by_uid(block, 'hero-reeve-hamlet-node-150')
        self.assertEqual((reeve['role'], reeve['well'], reeve['home']['name'], reeve['presence']), ('reeve', 'hamlets', 'Alder City', {'site_kind': 'hamlet', 'uid': 'hamlet-node-150', 'situation': 'reeve'}))
        self.assertTrue({'role:reeve', 'hamlet:farming', 'hamlet:starving', 'hamlet:threatened', 'seat:none'} <= set(reeve['selectable']), reeve['selectable'])
        self.assertEqual(reeve['claim'], {'verb': 'protect', 'target_uid': 'hamlet-node-150', 'target_name': 'the farmstead below Alder'})
        self.assertEqual(reeve['deeds'], [{'event_kind': 'hamlet', 'event_id': 'hamlet-node-150', 'age': 2, 'role': 'keeper'}])
        self.assertIn('ashen wyrm', reeve['log'][0]['text'].lower())
        self.assertIn('granary is short', reeve['situation'])
        quarry = by_uid(block, 'hero-reeve-hamlet-node-1')
        self.assertTrue({'hamlet:resource'} <= set(quarry['selectable']))
        self.assertNotIn('hamlet:starving', quarry['selectable'])
        self.assertNotIn('hamlet:threatened', quarry['selectable'], 'Dunlin is far from the wyrm on the grid')
        # The harbour stands on node 12 and the orphan hamlet on node 5; neither precipitates.
        self.assertFalse([p for p in block['people'] if p['uid'] in ('hero-reeve-hamlet-node-12', 'hero-reeve-hamlet-node-5')], 'harbours are ports; orphan hamlets are skipped')
        castellan = by_uid(block, 'hero-castellan-fortress-node-13')
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
        self.assertGreater(rolls['hero-reeve-hamlet-node-150']['chance'], rolls['hero-reeve-hamlet-node-1']['chance'], 'a starving, threatened hamlet is likelier to have a named reeve')
        self.assertGreater(rolls['hero-castellan-fortress-node-13']['chance'], 0.35, 'war pressure and defence raise the castellan')
        self.assertLessEqual(max(r['chance'] for r in rolls.values()), .95)

    def test_story_web_weaves_the_countryside_onto_its_own_spokes(self):
        import story_web
        world = countryside_world()
        world['heroes'] = hero_generator.generate(world, cast_fixture.certain())
        block = story_web.generate(world)
        webs = {w['uid']: w for w in block['webs']}
        reeve_spokes = [s['trope_id'] for s in webs['hero-reeve-hamlet-node-150']['spokes']]
        self.assertIn(webs['hero-reeve-hamlet-node-150']['offered'], ('the_famine', 'the_hunt'), 'a starving hamlet hunted by a wyrm')
        self.assertTrue({'the_famine', 'the_hunt'} <= set(reeve_spokes), reeve_spokes)
        self.assertEqual(webs['hero-reeve-hamlet-node-1']['offered'], 'the_founding', 'a fed, unthreatened quarry camp can grow')
        self.assertIn(webs['hero-castellan-fortress-node-13']['offered'], ('the_siege', 'the_wardens_line', 'the_vow'))
        self.assertIn('the_skim', [s['trope_id'] for s in webs['hero-harbourmaster-coastal-0-0']['spokes']])
        keeper_uid = next(u for u in webs if 'keeper' in u)
        self.assertIn(webs[keeper_uid]['offered'], ('the_vow', 'the_blight', 'crusade'))
        cult_uid = next(u for u in webs if u.startswith('hero-heresiarch-cult'))
        self.assertIn('the_schism', [s['trope_id'] for s in webs[cult_uid]['spokes']])


class SiteAnchorTests(unittest.TestCase):
    """A reeve and a castellan are anchored on the terrain node, in every field that carries it.

    `humans.hamlets[].id` and `humans.fortresses[].id` are ordinals -- the position in a list
    `terrain_humans` re-sorts by defence score at every age boundary -- so a person built on one
    is renamed by an advance that did not touch their ground. `Sim/tests/test_site_id_stability.py`
    pins the consequence across an advance; these pin the shape on one world, for both roles, and
    against the key space `npc_roster` already writes.
    """

    ANCHORED_FIELDS = ('uid', 'presence.uid', 'claim.target_uid', 'deeds[0].event_id')

    def carried(self, person):
        return {'uid': person['uid'], 'presence.uid': person['presence']['uid'],
                'claim.target_uid': person['claim']['target_uid'],
                'deeds[0].event_id': person['deeds'][0]['event_id']}

    def test_no_countryside_field_carries_the_ordinal_site_id(self):
        """All four together. Repairing `uid` alone leaves three ways to join the wrong row."""
        world = countryside_world()
        block = hero_generator.generate(world, cast_fixture.certain())
        ordinals = {str(site['id']) for key in ('hamlets', 'fortresses')
                    for site in world['humans'][key]}
        offenders = {}
        for person in block['people']:
            if person['well'] not in ('hamlets', 'fortresses'):
                continue
            for field, value in self.carried(person).items():
                tail = str(value).rsplit('hero-' + person['role'] + '-', 1)[-1]
                if tail in ordinals:
                    offenders[(person['role'], field)] = value
        self.assertEqual(offenders, {},
                         'these fields still carry an ordinal that renumbers every age: '
                         f'{sorted(offenders.items())}')

    def test_both_roles_key_on_the_node_with_the_anchor_spelled_out(self):
        world = countryside_world()
        block = hero_generator.generate(world, cast_fixture.certain())
        hamlet = next(h for h in world['humans']['hamlets'] if h['id'] == 'hamlet-0')
        fortress = world['humans']['fortresses'][0]
        reeve = by_uid(block, f"hero-reeve-hamlet-node-{hamlet['node']}")
        castellan = by_uid(block, f"hero-castellan-fortress-node-{fortress['node']}")
        self.assertEqual(self.carried(reeve),
                         {'uid': f"hero-reeve-hamlet-node-{hamlet['node']}",
                          'presence.uid': f"hamlet-node-{hamlet['node']}",
                          'claim.target_uid': f"hamlet-node-{hamlet['node']}",
                          'deeds[0].event_id': f"hamlet-node-{hamlet['node']}"})
        self.assertEqual(self.carried(castellan),
                         {'uid': f"hero-castellan-fortress-node-{fortress['node']}",
                          'presence.uid': f"fortress-node-{fortress['node']}",
                          'claim.target_uid': f"fortress-node-{fortress['node']}",
                          'deeds[0].event_id': f"fortress-node-{fortress['node']}"})

    def test_the_cast_anchor_is_the_key_npc_roster_already_writes(self):
        """The two key spaces join, which is the point of the change and not a coincidence.

        `npc_roster/sites.py` keys non-city sites `fortress-node-<n>` and documents the cast as
        the package that does not. This calls the roster's own row builder rather than restating
        its format, so a change to either spelling fails here instead of drifting apart quietly.
        """
        from npc_roster import sites as roster_sites
        world = countryside_world()
        world['hamlet_plans'] = {'hamlets': [
            {'hamlet_id': h['id'], 'node': h['node'], 'x': h['x'], 'z': h['z'],
             'core_id': h['core_id'], 'role': h.get('role'), 'status': 'ok', 'plots': []}
            for h in world['humans']['hamlets']]}
        world['castle_plans'] = {'castles': [
            {'fortress_id': f['id'], 'x': f['x'], 'z': f['z'], 'status': 'ok', 'plots': []}
            for f in world['humans']['fortresses']]}
        rows, _notes = roster_sites.collect(world)
        roster_uids = {row['uid'] for row in rows}
        block = hero_generator.generate(world, cast_fixture.certain())
        presences = {p['presence']['uid'] for p in block['people']
                     if p['well'] in ('hamlets', 'fortresses')}
        self.assertTrue(presences, 'no countryside person to check')
        self.assertEqual(presences - roster_uids, set(),
                         'a cast presence that names no roster site is the join the two packages '
                         'have never been able to make')


if __name__ == '__main__':
    unittest.main()
