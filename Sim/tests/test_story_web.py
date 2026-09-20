"""The story web compiles every living hero's spokes from the cast and changes nothing.

Hand-built worlds from the hero generator tests keep this fast; the generated-world
conformance check lives with the world schema tests.
"""
import copy
import json
import os
import pathlib
import sys
import unittest
from unittest.mock import patch

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))  # the cast fixture lives beside this file

import hero_generator
import story_web
from story_web import weights as weight_rules
from story_web.facts import FACTS, WorldFacts, person_facts
from story_web.policy import lint_tropes, load, load_all
from story_web.predicates import eligible, missing
from story_web.seeds import child_seed
from story_web.threads import RANK, opposes, threads_from

import test_hero_generator as cast_fixture

ROOT = pathlib.Path(__file__).resolve().parents[2]


def woven_world(**kwargs):
    world = cast_fixture.world(**kwargs)
    world['heroes'] = hero_generator.generate(world, cast_fixture.certain())
    return world


def web_of(block, uid):
    return next(w for w in block['webs'] if w['uid'] == uid)


class CompileTests(unittest.TestCase):
    def test_every_living_hero_is_woven_or_reported_with_the_nearest_misses(self):
        world = woven_world()
        block = story_web.generate(world)
        self.assertEqual(block['status'], 'ok')
        living = {p['uid'] for p in world['heroes']['people'] + world['heroes']['dreads'] if p['status'] == 'living'}
        self.assertEqual({w['uid'] for w in block['webs']} | {u['uid'] for u in block['unwoven']}, living)
        self.assertEqual(block['summary']['woven'] + block['summary']['unwoven'], len(living))
        for web in block['webs']:
            self.assertEqual(web['offered'], web['spokes'][0]['trope_id'])
            weights = [s['weight'] for s in web['spokes']]
            self.assertEqual(weights, sorted(weights, reverse=True))
            self.assertEqual([a['ring'] for a in web['acts']], [1, 2, 3])
            self.assertEqual(web['rest']['hook']['trope_id'], web['offered'])
            self.assertEqual([a['trope_id'] for a in web['rest']['armed']], [s['trope_id'] for s in web['spokes'][1:]])
            self.assertGreaterEqual(web['rest']['initiative_day'], 90)
            for act in web['acts']:
                self.assertTrue(2 <= len(act['options']) <= 4)
                self.assertEqual(act['abandonment']['implicit'], ['protagonist_dead', 'target_gone'])
            ranks = [(RANK[t['condition']['kind']], -t['weight'], t['to']) for t in web['threads']]
            self.assertEqual(ranks, sorted(ranks), 'threads are open first, then by weight')
            for thread in web['threads']:
                self.assertNotEqual(thread['to'], web['offered'])
        for entry in block['unwoven']:
            self.assertTrue(entry['nearest'])
        self.assertEqual(sum(block['summary']['offered'].values()), block['summary']['woven'])
        self.assertEqual(block['unreachable_tropes'], [], 'every trope has an entry some well can satisfy')
        self.assertEqual(block['summary']['reachable_tropes'], block['summary']['tropes'])

    def test_exported_objects_are_not_the_policy_documents(self):
        policies = load_all()
        block = story_web.generate(woven_world(), policies)
        court = [w for w in block['webs'] if w['offered'] == 'the_court']
        self.assertGreaterEqual(len(court), 2)
        self.assertIsNot(court[0]['acts'][0]['options'][0]['delta'], court[1]['acts'][0]['options'][0]['delta'])
        catalogue = next(t for t in policies['tropes']['tropes'] if t['id'] == 'the_court')
        self.assertIsNot(court[0]['acts'][0]['completion'], catalogue['acts'][0]['completion'])
        court[0]['acts'][0]['options'][0]['delta']['law'] = 9.
        self.assertNotEqual(catalogue['acts'][0]['options'][0]['delta']['law'], 9.)

    def test_replay_is_byte_identical_and_the_world_is_untouched(self):
        world = woven_world()
        before = json.dumps(world, sort_keys=True)
        first = story_web.generate(world)
        self.assertEqual(json.dumps(world, sort_keys=True), before)
        self.assertEqual(json.dumps(first, sort_keys=True), json.dumps(story_web.generate(woven_world()), sort_keys=True))
        json.dumps(first, allow_nan=False)
        other = woven_world(seed=7)
        self.assertNotEqual([w['rest']['initiative_day'] for w in story_web.generate(other)['webs']][:3],
                            [w['rest']['initiative_day'] for w in first['webs']][:3])

    def test_dreads_walk_only_dread_spokes_and_people_never_walk_the_lair(self):
        block = story_web.generate(woven_world())
        dread = web_of(block, 'dread-nest-ashen-wyrm-151')
        self.assertEqual(dread['offered'], 'the_lair')
        self.assertEqual(dread['rest']['hook']['prompt'], '')
        for thread in dread['threads']:
            self.assertIn(thread['to'], ('the_bargain', 'the_cage'))
        for web in block['webs']:
            if web['role'] != 'dread':
                self.assertNotIn('the_lair', [s['trope_id'] for s in web['spokes']])

    def test_prompts_bind_the_heros_own_names(self):
        block = story_web.generate(woven_world())
        heir = web_of(block, 'hero-pretender-surface-city-0-150-dwarf')
        self.assertEqual(heir['offered'], 'the_hunt')
        self.assertIn('Ashen wyrm', heir['rest']['hook']['prompt'])
        self.assertTrue(heir['rest']['hook']['prompt'][0].isupper())
        for web in block['webs']:
            for act in web['acts']:
                self.assertNotIn('{', act['prompt'])
                for option in act['options']:
                    self.assertNotIn('{', option['text'])

    def test_the_offered_spoke_is_the_heaviest_and_ties_break_on_trope_id(self):
        policies = load_all()
        for trope in policies['tropes']['tropes']:
            trope['boosts'] = {}
            trope['fits'] = []
            trope['claims'] = []
            trope['pull'] = {'law': 0., 'good': 0.}
        block = story_web.generate(woven_world(), policies)
        for web in block['webs']:
            self.assertEqual({s['weight'] for s in web['spokes']}, {1.})
            self.assertEqual([s['trope_id'] for s in web['spokes']], sorted(s['trope_id'] for s in web['spokes']))


