"""The hero generator precipitates a cast from a finished world and changes nothing.

Hand-built worlds keep this fast and independent of terrain_history; the generated-world
conformance check lives with the world schema tests, which already build one world.
"""
import copy
import json
import math
import os
import unittest
from unittest.mock import patch

import hero_generator
from hero_generator import alignment as alignment_rules
from hero_generator import archetypes as archetype_rules
from hero_generator import fame as fame_rules
from hero_generator.persona import compose
from hero_generator.policy import lint_archetypes, load, load_all


def certain():
    """Packaged policies with every precipitation chance at one, so well tests see every candidate."""
    policies = load_all()
    for rule in policies['wells']['precipitation'].values():
        rule['base'] = 1.
    policies['wells']['cap'] = 1.
    return policies


def direction(lon_deg, lat_deg):
    lon, lat = math.radians(lon_deg), math.radians(lat_deg)
    return [math.cos(lat) * math.cos(lon), math.sin(lat), math.cos(lat) * math.sin(lon)]


def city(uid, site_id, name, profile, race, city_class, lon, lat, node):
    return {'uid': uid, 'id': site_id, 'name': name, 'population_profile': profile, 'civilization_id': profile,
            'parent_race_id': race, 'city_class': city_class, 'direction': direction(lon, lat), 'node': node,
            'x': node % 17, 'z': node // 17, 'suitability': .7, 'population_estimate': 3000, 'founded_age': 0,
            'source_culture': f'{profile}-seed', 'war_history': []}


def war(war_id, age, kind, victor, defeated):
    record = {'id': war_id, 'age': age, 'kind': kind, 'participants': [victor['uid'], defeated['uid']],
              'victor_uid': victor['uid'], 'defeated_uid': defeated['uid'],
              'victor_civilization_id': victor['civilization_id'], 'defeated_civilization_id': defeated['civilization_id'],
              'victor_parent_race_id': victor['parent_race_id'], 'defeated_parent_race_id': defeated['parent_race_id'],
              'pressure': 1., 'chance': .9, 'roll': .3, 'reason': 'contested ground'}
    for side, other in ((victor, defeated), (defeated, victor)):
        side['war_history'].append({'war_id': war_id, 'age': age, 'kind': kind,
                                    'outcome': 'victor' if side is victor else 'defeated', 'opponent_uid': other['uid'],
                                    'opponent_civilization_id': other['civilization_id'],
                                    'opponent_parent_race_id': other['parent_race_id']})
    return record


def ruin(city_record, age, cause, evidence=None):
    keys = ('uid', 'name', 'node', 'x', 'z', 'direction', 'population_profile', 'civilization_id', 'city_class',
            'source_culture', 'founded_age', 'war_history')
    record = {k: copy.deepcopy(city_record[k]) for k in keys}
    record.update(id='ruin-' + city_record['uid'], kind='ruins', destroyed_age=age, asset_id='marker.city_ruins',
                  cause=cause, reason='test', evidence=evidence or {}, new_node_school=None)
    return record


NEST = {'id': 'nest-ashen-wyrm-151', 'species_id': 'ashen-wyrm', 'name': 'Ashen wyrm', 'node': 151, 'x': 151 % 17,
        'z': 151 // 17, 'direction': direction(66, 34), 'biome': 3, 'tier': 5, 'family': 'draconic',
        'kind': 'greater lair', 'size': 'huge', 'role': None, 'range_m': 2500., 'layer': 'surface', 'real': False}


def world(seed=42, dragon=True, ember_class='small', nest_tier=5, ages=2, elf_survivor=False, magic=True):
    """Alder beats Bracken (civil), Dunlin beats Cedar (international), a dragon eats Ember."""
    alder = city('surface-city-0-10-human_heartland', 0, 'Alder City', 'human_heartland', 'human', 'capital', 0, 10, 10)
    alder['founding_capital'] = True
    bracken = city('surface-city-0-40-human_heartland', 1, 'Bracken City', 'human_heartland', 'human', 'small', 12, 12, 40)
    cedar = city('surface-city-0-90-elf', 2, 'Cedar City', 'elf', 'elf', 'capital', -30, -20, 90)
    dunlin = city('surface-city-0-120-dwarf', 3, 'Dunlin City', 'dwarf', 'dwarf', 'medium', 60, 30, 120)
    ember = city('surface-city-0-150-dwarf', 4, 'Ember City', 'dwarf', 'dwarf', ember_class, 65, 33, 150)
    fern = city('surface-city-0-200-elf', 5, 'Fern City', 'elf', 'elf', 'small', -35, -25, 200)
    w1 = war('war-1-0', 1, 'civil', alder, bracken)
    w2 = war('war-1-1', 1, 'international', dunlin, cedar)
    nest = dict(NEST, tier=nest_tier)
    glen = city('surface-city-0-60-human_heartland', 6, 'Glen City', 'human_heartland', 'human', 'medium', 5, 14, 60)
    ruins = [ruin(bracken, 1, 'war_civil', {'war_id': w1['id']}), ruin(cedar, 1, 'war_international', {'war_id': w2['id']}),
             ruin(glen, 1, 'self_magic')]
    if dragon:
        ruins.append(ruin(ember, 1, 'dragon', {'nest_id': nest['id'], 'distance_m': 900., 'reach_m': 2500.}))
    schools = {'surface-city-0-40-human_heartland': 'radiant', 'surface-city-0-90-elf': 'water', 'surface-city-0-60-human_heartland': 'weave', 'surface-city-0-150-dwarf': 'fire'}
    for r in ruins:
        r['new_node_school'] = schools[r['uid']]
    networks = {s: {'name': s, 'nodes': [{'id': f'{s}-node-0', 'direction': direction(20, 20), 'intensity': 1.}], 'edges': []}
                for s in ('weave', 'umbral', 'infernal', 'radiant', 'fire', 'water', 'earth', 'air')}
    for r in ruins:
        networks[r['new_node_school']]['nodes'].append({'id': r['id'] + '-key', 'direction': r['direction'], 'intensity': 2.5})
    survivors = [alder, dunlin] + ([fern] if elf_survivor else [])
    history = [{'age': 1, 'events': copy.deepcopy(ruins), 'wars': [w1, w2],
                'surviving_city_ids': sorted(s['uid'] for s in survivors), 'new_city_ids': []}]
    for age in range(2, ages + 1):
        history.append({'age': age, 'events': [], 'wars': [], 'surviving_city_ids': history[0]['surviving_city_ids'], 'new_city_ids': []})
    cultures = [{'index': 0, 'id': 'human_heartland-aaaa', 'city_ids': [0], 'population_profile': 'human_heartland', 'civilization_id': 'human_heartland'},
                {'index': 1, 'id': 'dwarf-bbbb', 'city_ids': [3], 'population_profile': 'dwarf', 'civilization_id': 'dwarf'}]
    if elf_survivor:
        cultures.append({'index': 2, 'id': 'elf-cccc', 'city_ids': [5], 'population_profile': 'elf', 'civilization_id': 'elf'})
    return {
        'config': {'seed': seed, 'size': 17}, 'effective_config': {'globe_radius': 31831.},
        'history': {'version': 2, 'ages': history}, 'ruins': ruins,
        'settlements': {'version': 14, 'sites': survivors},
        'civilizations': {'entities': [
            {'id': 'human_heartland', 'name': 'Heartland humans', 'parent_race_id': 'human', 'region_index': 0},
            {'id': 'elf', 'name': 'High Elves', 'parent_race_id': 'elf', 'region_index': 1},
            {'id': 'dwarf', 'name': 'Dwarves', 'parent_race_id': 'dwarf', 'region_index': 2}]},
        'humans': {'version': 8, 'cultures': cultures, 'cores': []},
        'beast_nests': {'version': 1, 'sites': [nest] if dragon else []},
        'magic': {'enabled': True, 'networks': networks, 'colleges': []} if magic else {'enabled': False, 'networks': {}, 'colleges': []},
    }