class WeightTests(unittest.TestCase):
    def test_alignment_fit_favours_the_pull_and_never_removes_a_spoke(self):
        policy = load('weights')
        pull = {'law': 0.5, 'good': 0.5}
        with_it = weight_rules.alignment_fit(pull, {'law': 1., 'good': 1.}, policy)
        against = weight_rules.alignment_fit(pull, {'law': -1., 'good': -1.}, policy)
        neutral = weight_rules.alignment_fit(pull, {'law': 0., 'good': 0.}, policy)
        self.assertGreater(with_it, neutral)
        self.assertGreater(neutral, against)
        self.assertGreaterEqual(against, policy['fit_floor'])
        self.assertEqual(neutral, 1.)

    def test_archetype_and_claim_fits_multiply_and_the_breakdown_explains_the_number(self):
        policy = load('weights')
        trope = {'id': 't', 'pull': {'law': 0., 'good': 0.}, 'boosts': {'home:fell': 2.}, 'fits': ['broken_soul'], 'claims': ['avenge']}
        hero = {'alignment': {'law': 0., 'good': 0.}, 'archetype': 'broken_soul', 'claim': {'verb': 'avenge'}}
        value, breakdown = weight_rules.weight(trope, {'home:fell'}, hero, policy)
        self.assertEqual(value, round(2. * policy['fits_factor'] * policy['claim_factor'], 4))
        self.assertEqual(breakdown['boosted_by'], ['home:fell'])
        plain, _ = weight_rules.weight(trope, set(), {'alignment': hero['alignment'], 'archetype': 'x', 'claim': {'verb': 'hold'}}, policy)
        self.assertEqual(plain, 1.)
        block = story_web.generate(woven_world())
        for web in block['webs']:
            for spoke in web['spokes']:
                b = spoke['breakdown']
                self.assertEqual(spoke['weight'], round(b['boosts'] * b['alignment_fit'] * b['archetype_fit'] * b['claim_fit'], 4), spoke)

    def test_opposition_is_the_sign_of_the_dot_product(self):
        self.assertIsNone(opposes({'law': 0., 'good': 1.}, {'law': 0., 'good': .2}))
        self.assertIsNone(opposes({'law': .05, 'good': 0.}, {'law': 0., 'good': 0.}))
        self.assertEqual(opposes({'law': 0., 'good': 1.}, {'law': 0., 'good': -.2}), ('good', 'up'))
        self.assertEqual(opposes({'law': -.6, 'good': .3}, {'law': 1., 'good': .1}), ('law', 'down'))

    def test_angle_puts_good_to_the_right_and_lawful_up(self):
        self.assertEqual(weight_rules.angle_degrees(0., 1.), 0.)
        self.assertEqual(weight_rules.angle_degrees(1., 0.), 90.)
        self.assertEqual(weight_rules.angle_degrees(0., -1.), 180.)
        self.assertEqual(weight_rules.angle_degrees(-1., 0.), 270.)