def by_uid(block, uid):
    return next(p for p in block['people'] + block['dreads'] if p['uid'] == uid)


class RuinsWellTests(unittest.TestCase):
    def test_every_ruin_leaves_an_heir_every_war_a_victor_every_beast_kill_a_dread(self):
        block = hero_generator.generate(world(), certain())
        self.assertEqual(block['status'], 'ok')
        self.assertEqual(block['summary'], {'living': 23, 'legends': 0, 'dreads': 1, 'realms': 2, 'orgs': 5, 'camps': 4, 'hooks': 28, 'candidates': 28, 'precipitated': 28})
        bracken_heir = by_uid(block, 'hero-pretender-surface-city-0-40-human_heartland')
        self.assertEqual(bracken_heir['deeds'][0], {'event_kind': 'ruin', 'event_id': 'ruin-surface-city-0-40-human_heartland', 'age': 1, 'role': 'heir'})
        self.assertEqual(bracken_heir['deeds'][1]['event_id'], 'war-1-0')
        self.assertEqual((bracken_heir['status'], bracken_heir['home']['uid']), ('living', 'surface-city-0-10-human_heartland'))
        self.assertEqual(bracken_heir['claim'], {'verb': 'retake', 'target_uid': 'surface-city-0-40-human_heartland', 'target_name': 'Bracken City'})
        self.assertEqual(bracken_heir['presence'], {'site_kind': 'city', 'uid': 'surface-city-0-10-human_heartland', 'situation': 'court'})
        self.assertEqual(bracken_heir['realm_uid'], 'realm-human_heartland-aaaa')
        elf_heir = by_uid(block, 'hero-pretender-surface-city-0-90-elf')
        self.assertEqual((elf_heir['status'], elf_heir['home'], elf_heir['presence']['situation']), ('living', None, 'leader'))
        warlord = by_uid(block, 'hero-warlord-1-surface-city-0-10-human_heartland')
        self.assertEqual(warlord['deeds'][0]['event_id'], 'war-1-0')
        self.assertEqual(warlord['claim']['verb'], 'hold')
        dread = block['dreads'][0]
        self.assertEqual((dread['uid'], dread['nest_id'], dread['status'], dread['species']), ('dread-nest-ashen-wyrm-151', 'nest-ashen-wyrm-151', 'living', 'Ashen wyrm'))
        self.assertEqual(dread['deeds'][0]['event_id'], 'ruin-surface-city-0-150-dwarf')
        self.assertIn('Ember', dread['display_name'])
        self.assertIn({'a': bracken_heir['uid'], 'b': warlord['uid'], 'kind': 'rival', 'from_event': 'war-1-0'}, block['bonds'])
        self.assertEqual(warlord['rivals'], [bracken_heir['uid']])
        self.assertEqual(block['mantles'], [], 'the elf heir leads a camp, so no claim is vacant')
        # A realm is its seat plus the seat's own realm morpheme: human -mark, dwarven -rik.
        # The English form ships alongside, because a map label and a chronicle line want
        # different things from the same realm.
        self.assertEqual([r['name'] for r in block['realms']], ['Aldermark', 'Dunlinrik'])
        self.assertEqual([r['english_name'] for r in block['realms']],
                         ['Realm of Alder', 'Realm of Dunlin'])
        self.assertEqual(block['realms'][0]['capital_uid'], 'surface-city-0-10-human_heartland')
        for person in block['people']:
            self.assertTrue(person['situation'] and person['persona']['never'] and person['persona']['line'])
            self.assertEqual(bool(person['log']), bool(person['deeds']), 'a log entry per deed, none invented')
            for entry in person['log']:
                self.assertEqual(set(entry), {'age', 'event_kind', 'event_id', 'role', 'text'})
            self.assertEqual(person['faces'][0]['label'], 'public')
            self.assertEqual(person['alignment']['label'], alignment_rules.label(person['alignment']['law'], person['alignment']['good']))
        self.assertEqual(bracken_heir['log'][0]['event_id'], 'ruin-surface-city-0-40-human_heartland')
        self.assertIn('claims Bracken City', bracken_heir['situation'])

    def test_replay_is_byte_identical_and_the_world_is_untouched(self):
        source = world()
        before = json.dumps(source, sort_keys=True)
        first = hero_generator.generate(source, certain())
        self.assertEqual(json.dumps(source, sort_keys=True), before)
        self.assertEqual(json.dumps(first, sort_keys=True), json.dumps(hero_generator.generate(world(), certain()), sort_keys=True))
        self.assertNotEqual(json.dumps(first, sort_keys=True), json.dumps(hero_generator.generate(world(seed=7)), sort_keys=True))
        json.dumps(first, allow_nan=False)

    def test_dead_dread_and_missing_dragon_are_reported_not_invented(self):
        block = hero_generator.generate(world(dragon=False), certain())
        self.assertEqual(block['dreads'], [])
        self.assertEqual(block['summary']['living'], 19)
        gone = world()
        gone['beast_nests']['sites'] = []
        dread = hero_generator.generate(gone, certain())['dreads'][0]
        self.assertEqual((dread['status'], dread['presence'], dread['species']), ('legend', None, 'Ashen wyrm'))

    def test_an_old_ruin_leaves_a_legend_and_a_later_heir_inherits(self):
        block = hero_generator.generate(world(ages=3), certain())
        self.assertEqual({p['status'] for p in block['people'] if p['well'] == 'ruins'}, {'legend'}, 'heirs and victors of Age 1 are legends by Age 3')
        self.assertTrue(all(p['status'] == 'living' for p in block['people'] if p['role'] in ('sovereign', 'council')), 'seats are always held now')
        later = world(ages=3, elf_survivor=True)
        fern = later['settlements']['sites'][-1]
        glen = city('surface-city-0-210-elf', 6, 'Glen City', 'elf', 'elf', 'small', -36, -26, 210)
        later['ruins'].append(ruin(glen, 3, 'weave'))
        later['history']['ages'][2]['events'] = [copy.deepcopy(later['ruins'][-1])]
        block = hero_generator.generate(later, certain())
        heir = by_uid(block, 'hero-pretender-surface-city-0-210-elf')
        self.assertEqual((heir['status'], heir['home']['uid']), ('living', fern['uid']))
        self.assertIn('legend:predecessor', heir['selectable'])
        self.assertEqual(heir['predecessor_uid'], 'hero-pretender-surface-city-0-90-elf')
        without = hero_generator.generate(world(elf_survivor=True), certain())
        self.assertFalse(any('legend:predecessor' in p['selectable'] for p in without['people']))