class ThreadTests(unittest.TestCase):
    def test_archetype_constraints_cut_threads_that_need_a_forbidden_change(self):
        policies = load_all()
        tropes = policies['tropes']['tropes']
        hunt = next(t for t in tropes if t['id'] == 'the_hunt')
        hunter = {'uid': 'x', 'role': 'pretender', 'archetype': 'obsessed_hunter', 'alignment': {'law': 0., 'good': 0.}, 'claim': {'verb': 'kill'}}
        facts = {'role:pretender', 'status:living', 'dread:living', 'claim:kill', 'home:set'}
        threads = threads_from(hunt, tropes, facts, hunter, policies)
        by_to = {t['to']: t for t in threads}
        claim_threads = [t for t in threads if t['condition']['kind'] == 'claim']
        self.assertTrue(claim_threads)
        for t in claim_threads:
            self.assertIn('not allowed by archetype', t['cut'])
        oathbound = dict(hunter, archetype='oathbound')
        for t in threads_from(hunt, tropes, facts, oathbound, policies):
            if t['condition']['kind'] == 'claim':
                self.assertEqual(t['cut'], 'claim locked by archetype')
        incarnate = dict(hunter, archetype='incarnate')
        for t in threads_from(hunt, tropes, facts, incarnate, policies):
            if t['condition']['kind'] == 'alignment':
                self.assertEqual(t['cut'], 'drift locked by archetype')
        free = dict(hunter, archetype='reluctant_hero')
        self.assertTrue(all(t['cut'] is None for t in threads_from(hunt, tropes, facts, free, policies)))
        self.assertLessEqual(len(threads), policies['weights']['max_threads_per_act'])
        self.assertNotIn('the_hunt', by_to)

    def test_feature_threads_only_name_gainable_facts(self):
        policies = load_all()
        gainable = set(policies['weights']['gainable_features'])
        block = story_web.generate(woven_world(), policies)
        for web in block['webs']:
            for thread in web['threads']:
                if thread['condition']['kind'] == 'feature':
                    for fact in thread['condition']['facts']:
                        self.assertFalse(fact.startswith('!'))
                        self.assertIn(fact, gainable)

    def test_every_conjunction_is_tried_and_thread_weights_are_post_condition(self):
        policies = load_all()
        policies['weights']['max_threads_per_act'] = 100  # look at every candidate, not just the capped list
        tropes = policies['tropes']['tropes']
        hunt = next(t for t in tropes if t['id'] == 'the_hunt')
        # A champion whose nearest Unmasking conjunction (faces:two) is unreachable but whose other
        # conjunction (deed:credited_not_actual) is gainable must still get the thread.
        champion = {'uid': 'c', 'role': 'champion', 'archetype': 'knight_errant', 'alignment': {'law': 0., 'good': 0.}, 'claim': {'verb': 'kill'}}
        facts = {'role:champion', 'status:living', 'claim:kill', 'home:set', 'world:dread_living'}
        threads = {t['to']: t for t in threads_from(hunt, tropes, facts, champion, policies)}
        self.assertEqual(threads['unmasking']['condition'], {'kind': 'feature', 'facts': ['deed:credited_not_actual']})
        # A claim thread is weighed with the changed verb applied, so the claim fit counts.
        crusade = threads['crusade'] if 'crusade' in threads else None
        if crusade is not None:
            after = dict(champion, claim={'verb': 'convert'})
            trope = next(t for t in tropes if t['id'] == 'crusade')
            expected = weight_rules.weight(trope, (facts - {'claim:kill'}) | {'claim:convert'}, after, policies['weights'])[0]
            self.assertEqual(crusade['weight'], expected)