class PrecipitationTests(unittest.TestCase):
    def test_every_candidate_rolls_once_and_the_ledger_records_the_outcome_either_way(self):
        block = hero_generator.generate(world())
        rolls = block['rolls']
        self.assertEqual([r['kind'] for r in rolls], ['heir'] * 4 + ['warlord'] * 2 + ['dread'] + ['domain_holder', 'domain_holder', 'domain_holder', 'magister', 'domain_holder']
                         + ['sovereign'] * 2 + ['council'] * 8 + ['champion'] * 2 + ['camp'] * 4)
        self.assertEqual(len({r['candidate_uid'] for r in rolls}), 28)
        for roll in rolls:
            self.assertEqual(roll['precipitated'], roll['roll'] < roll['chance'])
            self.assertTrue(0. <= roll['roll'] <= 1. and 0. < roll['chance'] <= .95)
        kept = {r['candidate_uid'] for r in rolls if r['precipitated']}
        self.assertEqual({p['uid'] for p in block['people'] + block['dreads'] + block['camps']}, kept)
        self.assertEqual((block['summary']['candidates'], block['summary']['precipitated']), (28, len(kept)))
        self.assertLess(len(kept), 28, 'the packaged chances must leave some history unclaimed on this fixture')

    def test_chances_read_the_event_weight_and_zero_precipitates_nobody(self):
        rolls = {r['candidate_uid']: r for r in hero_generator.generate(world())['rolls']}
        self.assertLess(rolls['hero-pretender-surface-city-0-150-dwarf']['chance'], rolls['hero-pretender-surface-city-0-90-elf']['chance'],
                        'a capital heir is likelier than a small-town heir')
        self.assertLess(rolls['hero-warlord-1-surface-city-0-10-human_heartland']['chance'], rolls['hero-warlord-1-surface-city-0-120-dwarf']['chance'],
                        'an international victor is likelier than a civil one')
        nobody = load_all()
        for rule in nobody['wells']['precipitation'].values():
            rule['base'] = -10.
        block = hero_generator.generate(world(), nobody)
        self.assertEqual((block['people'], block['dreads'], block['camps'], block['mantles'], block['bonds']), ([], [], [], [], []))
        self.assertEqual(len(block['rolls']), 28)
        self.assertNotEqual([r['roll'] for r in hero_generator.generate(world(seed=7))['rolls']], [r['roll'] for r in block['rolls']])