class FactTests(unittest.TestCase):
    def test_person_and_world_facts_read_the_record_and_the_world_only(self):
        world = woven_world()
        heroes = world['heroes']
        heir = next(p for p in heroes['people'] if p['uid'] == 'hero-pretender-surface-city-0-150-dwarf')
        facts = person_facts(heir, heroes['bonds'])
        self.assertTrue({'role:pretender', 'status:living', 'claim:retake', 'lost:set', 'tier:' + heir['tier']} <= facts)
        self.assertIn('bond:rival', facts)
        world_facts = WorldFacts(world, heroes, load('weights')).for_hero(heir)
        self.assertIn('world:rival_dread', world_facts)
        self.assertIn('world:relic_resting', world_facts)
        for fact in facts | world_facts:
            self.assertTrue(fact in FACTS or fact.startswith('archetype:'), fact)
        empty = WorldFacts({'config': {'seed': 1}}, {'people': [], 'dreads': []}, load('weights'))
        self.assertEqual(empty.for_hero({'uid': 'x', 'civilization_id': 'c'}), set())

    def test_world_facts_fire_from_threat_food_moon_nodes_and_mantles(self):
        world = woven_world()
        heroes = world['heroes']
        heir = next(p for p in heroes['people'] if p['uid'] == 'hero-pretender-surface-city-0-150-dwarf')
        home = heir['home']['uid']
        site_id = next(s['id'] for s in world['settlements']['sites'] if s['uid'] == home)
        world['threat_assessments'] = {'cities': [{'city_uid': home, 'war_pressure': .15, 'regional_threat': .6, 'war_risk': .3, 'enemy_living': True}]}
        world['humans']['cores'] = [{'site_id': site_id, 'food_deficit': 3.}]
        world['seasonal_food'] = {'cities': [{'site_id': site_id, 'food_coverage': .2}]}
        world['lunar_almanac'] = {'events': [{'day': 3, 'kind': 'surge', 'school': 'umbral'}, {'day': 9, 'kind': 'hollow_night'}]}
        heroes['mantles'] = [{'claim': {'verb': 'retake'}, 'predecessor_uid': 'legend-x', 'civilization_id': heir['civilization_id'], 'vacant_since_age': 1}]
        facts = WorldFacts(world, heroes, load('weights')).for_hero(heir)
        for fact in ('world:war_pressure', 'world:threatened', 'world:food_deficit', 'world:famine', 'world:war_risk',
                     'world:enemy_living', 'world:surge', 'world:hollow_night', 'world:mantle_open'):
            self.assertIn(fact, facts)
        keeper = next(p for p in heroes['people'] if p['role'] == 'domain_holder')
        self.assertIn('world:node_intense', WorldFacts(world, heroes, load('weights')).for_hero(keeper))
        block = story_web.generate(world)
        self.assertEqual(block['status'], 'ok')
        self.assertIn('the_siege', [s['trope_id'] for s in web_of(block, heir['uid'])['spokes']])
        self.assertIn('the_famine', [s['trope_id'] for s in web_of(block, heir['uid'])['spokes']])

    def test_bind_survives_records_without_names_or_with_carried_relics(self):
        from story_web.bind import fill, slots_for
        heroes = {'people': [{'uid': 'a'}], 'dreads': [], 'realms': [{'uid': 'r1'}, {'uid': 'r2', 'name': 'Realm of Two'}],
                  'relics': [{'resting_at': 'lost-1', 'name': 'the crown', 'holder_uid': 'a'}, {'name': 'carried'}]}
        hero = {'uid': 'a', 'home': {'uid': 'h'}, 'lost': {'uid': 'lost-1', 'name': 'Lost City'}, 'realm_uid': 'r1', 'rivals': ['zzz'],
                'claim': {'verb': 'retake'}}
        slots = slots_for(hero, heroes)
        self.assertEqual(fill('{hero} at {home} wants {relic} from {lost} near {realm_other}, rival {rival}', slots),
                         'A at their home wants the relic from Lost City near Realm of Two, rival zzz')

    def test_predicates_negate_and_report_the_nearest_miss(self):
        facts = {'a', 'b'}
        self.assertTrue(eligible([['a', '!c']], facts))
        self.assertFalse(eligible([['a', 'c']], facts))
        self.assertEqual(missing([['a', 'c', 'd'], ['b', 'c']], facts), ['c'])
        self.assertEqual(missing([['a']], facts), [])