class MagicWellTests(unittest.TestCase):
    def test_key_points_keep_wardens_and_a_self_destroyed_college_leaves_a_master(self):
        block = hero_generator.generate(world(), certain())
        wardens = [p for p in block['people'] if p['role'] == 'domain_holder']
        self.assertEqual(len(wardens), 4, 'one candidate per ruin key point')
        ember = by_uid(block, 'hero-domain-surface-city-0-150-dwarf')
        self.assertEqual((ember['school'], ember['node_id'], ember['status']), ('fire', 'ruin-surface-city-0-150-dwarf-key', 'living'))
        self.assertEqual(ember['presence'], {'site_kind': 'ruin', 'uid': 'surface-city-0-150-dwarf', 'situation': 'warding'})
        self.assertEqual(ember['deeds'][0]['role'], 'keeper')
        self.assertEqual(ember['claim']['verb'], 'hold')
        self.assertIn('keypoint:ruin_born', ember['selectable'])
        master = by_uid(block, 'hero-magister-surface-city-0-60-human_heartland')
        self.assertEqual((master['role'], master['school'], master['status']), ('magister', 'weave', 'living'))
        self.assertIn('school:dark', master['selectable'])
        self.assertIn('college:destroyed', master['selectable'])
        self.assertEqual(master['claim'], {'verb': 'exploit', 'target_uid': 'ruin-surface-city-0-60-human_heartland-key', 'target_name': 'the weave key point at Glen'})
        self.assertNotIn('{school}', ' '.join(p['display_name'] for p in block['people']))
        without = hero_generator.generate(world(magic=False), certain())
        self.assertFalse([p for p in without['people'] if p['role'] == 'domain_holder'], 'no networks, no key points, no wardens')
        self.assertEqual(by_uid(without, 'hero-magister-surface-city-0-60-human_heartland')['claim']['target_uid'], 'surface-city-0-60-human_heartland')

    def test_wardens_roll_on_intensity_and_masters_on_their_own_chance(self):
        rolls = {r['candidate_uid']: r for r in hero_generator.generate(world())['rolls']}
        self.assertEqual(rolls['hero-domain-surface-city-0-150-dwarf']['chance'], .5)
        self.assertEqual(rolls['hero-magister-surface-city-0-60-human_heartland']['chance'], .75)
        self.assertEqual(rolls['hero-domain-surface-city-0-150-dwarf']['kind'], 'domain_holder')