class CatalogueTests(unittest.TestCase):
    def test_catalogue_is_complete_names_only_known_facts_and_covers_every_archetype(self):
        document = load('tropes')
        lint_tropes(document)
        self.assertGreaterEqual(len(document['tropes']), 40)
        archetypes = {c['id'] for c in json.loads((ROOT / 'Sim/hero_generator/policies/archetypes.json').read_text(encoding='utf-8'))['cards']}
        fitted = {a for t in document['tropes'] for a in t['fits']}
        self.assertEqual(archetypes - fitted, set(), 'every archetype must fit at least one spoke')
        self.assertEqual(fitted - archetypes, set(), 'fits must name real archetypes')
        for trope in document['tropes']:
            for act in trope['acts']:
                self.assertTrue(act['prompt'] or trope['cast'] == ['dread'], f'{trope["id"]} has a silent act for people')

    def test_never_computed_names_only_features_no_well_emits(self):
        """The cities well precipitates diaspora leaders, so those roles are reachable; the reserved trio is not."""
        world = cast_fixture.world()
        city = world['settlements']['sites'][0]
        city.update(diaspora=True, diaspora_reason='religious_schism', founded_age=1,
                    migration_source_node=world['settlements']['sites'][1]['node'])
        block = hero_generator.generate(world, cast_fixture.certain())
        emitted = {f for p in block['people'] + block['dreads'] for f in p['selectable']}
        self.assertIn('role:prophet', emitted)
        self.assertFalse(story_web.NEVER_COMPUTED & emitted, story_web.NEVER_COMPUTED & emitted)
        source = (ROOT / 'Sim/hero_generator/wells/cities.py').read_text(encoding='utf-8')
        for role in ('prophet', 'exile', 'founder'):
            self.assertIn(f"'{role}'", source, f'the cities well should still map a diaspora reason to {role}')
        world['heroes'] = block
        web = story_web.generate(world)
        prophet = next(w for w in web['webs'] if w['role'] in ('prophet', 'heresiarch'))
        self.assertIn('crusade', [s['trope_id'] for s in prophet['spokes']] + [t['to'] for t in prophet['threads']])

    def test_war_outlook_and_famine_facts_read_threat_three_and_the_seasonal_model(self):
        world = woven_world()
        heroes = world['heroes']
        final = heroes['final_age']
        heir = next(p for p in heroes['people'] if p['uid'] == 'hero-pretender-surface-city-0-150-dwarf')
        home = heir['home']['uid']
        site_id = next(s['id'] for s in world['settlements']['sites'] if s['uid'] == home)
        world['threat_assessments'] = {'cities': [{'city_uid': home, 'war_pressure': .15, 'regional_threat': .2, 'wars_recent': 1,
                                                   'enemy_living': True, 'war_risk': .4, 'war_risk_kind': 'civil', 'war_risk_opponent_uid': 'x'}]}
        world['seasonal_food'] = {'cities': [{'site_id': site_id, 'food_coverage': .3}]}
        facts = WorldFacts(world, heroes, load('weights')).for_hero(heir)
        for fact in ('world:war_recent', 'world:enemy_living', 'world:war_risk', 'world:famine', 'world:war_pressure'):
            self.assertIn(fact, facts)
        fed = copy.deepcopy(world)
        fed['seasonal_food'] = {'cities': [{'site_id': site_id, 'food_coverage': .9}]}
        self.assertNotIn('world:famine', WorldFacts(fed, heroes, load('weights')).for_hero(heir))
        victor = {'uid': 'v', 'role': 'warlord', 'status': 'living', 'tier': 'notable', 'claim': {'verb': 'hold'},
                  'deeds': [{'event_kind': 'war', 'role': 'credited', 'age': final}, {'event_kind': 'war', 'role': 'victim', 'age': final - 1}]}
        self.assertTrue({'war:veteran', 'war:victor_recent'} <= person_facts(victor, [], final))
        self.assertNotIn('war:defeated_recent', person_facts(victor, [], final))
        block = story_web.generate(world)
        spokes = [s['trope_id'] for s in web_of(block, heir['uid'])['spokes']]
        self.assertIn('the_siege', spokes, 'a living enemy and a war risk admit the Siege')
        self.assertIn('the_famine', spokes)

    def test_victors_walk_post_war_spokes_and_the_siege_needs_a_real_threat(self):
        world = woven_world()
        heroes = world['heroes']
        warlord = next(p for p in heroes['people'] if p['role'] == 'warlord')
        block = story_web.generate(world)
        web = web_of(block, warlord['uid'])
        spokes = [s['trope_id'] for s in web['spokes']]
        self.assertIn('the_veteran', spokes, 'a warlord with no war risk is a veteran')
        self.assertNotIn('the_siege', spokes, 'no forecast, no living enemy: nobody is coming')
        if 'war:victor_recent' in web['facts']:
            self.assertIn('the_spoils', spokes)
        for w in block['webs']:
            for trope_id in ('the_spoils', 'the_veteran', 'the_pursuit'):
                if trope_id in [s['trope_id'] for s in w['spokes']]:
                    self.assertIn(w['role'], ('warlord', 'sovereign'))

    def test_malformed_world_rows_cost_one_fact_not_the_block(self):
        world = woven_world()
        world['threat_assessments'] = {'cities': [{'war_pressure': 1.}, 'junk', None]}
        world['humans']['cores'] = [{'site_id': 0, 'food_deficit': 'many'}, 7]
        world['lunar_almanac'] = {'events': 'surge'}
        world['magic']['networks'] = ['not', 'a', 'dict']
        world['heroes']['relics'] = [{'name': 'loose'}] + world['heroes']['relics']
        world['heroes']['camps'] = [{}] + world['heroes']['camps']
        world['heroes']['mantles'] = [{'claim': {}}]
        world['heroes']['bonds'] = [{'a': 'x'}] + world['heroes']['bonds']
        block = story_web.generate(world)
        self.assertEqual(block['status'], 'ok')
        self.assertEqual(block['summary']['unwoven'], 0)

    def test_broken_policies_fail_loudly(self):
        document = load('tropes')
        broken = copy.deepcopy(document)
        broken['tropes'][0]['requires'] = [['no:such_fact']]
        with self.assertRaises(ValueError):
            lint_tropes(broken)
        broken = copy.deepcopy(document)
        broken['tropes'][0]['acts'][0]['options'][0]['delta']['good'] = 0.9
        with self.assertRaises(ValueError):
            lint_tropes(broken)
        broken = copy.deepcopy(document)
        del broken['tropes'][0]['acts'][2]
        with self.assertRaises(ValueError):
            lint_tropes(broken)
        with self.assertRaises(ValueError):
            load('unknown')


class FixtureTests(unittest.TestCase):
    def test_pinned_fixture_cast_yields_the_pinned_web(self):
        """A policy edit must change this on purpose: bump the fixture, never silently drift."""
        fixture = json.loads((ROOT / 'Fixtures' / 'story-web-v1.json').read_text(encoding='utf-8'))
        block = story_web.generate(fixture['world'])
        self.assertEqual(block['policy_revision'], fixture['policy_revision'])
        self.assertEqual(block['summary'], fixture['expected']['summary'])
        self.assertEqual({w['uid']: w['offered'] for w in block['webs']}, fixture['expected']['offered'])
        self.assertEqual({w['uid']: [[s['trope_id'], s['weight']] for s in w['spokes']] for w in block['webs']}, fixture['expected']['spokes'])
        self.assertEqual({w['uid']: [[t['to'], t['condition']['kind'], t['cut']] for t in w['threads']] for w in block['webs']},
                         fixture['expected']['threads'])
        self.assertEqual([u['uid'] for u in block['unwoven']], fixture['expected']['unwoven'])

    def test_report_lists_every_web_and_flags_only_review_items(self):
        from story_web.report import flags, lines
        policies = load_all()
        tropes = {t['id']: t for t in policies['tropes']['tropes']}
        world = woven_world()
        block = story_web.generate(world, policies)
        text = '\n'.join(lines(block, tropes, world['heroes']))
        for web in block['webs']:
            self.assertIn(web['uid'], text)
        self.assertIn('review (', text)
        self.assertIn('tilt (', text)
        for uid, name, reason in flags(block, tropes):
            self.assertTrue(reason.split(':')[0] in ('generic', 'unfit', 'claim', 'close', 'unwoven'), reason)