class SitesTests(unittest.TestCase):
    def test_camps_squat_ruins_relics_rest_in_them_and_the_dispossessed_are_placed(self):
        block = hero_generator.generate(world(), certain())
        self.assertEqual([c['uid'] for c in block['camps']], ['camp-' + r['uid'] for r in world()['ruins']])
        camp = next(c for c in block['camps'] if c['ruin_uid'] == 'surface-city-0-90-elf')
        self.assertEqual((camp['x'], camp['z'], camp['origin'], camp['since_age']), (90 % 17, 90 // 17, 'ruin_squat', 1))
        elf_heir = by_uid(block, 'hero-pretender-surface-city-0-90-elf')
        self.assertEqual((elf_heir['status'], elf_heir['presence']), ('living', {'site_kind': 'camp', 'uid': camp['uid'], 'situation': 'leader'}))
        self.assertEqual(camp['leader_uid'], elf_heir['uid'])
        self.assertIn('role:camp_leader', elf_heir['selectable'])
        self.assertEqual(block['mantles'], [], 'a camp leader is not a legend, so no mantle is open')
        master = by_uid(block, 'hero-magister-surface-city-0-60-human_heartland')
        self.assertEqual(master['presence']['site_kind'], 'camp')
        self.assertIn(master['presence']['situation'], ('captive', 'hidden'))
        self.assertTrue(master['companion']['eligible'])
        self.assertEqual(master['companion']['join_condition'], {'captive': 'rescued', 'hidden': 'found'}[master['presence']['situation']])
        self.assertEqual({r['kind'] for r in block['relics']}, {'banner', 'crown', 'focus', 'reliquary'})
        focus = next(r for r in block['relics'] if r['kind'] == 'focus')
        self.assertEqual((focus['school'], focus['resting_at'], focus['holder_uid']), ('weave', 'surface-city-0-60-human_heartland', None))

    def test_without_a_camp_the_master_is_a_refugee_and_the_heir_a_legend(self):
        policies = certain()
        policies['wells']['precipitation']['camp']['base'] = -10.
        block = hero_generator.generate(world(), policies)
        self.assertEqual(block['camps'], [])
        master = by_uid(block, 'hero-magister-surface-city-0-60-human_heartland')
        self.assertEqual(master['presence']['situation'], 'refugee')
        self.assertEqual(master['companion'], {'eligible': True, 'join_condition': 'hired', 'offered_from_face': 'public'})
        elf_heir = by_uid(block, 'hero-pretender-surface-city-0-90-elf')
        self.assertEqual((elf_heir['status'], elf_heir['presence']), ('legend', None))
        self.assertEqual(len(block['mantles']), 1)


class FacesAndHooksTests(unittest.TestCase):
    def deceiver_policies(self):
        policies = certain()
        keep = {'deceiver', 'exiled_hero', 'conqueror', 'oathbound', 'ancient', 'warden'}
        policies['archetypes']['cards'] = [c for c in policies['archetypes']['cards'] if c['id'] in keep]
        return policies

    def test_a_public_face_states_a_different_purpose_than_the_effect(self):
        block = hero_generator.generate(world(), self.deceiver_policies())
        master = by_uid(block, 'hero-magister-surface-city-0-60-human_heartland')
        self.assertEqual(master['archetype'], 'deceiver')
        self.assertEqual([f['label'] for f in master['faces']], ['public', 'true'])
        public, true = master['faces']
        self.assertGreater(public['alignment']['good'], 0.)
        self.assertEqual(true['alignment'], master['alignment'])
        self.assertIn(public['apparent_role'], ('healer', 'scribe', 'pilgrim', 'midwife', 'herbalist'))
        self.assertEqual(public['claim']['verb'], 'protect')
        self.assertEqual(master['persona'], true['persona'])
        self.assertNotEqual(public['persona']['toward_player'], true['persona']['toward_player'])
        hooks = [h for h in block['quest_hooks'] if h['giver_uid'] == master['uid']]
        self.assertEqual(len(hooks), 2)
        self.assertTrue(all(h['unwitting'] and h['offered_from_face'] == 'public' for h in hooks))
        own, other = hooks
        self.assertEqual(own['actual_effect'], {'kind': 'ley_node', 'node_id': 'ruin-surface-city-0-60-human_heartland-key', 'school': 'weave', 'intensity_delta': .5})
        self.assertEqual(other['actual_effect'], {'kind': 'ley_node', 'node_id': 'infernal-node-0', 'school': 'infernal', 'intensity_delta': -.5})
        self.assertNotIn('weave', own['stated_purpose'])
        self.assertIn('poisoning', other['stated_purpose'])
        self.assertEqual(master['companion']['offered_from_face'], 'public')

    def test_honest_people_ask_for_what_they_mean(self):
        block = hero_generator.generate(world(), certain())
        hooks = {h['hook_id']: h for h in block['quest_hooks']}
        self.assertEqual(block['summary']['hooks'], len(hooks))
        self.assertTrue(all(not h['unwitting'] for h in hooks.values()))
        heir = [h for h in hooks.values() if h['giver_uid'] == 'hero-pretender-surface-city-0-150-dwarf']
        self.assertEqual([h['actual_effect']['kind'] for h in heir], ['ruin', 'relic'])
        self.assertEqual(heir[1]['actual_effect']['uid'], 'relic-surface-city-0-150-dwarf')
        warden = [h for h in hooks.values() if h['giver_uid'] == 'hero-domain-surface-city-0-150-dwarf']
        self.assertEqual([(h['actual_effect']['school'], h['actual_effect']['intensity_delta']) for h in warden], [('fire', .5), ('water', -.5)])
        self.assertIn('Strengthen the fire key point at Ember', warden[0]['stated_purpose'])
        self.assertFalse([h for h in hooks.values() if h['giver_uid'] == 'hero-pretender-surface-city-0-90-elf' and h['actual_effect']['kind'] == 'city'])
        legends = {p['uid'] for p in block['people'] if p['status'] == 'legend'}
        self.assertFalse(legends & {h['giver_uid'] for h in hooks.values()}, 'legends give no quests')

    def test_beast_and_fractured_faces_carry_their_own_alignment(self):
        from hero_generator.faces import build
        policies = load_all()
        overlays = policies['axis_overlays']
        person = {'uid': 'x', 'name': 'X', 'role': 'pretender', 'claim': {'verb': 'retake', 'target_uid': 'r', 'target_name': 'R'}}
        beast = next(c for c in policies['archetypes']['cards'] if c['id'] == 'beast')
        calm, loosed = build(beast, person, alignment_rules.record(.2, .4), overlays, policies['names'], 1)
        self.assertEqual((calm['label'], loosed['label'], loosed['alignment']['law'], loosed['alignment']['good']), ('calm', 'unleashed', -1., -.5))
        fractured = next(c for c in policies['archetypes']['cards'] if c['id'] == 'fractured_heart')
        first, second = build(fractured, person, alignment_rules.record(.8, .8), overlays, policies['names'], 1)
        self.assertLess(second['alignment']['good'], 0.)
        self.assertNotEqual(first['persona'], second['persona'])


class QuestContractTests(unittest.TestCase):
    """The quest contract: a hook names an anchor, a verb and a difficulty 1-5.

    The generator never prices a reward. It says who is asking, what the player does, where
    the player stands to do it, and how hard the thing is on the creature-tier rubric; the
    consuming game turns that number into treasure.
    """

    def canonical_verbs(self):
        """The one vocabulary, read from the roster's own policy rather than restated here.

        `hero_generator` may not import a sibling package, so the list is declared twice and
        this test is what keeps the two copies one list.
        """
        import pathlib
        path = pathlib.Path(__file__).resolve().parents[1] / 'npc_roster' / 'policies' / 'posts.json'
        return list(json.loads(path.read_text(encoding='utf-8'))['verbs'])

    def fixture_world(self):
        import pathlib
        path = pathlib.Path(__file__).resolve().parents[2] / 'Fixtures' / 'hero-generator-v1.json'
        return json.loads(path.read_text(encoding='utf-8'))['world']

    def reference_blocks(self):
        return (('hand-built', hero_generator.generate(world(), certain())),
                ('pinned fixture', hero_generator.generate(self.fixture_world())))

    def test_the_hook_vocabulary_is_the_roster_vocabulary(self):
        from hero_generator import hooks as hook_rules
        self.assertEqual(list(hook_rules.VERBS), self.canonical_verbs())

    def test_every_hook_names_a_verb_and_carries_a_difficulty(self):
        from hero_generator import hooks as hook_rules
        for label, block in self.reference_blocks():
            hooks = block['quest_hooks']
            self.assertTrue(hooks, label)
            for hook in hooks:
                self.assertIn(hook['verb'], hook_rules.VERBS, f'{label}: {hook["hook_id"]}')
                self.assertIsInstance(hook['difficulty'], int, f'{label}: {hook["hook_id"]}')
                self.assertTrue(1 <= hook['difficulty'] <= 5, f'{label}: {hook["hook_id"]}')
            # A rubric that answers the same number everywhere is not a rubric. This is the
            # guard against the equation quietly collapsing to a constant.
            self.assertGreater(len({h['difficulty'] for h in hooks}), 1, label)

    def test_difficulty_is_the_creature_tier_of_the_thing_you_face(self):
        """A lair's own tier is the whole answer for a slay hook: derived, never invented."""
        for tier in (1, 2, 3, 4, 5):
            block = hero_generator.generate(world(nest_tier=tier), certain())
            slay = [h for h in block['quest_hooks'] if h['actual_effect']['kind'] == 'nest']
            self.assertTrue(slay, tier)
            self.assertEqual({h['difficulty'] for h in slay}, {tier})
            self.assertEqual({h['verb'] for h in slay}, {'slay'})

    def test_every_hook_stands_somewhere_or_says_why_it_does_not(self):
        from hero_generator import hooks as hook_rules
        for label, block in self.reference_blocks():
            for hook in block['quest_hooks']:
                where = f'{label}: {hook["hook_id"]}'
                if hook['target_node'] is None:
                    self.assertIn(hook['unsited_reason'], hook_rules.UNSITED_REASONS, where)
                else:
                    self.assertIsInstance(hook['target_node'], int, where)
                    self.assertIsNone(hook['unsited_reason'], where)
                # The nest hooks are the ones whose `target` was null, because a nest effect
                # names `nest_id` and the old field only read `uid` or `node_id`.
                self.assertIsNotNone(hook['target'], where)

    def test_a_ley_key_point_stands_at_its_ruin_and_a_bare_node_stands_nowhere(self):
        """The one place a ley objective has a position, and the one place it has none."""
        block = hero_generator.generate(world(), certain())
        ruins_by_id = {r['id']: r for r in world()['ruins']}
        ley = [h for h in block['quest_hooks'] if h['actual_effect']['kind'] == 'ley_node']
        self.assertTrue(ley)
        keyed = [h for h in ley if h['actual_effect']['node_id'].endswith('-key')]
        bare = [h for h in ley if not h['actual_effect']['node_id'].endswith('-key')]
        self.assertTrue(keyed and bare)
        for hook in keyed:
            ruin = ruins_by_id[hook['actual_effect']['node_id'][:-4]]
            self.assertEqual(hook['target_node'], ruin['node'], hook['hook_id'])
            self.assertIsNone(hook['unsited_reason'])
        for hook in bare:
            self.assertIsNone(hook['target_node'], hook['hook_id'])
            self.assertEqual(hook['unsited_reason'], 'ley_node_has_no_site')
        self.assertEqual({h['verb'] for h in ley if h['actual_effect']['intensity_delta'] > 0}, {'tend'})
        self.assertEqual({h['verb'] for h in ley if h['actual_effect']['intensity_delta'] < 0}, {'cleanse'})


class CitiesAndGuildsTests(unittest.TestCase):
    def test_realms_seat_sovereigns_cities_seat_councils_and_orders_hold_the_line(self):
        block = hero_generator.generate(world(), certain())
        sovereigns = {p['realm_uid']: p for p in block['people'] if p['role'] == 'sovereign'}
        self.assertEqual(set(sovereigns), {'realm-human_heartland-aaaa', 'realm-dwarf-bbbb'})
        alder = sovereigns['realm-human_heartland-aaaa']
        self.assertEqual((alder['home']['uid'], alder['presence']['situation'], alder['claim']['verb']), ('surface-city-0-10-human_heartland', 'throne', 'hold'))
        self.assertEqual(next(r for r in block['realms'] if r['uid'] == alder['realm_uid'])['sovereign_uid'], alder['uid'])
        self.assertEqual(alder['deeds'][0]['event_id'], 'war-1-0', 'the capital fought the civil war')
        self.assertIn('dynasty-surface-city-0-10-human_heartland', [o['uid'] for o in block['orgs'] if o['kind'] == 'dynasty'])
        seats = sorted((p['home']['name'], p['seat']) for p in block['people'] if p['role'] == 'council')
        self.assertEqual(seats, [('Alder City', 'chaplain'), ('Alder City', 'commander'), ('Alder City', 'mage'), ('Alder City', 'magistrate'), ('Alder City', 'market_steward'),
                                 ('Dunlin City', 'commander'), ('Dunlin City', 'magistrate'), ('Dunlin City', 'market_steward')])
        steward = by_uid(block, 'hero-council-surface-city-0-10-human_heartland-market_steward')
        self.assertIn('seat:trade', steward['selectable'])
        self.assertEqual(steward['claim']['verb'], 'exploit')
        council = next(o for o in block['orgs'] if o['uid'] == 'council-surface-city-0-10-human_heartland')
        self.assertEqual(len(council['members']), 5)
        self.assertIn(alder['uid'], steward['allies'])
        champion = by_uid(block, 'hero-champion-surface-city-0-120-dwarf')
        self.assertEqual((champion['nest_id'], champion['claim']['verb'], champion['presence']['situation']), ('nest-ashen-wyrm-151', 'kill', 'guildhall'))
        self.assertEqual(champion['deeds'][0], {'event_kind': 'nest', 'event_id': 'nest-ashen-wyrm-151', 'age': 2, 'role': 'credited', 'tier': 5})
        self.assertIn('deed:credited_not_actual', champion['selectable'], 'the warlord of Dunlin actually won its war')
        self.assertIn('hero-warlord-1-surface-city-0-120-dwarf', champion['rivals'])
        order = next(o for o in block['orgs'] if o['uid'] == 'order-surface-city-0-120-dwarf')
        self.assertEqual((order['charter']['against'], order['members']), ('draconic', [champion['uid']]))
        fallen = by_uid(block, 'hero-champion-surface-city-0-150-dwarf')
        self.assertTrue({'defence:failed', 'dread:failed_against', 'order:remnant'} <= set(fallen['selectable']))
        self.assertEqual(fallen['presence']['site_kind'], 'camp')
        self.assertIn('remnant-surface-city-0-150-dwarf', [o['uid'] for o in block['orgs']])
        self.assertTrue(all(len(h) for h in [q for q in block['quest_hooks'] if q['actual_effect']['kind'] == 'nest']))
        self.assertNotIn('{', ' '.join(p['display_name'] for p in block['people']))

    def test_diaspora_leaders_and_a_second_founding_redeem_an_heir(self):
        source = world(elf_survivor=True)
        fern = source['settlements']['sites'][-1]
        fern.update(diaspora='religious_schism', diaspora_reason='religious_schism', source_civilization_id='human_heartland', founded_age=2)
        block = hero_generator.generate(source, certain())
        prophet = by_uid(block, 'hero-heresiarch-surface-city-0-200-elf')
        self.assertEqual((prophet['role'], prophet['claim']['verb'], prophet['claim']['target_uid']), ('heresiarch', 'convert', 'surface-city-0-10-human_heartland'))
        self.assertEqual(prophet['deeds'][0]['event_kind'], 'founding')
        self.assertEqual(prophet['archetype'], 'zealot')
        heir = by_uid(block, 'hero-pretender-surface-city-0-90-elf')
        self.assertTrue({'villain:prior_age', 'stake:regained'} <= set(heir['selectable']), 'the elves founded again after the heir lost Cedar')
        source['settlements']['sites'][-1].update(diaspora_reason='exile', source_civilization_id='elf')
        exile = by_uid(hero_generator.generate(source, certain()), 'hero-exile-surface-city-0-200-elf')
        self.assertEqual((exile['role'], exile['claim']['verb']), ('exile', 'protect'))

    def test_seated_people_are_finished_first_so_a_tyrant_makes_rebels(self):
        policies = certain()
        keep = {'tyrant', 'rebel', 'exiled_hero', 'oathbound', 'warden', 'conqueror', 'ancient', 'hermit_sage', 'trickster'}
        policies['archetypes']['cards'] = [c for c in policies['archetypes']['cards'] if c['id'] in keep]
        for c in policies['archetypes']['cards']:
            if c['id'] == 'tyrant':
                c['requires'] = [['role:warlord'], ['role:sovereign']]
        block = hero_generator.generate(world(), policies)
        seated = [p for p in block['people'] if p['role'] in ('sovereign', 'warlord')]
        self.assertTrue(seated and all(p['archetype'] == 'tyrant' for p in seated))
        heir = by_uid(block, 'hero-pretender-surface-city-0-90-elf')
        self.assertNotIn('realm:tyrant', heir['selectable'], 'the elf camp leader belongs to no tyrant realm')
        human_heir = by_uid(block, 'hero-pretender-surface-city-0-40-human_heartland')
        self.assertIn('realm:tyrant', human_heir['selectable'])
        self.assertIn('seat:none', human_heir['selectable'])
        self.assertTrue(any(p['archetype'] == 'rebel' for p in block['people']), 'somebody under a tyrant rebels')

    def test_cross_cutting_features_read_ground_fame_and_lineage(self):
        source = world()
        source['layers'] = {'ley_umbral': [[0.] * 17 for _ in range(17)]}
        source['layers']['ley_umbral'][10 // 17][10 % 17] = .9
        block = hero_generator.generate(source, certain())
        self.assertIn('ley:tainted_home', by_uid(block, 'hero-sovereign-surface-city-0-10-human_heartland')['selectable'])
        self.assertNotIn('ley:tainted_home', by_uid(block, 'hero-sovereign-surface-city-0-120-dwarf')['selectable'])
        mentors = [p for p in block['people'] if 'mentor:successor' in p['selectable']]
        self.assertTrue(mentors)
        self.assertTrue(all(p['tier'] in ('renowned', 'legendary') and p['allies'] for p in mentors))
        self.assertTrue(any(e['kind'] == 'mentor' for e in block['bonds']))


class EpithetCaseTests(unittest.TestCase):
    def test_a_school_inside_a_title_is_capitalised_and_elsewhere_is_not(self):
        """`Keeper of the fire Stone` read as a typo for as long as that template existed."""
        from hero_generator.naming import _fill, _placeholders

        context = {'school': 'fire', 'seat': 'Court Mage'}
        self.assertEqual(_fill('Keeper of the {School} Stone', context), 'Keeper of the Fire Stone')
        self.assertEqual(_fill('the {school} focus', context), 'the fire focus')
        self.assertEqual(_fill('{Seat}', context), 'Court Mage', 'only the first letter is raised')

    def test_a_capitalised_token_still_resolves_to_its_context_key(self):
        """Template choice filters on placeholders having values; a token that resolved to no
        key would not render wrong, it would silently never be chosen."""
        from hero_generator.naming import _placeholders

        self.assertEqual(_placeholders('Keeper of the {School} Stone'), ['school'])
        self.assertEqual(_placeholders('{lost} and {Home}'), ['lost', 'home'])

    def test_the_shipped_epithets_name_a_school_only_in_the_capitalised_form(self):
        from hero_generator.policy import load

        for role, epithets in load('names')['epithets'].items():
            for epithet in (epithets if isinstance(epithets, list) else []):
                self.assertNotIn('{school}', epithet,
                                 f'{role}: a school inside an epithet belongs in the capitalised form')


class FixtureTests(unittest.TestCase):
    def test_pinned_fixture_world_yields_the_pinned_cast(self):
        """A policy edit must change this on purpose: bump the fixture, never silently drift."""
        import pathlib
        path = pathlib.Path(__file__).resolve().parents[2] / 'Fixtures' / 'hero-generator-v1.json'
        fixture = json.loads(path.read_text(encoding='utf-8'))
        block = hero_generator.generate(fixture['world'])
        self.assertEqual(block['policy_revision'], fixture['policy_revision'])
        self.assertEqual(block['summary'], fixture['expected']['summary'])
        keys = ('uid', 'role', 'status', 'archetype', 'tier', 'fame', 'display_name', 'realm_uid', 'predecessor_uid')
        for expected, actual in zip(fixture['expected']['people'] + fixture['expected']['dreads'], block['people'] + block['dreads']):
            self.assertEqual({k: actual.get(k) for k in keys}, {k: expected[k] for k in keys})
            self.assertEqual(actual['alignment']['label'], expected['alignment'])
            self.assertEqual((actual.get('home') or {}).get('uid'), expected['home'])
        self.assertEqual(block['rolls'], fixture['expected']['rolls'])
        self.assertEqual(block['bonds'], fixture['expected']['bonds'])
        self.assertEqual(block['mantles'], fixture['expected']['mantles'])
        self.assertEqual([(r['uid'], r['name'], r['capital_uid']) for r in block['realms']],
                         [(r['uid'], r['name'], r['capital_uid']) for r in fixture['expected']['realms']])


class FameAndAlignmentTests(unittest.TestCase):
    def test_fame_moves_with_the_class_of_the_fallen_city_and_the_tier_of_the_beast(self):
        small = by_uid(hero_generator.generate(world(ember_class='small'), certain()), 'hero-pretender-surface-city-0-150-dwarf')['fame']
        capital = by_uid(hero_generator.generate(world(ember_class='capital'), certain()), 'hero-pretender-surface-city-0-150-dwarf')['fame']
        self.assertGreater(capital, small)
        weak = hero_generator.generate(world(nest_tier=2), certain())['dreads'][0]['fame']
        strong = hero_generator.generate(world(nest_tier=5), certain())['dreads'][0]['fame']
        self.assertGreater(strong, weak)
        self.assertEqual([fame_rules.tier(v) for v in (0., 7.9, 8., 23.9, 24.)], ['notable', 'notable', 'renowned', 'renowned', 'legendary'])

    def test_deeds_decide_a_sign_that_jitter_never_flips(self):
        policy = load('alignment')
        person = {'uid': 'x', 'civilization_id': 'gnome', 'deeds': [{'event_kind': 'war', 'kind': 'civil', 'role': 'credited'}]}
        for seed in range(40):
            record = alignment_rules.derive_person(person, policy, seed)
            self.assertGreater(record['law'], 0.)
            self.assertLess(record['good'], 0.)
        self.assertEqual(alignment_rules.label(.5, .5), 'Lawful Good')
        self.assertEqual(alignment_rules.label(0., 0.), 'True Neutral')
        self.assertEqual(alignment_rules.code(-.5, -.5), 'CE')

    def test_every_archetype_reads_differently_in_every_cell_and_rejects_none(self):
        policies = load_all()
        overlays = policies['axis_overlays']
        for card in policies['archetypes']['cards']:
            personas = {}
            for law in (-1., 0., 1.):
                for good in (-1., 0., 1.):
                    record = alignment_rules.record(law, good)
                    persona = compose(card, overlays, record)
                    self.assertTrue(persona['never'] and persona['line'] and persona['manner'])
                    personas[record['code']] = persona
            self.assertEqual(len({json.dumps(p, sort_keys=True) for p in personas.values()}), 9, card['id'])
            self.assertIn('harm an innocent to advance the claim', personas['LG']['never'])
            self.assertNotIn('harm an innocent to advance the claim', personas['LE']['never'])
            self.assertNotEqual(personas['LG']['lies'], personas['CE']['lies'])

    def test_intensity_pushes_to_the_corner_or_the_moral_pole(self):
        import random
        base = alignment_rules.record(.2, -.1)
        corner = alignment_rules.intensify(base, 'corner', random.Random(1))
        self.assertEqual((corner['law'], corner['good']), (1., -1.))
        pole = alignment_rules.intensify(base, 'good_axis', random.Random(1))
        self.assertEqual((pole['law'], pole['good']), (.2, -1.))
        self.assertIs(alignment_rules.intensify(base, None, random.Random(1)), base)


class CatalogueTests(unittest.TestCase):
    def test_catalogue_is_complete_and_names_only_known_features(self):
        document = load('archetypes')
        lint_archetypes(document)
        self.assertGreaterEqual(len(document['cards']), 32)
        for card in document['cards']:
            for conjunction in card['requires']:
                for feature in conjunction:
                    self.assertIn(feature, archetype_rules.FEATURES, card['id'])
            for feature in card['boosts']:
                self.assertIn(feature, archetype_rules.FEATURES, card['id'])

    def test_preconditions_filter_and_priors_only_weight(self):
        import random
        cards = load('archetypes')['cards']
        tyrant = next(c for c in cards if c['id'] == 'tyrant')
        self.assertTrue(archetype_rules.eligible(tyrant, {'role:warlord', 'war:civil_victor'}))
        self.assertFalse(archetype_rules.eligible(tyrant, {'role:warlord', 'war:regional_victor'}))
        good = alignment_rules.record(1., 1.)
        evil = alignment_rules.record(1., -1.)
        self.assertGreater(archetype_rules.weight(tyrant, set(), evil), archetype_rules.weight(tyrant, set(), good))
        self.assertGreater(archetype_rules.weight(tyrant, set(), good), 0.)
        self.assertIsNone(archetype_rules.choose(cards, {'role:nothing'}, good, random.Random(0)))

    def test_broken_policies_fail_loudly(self):
        document = load('archetypes')
        broken = copy.deepcopy(document)
        del broken['cards'][0]['pole_notes']['evil']
        with self.assertRaises(ValueError):
            lint_archetypes(broken)
        with self.assertRaises(ValueError):
            load('unknown')


class IsolationTests(unittest.TestCase):
    # The seed helper is no longer copied into this package; it is imported from the shared,
    # generator-free `world_geometry`, and `Sim/tests/test_world_geometry.py` is the one pin
    # holding it to `icarus_sim.terrain_tectonics.child_seed`. A second pin here would assert
    # the same equality by a longer route. The isolation assertion below is the part that is
    # still this package's own, and it stays.

    def test_attach_reports_failure_instead_of_raising_and_honours_the_switch(self):
        block = hero_generator.attach({'config': {'seed': 1}})
        # A failed block still names the version it would have written, so a consumer can
        # tell which contract failed rather than only that something did.
        self.assertEqual((block['version'], block['status']), (hero_generator.VERSION, 'failed'))
        self.assertIn('history.ages', block['error'])
        with patch.dict(os.environ, {hero_generator.ENV_SWITCH: '0'}):
            self.assertIsNone(hero_generator.attach(world()))
        with patch.dict(os.environ, {hero_generator.ENV_SWITCH: '1'}):
            self.assertEqual(hero_generator.attach(world())['status'], 'ok')
        with self.assertRaises(ValueError):
            hero_generator.generate({'config': {'seed': 'x'}})

    def test_package_reads_only_the_world_json(self):
        import pathlib
        root = pathlib.Path(hero_generator.__file__).parent
        for path in root.rglob('*.py'):
            for line in path.read_text(encoding='utf-8').splitlines():
                self.assertFalse(line.lstrip().startswith(('import icarus_sim', 'from icarus_sim')), f'{path}: {line}')


if __name__ == '__main__':
    unittest.main()