class IsolationTests(unittest.TestCase):
    def test_seed_helper_matches_the_generator(self):
        from icarus_sim.terrain_tectonics import child_seed as reference
        for master, domain, variation in ((42, 'web-x', 0), (7, 'web-initiative-a', 3), (4294967295, '', 1)):
            self.assertEqual(child_seed(master, domain, variation), reference(master, domain, variation))

    def test_attach_reports_failure_instead_of_raising_and_honours_the_switch(self):
        block = story_web.attach({'config': {'seed': 1}})
        self.assertEqual((block['version'], block['status']), (1, 'failed'))
        self.assertIn('heroes', block['error'])
        failed = {'config': {'seed': 1}, 'heroes': {'version': 1, 'status': 'failed', 'error': 'boom'}}
        self.assertIn('boom', story_web.attach(failed)['error'])
        with patch.dict(os.environ, {story_web.ENV_SWITCH: '0'}):
            self.assertIsNone(story_web.attach(woven_world()))
        with patch.dict(os.environ, {story_web.ENV_SWITCH: '1'}):
            self.assertEqual(story_web.attach(woven_world())['status'], 'ok')
        with self.assertRaises(ValueError):
            story_web.generate({'config': {'seed': 'x'}})

    def test_package_reads_only_the_exported_blocks(self):
        root = pathlib.Path(story_web.__file__).parent
        for path in root.rglob('*.py'):
            for line in path.read_text(encoding='utf-8').splitlines():
                self.assertFalse(line.lstrip().startswith(('import icarus_sim', 'from icarus_sim', 'import hero_generator', 'from hero_generator')),
                                 f'{path}: {line}')

    def test_lab_renders_the_web_and_hides_it_before_stage_sixteen(self):
        js = (ROOT / 'tools' / 'terrain_world.js').read_text(encoding='utf-8')
        self.assertIn('function renderStoryWebs', js)
        self.assertIn('data.story_web', js)
        html = (ROOT / 'tools' / 'terrain_lab.html').read_text(encoding='utf-8')
        self.assertIn("'story_web'", html.split('const historyStateKeys=')[1].split(';')[0])


if __name__ == '__main__':
    unittest.main()
