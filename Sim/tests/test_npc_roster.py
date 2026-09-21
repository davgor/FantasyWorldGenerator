"""The NPC roster: one record per staffed post, an earmark that stays bounded, and a life state.

The world here is hand-built rather than generated so the suite stays fast and so each
invariant can be moved one field at a time. The registry lint and the seed-parity test are
the two that reach into `icarus_sim`; the package itself must never do so, and a test below
asserts exactly that.
"""
import copy
import json
from pathlib import Path
import sys
import unittest

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / 'Sim'))

import npc_roster
from npc_roster import policy, sites
from npc_roster.seeds import child_seed


def plot(index, building_id, workers, name='Thing'):
    return {'id': f'plot-{index}', 'building_id': building_id, 'name': name, 'kind': 'service',
            'phase': 'high', 'x_m': 0., 'z_m': 0., 'workers': workers, 'beds': 0}


def world(**overrides):
    """A two-city, one-hamlet, one-fortress world with a cast, in export shape."""
    document = {
        'config': {'seed': 42, 'size': 17},
        'civilizations': {'entities': [{'id': 'human_heartland', 'name': 'Heartland', 'parent_race_id': 'human'},
                                       {'id': 'dwarf', 'name': 'Dwarves', 'parent_race_id': 'dwarf'}],
                          'registry': {'revision': 12, 'sha256': 'abc'}},
        'settlements': {'sites': [
            {'id': 0, 'uid': 'surface-city-0-40-human_heartland', 'name': 'Bracken City (Age 1)', 'node': 40,
             'x': 6, 'z': 2, 'civilization_id': 'human_heartland', 'parent_race_id': 'human', 'city_class': 'medium'},
            {'id': 1, 'uid': 'surface-city-0-77-dwarf', 'name': 'Umber City', 'node': 77, 'x': 9, 'z': 4,
             'civilization_id': 'dwarf', 'parent_race_id': 'dwarf', 'city_class': 'small'}]},
        'humans': {'fortresses': [{'id': 'fortress-0', 'kind': 'fortress', 'node': 512, 'x': 3, 'z': 3,
                                   'core_id': 0, 'population_profile': 'human_heartland',
                                   'culture_id': 'human_heartland-deadbeef'}],
                   'hamlets': [{'id': 'hamlet-0', 'node': 301, 'core_id': 0, 'population_profile': 'human_heartland'}]},
        'city_plans': {'version': 6, 'cities': [
            {'version': 6, 'city_uid': 'surface-city-0-40-human_heartland', 'name': 'Bracken City (Age 1)',
             'civilization_id': 'human_heartland', 'city_class': 'medium', 'status': 'complete',
             'plots': [plot(0, 'building.smithy', 2), plot(1, 'building.guildhall', 2),
                       plot(2, 'building.worker_house', 0), plot(3, 'building.guardhouse', 8)]},
            {'version': 6, 'city_uid': 'surface-city-0-77-dwarf', 'name': 'Umber City', 'civilization_id': 'dwarf',
             'city_class': 'small', 'status': 'unbuildable', 'plots': []}]},
        'hamlet_plans': {'version': 2, 'hamlets': [
            {'version': 2, 'hamlet_id': 'coastal-0-0', 'kind': 'hamlet', 'role': 'farming', 'node': 301,
             'core_city_uid': 'surface-city-0-40-human_heartland', 'core_id': 0,
             'civilization_id': 'human_heartland', 'status': 'complete',
             'plots': [plot(0, 'building.hamlet_farmyard', 3), plot(1, 'building.hamlet_smith_shed', 1)]}]},
        'castle_plans': {'version': 1, 'castles': [
            {'version': 1, 'kind': 'castle', 'fortress_id': 'fortress-0', 'core_id': 0, 'x': 3, 'z': 3,
             'status': 'complete', 'plots': [plot(0, 'building.keep_tower', 8)]}]},
        'heroes': {'version': 1, 'status': 'ok', 'people': [
            {'uid': 'hero-sovereign-surface-city-0-40-human_heartland', 'role': 'sovereign', 'status': 'living',
             'name': 'Marel', 'display_name': 'Marel the Sovereign', 'race_id': 'human',
             'civilization_id': 'human_heartland', 'home': {'uid': 'surface-city-0-40-human_heartland'},
             'presence': {'site_kind': 'city', 'uid': 'surface-city-0-40-human_heartland', 'situation': 'throne'}},
            {'uid': 'hero-pretender-surface-city-9-99-dwarf', 'role': 'pretender', 'status': 'legend',
             'name': 'Torin', 'display_name': 'Torin the Heir', 'race_id': 'dwarf', 'civilization_id': 'dwarf',
             'home': None, 'presence': None},
            {'uid': 'hero-castellan-fortress-0', 'role': 'castellan', 'status': 'living', 'name': 'Bren',
             'display_name': 'Bren Castellan', 'race_id': 'human', 'civilization_id': 'human_heartland',
             'home': {'uid': 'surface-city-0-40-human_heartland'},
             'presence': {'site_kind': 'fortress', 'uid': 'fortress-0', 'situation': 'post'}}],
                   'dreads': []},
    }
    document.update(overrides)
    return document


class RosterTests(unittest.TestCase):
    def setUp(self):
        self.block = npc_roster.generate(world())

    def posts_at(self, site_uid):
        return [p for p in self.block['people'] if p['site_uid'] == site_uid and 'hero_uid' not in p]

    def test_every_staffed_plot_yields_exactly_its_worker_count_in_posts(self):
        city = self.posts_at('surface-city-0-40-human_heartland')
        self.assertEqual(len(city), 12)  # smithy 2 + guildhall 2 + guardhouse 8
        self.assertEqual(sorted(p['post'] for p in city if p['building_id'] == 'building.smithy'),
                         ['apprentice', 'smith'])
        self.assertEqual(sum(p['building_id'] == 'building.guardhouse' for p in city), 8)

    def test_a_role_with_target_six_expands_to_six_distinct_records(self):
        guards = [p for p in self.posts_at('surface-city-0-40-human_heartland')
                  if p['post'] == 'watch_guard']
        self.assertEqual(len(guards), 6)
        self.assertEqual(len({p['uid'] for p in guards}), 6)

    def test_houses_and_unstaffed_plots_yield_nobody(self):
        self.assertFalse([p for p in self.block['people'] if p['building_id'] == 'building.worker_house'])

    def test_an_unbuildable_plan_keeps_its_site_row_with_no_people(self):
        row = next(s for s in self.block['sites'] if s['uid'] == 'surface-city-0-77-dwarf')
        self.assertEqual((row['plan_status'], row['posts']), ('unbuildable', 0))
        self.assertEqual(self.posts_at('surface-city-0-77-dwarf'), [])

    def test_replay_is_byte_identical_and_the_world_is_untouched(self):
        source = world()
        before = json.dumps(source, sort_keys=True)
        first = json.dumps(npc_roster.generate(source), sort_keys=True)
        second = json.dumps(npc_roster.generate(source), sort_keys=True)
        self.assertEqual(first, second)
        self.assertEqual(before, json.dumps(source, sort_keys=True))
        self.assertNotIn('npcs', source)

    def test_exported_objects_are_not_the_policy_documents(self):
        policies = policy.load_all()
        block = npc_roster.generate(world(), policies)
        block['verbs'].append('mutated')
        block['post_verbs']['smith'].append('mutated')
        self.assertNotIn('mutated', policies['posts']['verbs'])
        self.assertNotIn('mutated', policies['posts']['role_verbs']['smith'])

    def test_plot_ten_does_not_sort_before_plot_two(self):
        ordered = [sites._plot_order({'id': f'plot-{n}'}) for n in (2, 10)]
        self.assertLess(ordered[0], ordered[1])

    def test_every_person_resolves_to_a_site_or_declares_why_not(self):
        known = {s['uid'] for s in self.block['sites']}
        for person in self.block['people']:
            if person['site_uid'] is None:
                self.assertIn('hero_uid', person, f"{person['uid']} is a post with no site")
            else:
                self.assertIn(person['site_uid'], known)


class SiteTests(unittest.TestCase):
    def test_small_sites_anchor_on_the_node_not_the_renumbering_plan_id(self):
        block = npc_roster.generate(world())
        uids = {s['uid'] for s in block['sites']}
        self.assertIn('hamlet-node-301', uids)
        self.assertIn('fortress-node-512', uids)
        self.assertNotIn('hamlet-0', uids)
        self.assertNotIn('fortress-0', uids)

    def test_renumbering_a_plan_id_moves_nobody(self):
        """The failure this whole scheme exists to prevent: an age advance renumbers the
        ordinal ids, and a quest giver must not silently become a different person."""
        before = npc_roster.generate(world())
        renumbered = world()
        renumbered['humans']['fortresses'][0]['id'] = 'fortress-7'
        renumbered['castle_plans']['castles'][0]['fortress_id'] = 'fortress-7'
        renumbered['hamlet_plans']['hamlets'][0]['hamlet_id'] = 'coastal-4-9'
        after = npc_roster.generate(renumbered)
        self.assertEqual([p['uid'] for p in before['people']], [p['uid'] for p in after['people']])
        self.assertEqual([s['uid'] for s in before['sites']], [s['uid'] for s in after['sites']])

    def test_a_castle_carries_no_civilization_so_it_inherits_its_core_city(self):
        row = next(s for s in npc_roster.generate(world())['sites'] if s['kind'] == 'fortress')
        self.assertEqual(row['civilization_id'], 'human_heartland')
        self.assertEqual(row['parent_race_id'], 'human')
        self.assertEqual(row['name'], 'the fortress above Bracken')

    def test_a_fortress_with_no_matching_record_costs_one_site_not_the_block(self):
        broken = world()
        broken['humans']['fortresses'] = []
        block = npc_roster.generate(broken)
        self.assertEqual(block['status'], 'ok')
        self.assertEqual(block['summary']['unanchored_sites'], 1)
        self.assertFalse([s for s in block['sites'] if s['kind'] == 'fortress'])

    def test_an_unknown_civilization_leaves_the_parent_race_null_rather_than_guessing_human(self):
        broken = world()
        broken['civilizations']['entities'] = []
        broken['settlements']['sites'][0].pop('parent_race_id')
        block = npc_roster.generate(broken)
        row = next(s for s in block['sites'] if s['uid'] == 'surface-city-0-40-human_heartland')
        self.assertIsNone(row['parent_race_id'])
        self.assertGreaterEqual(block['summary']['unresolved_parent_race'], 1)

    def test_nothing_is_keyed_on_a_culture_id(self):
        """Culture ids rehash on every age advance; a key built on one silently breaks."""
        serialized = json.dumps(npc_roster.generate(world()))
        self.assertNotIn('deadbeef', serialized)


class EarmarkTests(unittest.TestCase):
    def test_the_earmark_is_bounded_by_the_per_site_cap(self):
        caps = policy.load('posts')['caps']
        block = npc_roster.generate(world())
        for row in block['sites']:
            cap = caps[row['city_class']] if row['kind'] == 'city' else caps[row['kind']]
            flagged = [p for p in block['people']
                       if p['site_uid'] == row['uid'] and p['important'] and 'hero_uid' not in p]
            self.assertLessEqual(len(flagged), cap, row['uid'])

    def test_only_a_senior_post_is_ever_earmarked(self):
        block = npc_roster.generate(world())
        for person in block['people']:
            if person['important'] and 'hero_uid' not in person:
                self.assertTrue(person['uid'].endswith('-0'), person['uid'])

    def test_every_hero_is_important_and_no_cap_can_demote_one(self):
        block = npc_roster.generate(world())
        cast = [p for p in block['people'] if 'hero_uid' in p]
        self.assertEqual(len(cast), 3)
        self.assertTrue(all(p['important'] for p in cast))

    def test_the_cast_dominates_the_fraction_on_a_small_world_so_the_bound_is_per_site(self):
        """Measured 9.4% on a size-17 world against 7.0% at size 65, because the cast is always
        important and is not capped. A flat percentage would be measuring the cast, not the cap."""
        block = npc_roster.generate(world())
        cast = sum('hero_uid' in p for p in block['people'] if p['important'])
        posts = block['summary']['important'] - cast
        self.assertEqual(cast, 3)
        self.assertLessEqual(posts, sum(policy.load('posts')['caps'][k] for k in ('medium', 'small', 'hamlet', 'fortress')))

    def test_two_sites_never_share_a_display_name(self):
        document = world()
        document['humans']['fortresses'].append({'id': 'fortress-1', 'kind': 'fortress', 'node': 640, 'x': 4, 'z': 4,
                                                 'core_id': 0, 'population_profile': 'human_heartland'})
        document['castle_plans']['castles'].append({'version': 1, 'kind': 'castle', 'fortress_id': 'fortress-1',
                                                    'core_id': 0, 'x': 4, 'z': 4, 'status': 'complete',
                                                    'plots': [plot(0, 'building.keep_tower', 8)]})
        names = [s['name'] for s in npc_roster.generate(document)['sites']]
        self.assertEqual(len(names), len(set(names)), names)

    def test_a_capped_out_candidate_is_counted_rather_than_hidden(self):
        crowded = world()
        plots = crowded['city_plans']['cities'][0]['plots']
        plots.extend([plot(10 + n, building, 2) for n, building in
                      enumerate(('building.inn', 'building.temple', 'building.court', 'building.library',
                                 'building.treasury', 'building.school'))])
        block = npc_roster.generate(crowded)
        self.assertGreater(block['summary']['important_capped_out'], 0)


class CastTests(unittest.TestCase):
    def test_legend_maps_to_dead_and_living_maps_to_alive(self):
        block = npc_roster.generate(world())
        by_hero = {p['hero_uid']: p for p in block['people'] if 'hero_uid' in p}
        self.assertEqual(by_hero['hero-sovereign-surface-city-0-40-human_heartland']['status'], 'alive')
        self.assertEqual(by_hero['hero-pretender-surface-city-9-99-dwarf']['status'], 'dead')

    def test_a_hero_with_no_presence_keeps_a_null_site_rather_than_a_dangling_one(self):
        block = npc_roster.generate(world())
        legend = next(p for p in block['people'] if p.get('hero_uid', '').startswith('hero-pretender'))
        self.assertIsNone(legend['site_uid'])
        self.assertIsNone(legend['site_kind'])
        self.assertEqual(block['summary']['cast_outside_a_planned_site'], 1)

    def test_a_hero_posted_to_a_fortress_carries_the_casts_own_reference(self):
        """The cast keys fortresses on the ordinal id and this package keys them on the node,
        so the two never join directly; carrying presence verbatim is what makes it resolvable."""
        block = npc_roster.generate(world())
        castellan = next(p for p in block['people'] if p.get('hero_uid') == 'hero-castellan-fortress-0')
        self.assertEqual((castellan['presence_kind'], castellan['presence_uid']), ('fortress', 'fortress-0'))

    def test_a_presence_elsewhere_carries_the_node_it_actually_stands_on(self):
        """A castellan filed under their home city is in a real place and the wrong one; anything
        measuring travel needs where they actually are, and only the world can do that join."""
        block = npc_roster.generate(world())
        castellan = next(p for p in block['people'] if p.get('hero_uid') == 'hero-castellan-fortress-0')
        self.assertEqual(castellan['site_uid'], 'surface-city-0-40-human_heartland')
        self.assertEqual((castellan['presence_node'], castellan['presence_x'], castellan['presence_z']), (512, 3, 3))
        self.assertEqual(block['summary']['cast_located_by_presence'], 1)

    def test_a_person_standing_where_they_are_filed_carries_no_second_position(self):
        block = npc_roster.generate(world())
        sovereign = next(p for p in block['people'] if p.get('hero_uid', '').startswith('hero-sovereign'))
        self.assertNotIn('presence_node', sovereign)

    def test_a_ruin_presence_resolves_through_the_canonical_ruin_id(self):
        """`presence_uid` on a ruin names the city the ruin used to be, not the ruin's own id."""
        document = world()
        document['ruins'] = [{'id': 'ruin-surface-city-9-99-dwarf', 'node': 991, 'x': 7, 'z': 7}]
        document['heroes']['people'][1]['presence'] = {'site_kind': 'ruin', 'uid': 'surface-city-9-99-dwarf'}
        block = npc_roster.generate(document)
        legend = next(p for p in block['people'] if p.get('hero_uid', '').startswith('hero-pretender'))
        self.assertEqual(legend['presence_node'], 991)

    def test_an_unresolvable_presence_is_counted_rather_than_guessed(self):
        document = world()
        document['heroes']['people'][0]['presence'] = {'site_kind': 'nest', 'uid': 'nest-that-does-not-exist'}
        block = npc_roster.generate(document)
        person = next(p for p in block['people'] if p.get('hero_uid', '').startswith('hero-sovereign'))
        self.assertNotIn('presence_node', person)
        self.assertEqual(block['summary']['cast_presence_unresolved'], 1)

    def test_a_missing_or_failed_cast_costs_the_cast_not_the_block(self):
        for heroes in (None, {'version': 1, 'status': 'failed', 'error': 'boom'}):
            document = world()
            document['heroes'] = heroes
            block = npc_roster.generate(document)
            self.assertEqual(block['status'], 'ok')
            self.assertEqual(block['summary']['heroes_linked'], 0)


class ReconciliationTests(unittest.TestCase):
    def test_a_longer_roster_than_the_plot_budgeted_truncates_and_is_reported(self):
        document = world()
        document['city_plans']['cities'][0]['plots'] = [plot(0, 'building.guardhouse', 3)]
        block = npc_roster.generate(document)
        posts = [p for p in block['people'] if p['building_id'] == 'building.guardhouse']
        self.assertEqual(len(posts), 3)
        self.assertEqual(block['summary']['roster_mismatches'], 1)

    def test_a_shorter_roster_continues_under_its_last_role_rather_than_inventing_one(self):
        document = world()
        document['city_plans']['cities'][0]['plots'] = [plot(0, 'building.smithy', 4)]
        block = npc_roster.generate(document)
        posts = [p for p in block['people'] if p['building_id'] == 'building.smithy']
        self.assertEqual(len(posts), 4)
        self.assertEqual({p['post'] for p in posts}, {'smith', 'apprentice'})
        self.assertEqual(block['summary']['roster_mismatches'], 1)

    def test_a_building_the_policy_does_not_know_yields_nobody(self):
        document = world()
        document['city_plans']['cities'][0]['plots'] = [plot(0, 'building.invented', 4)]
        block = npc_roster.generate(document)
        self.assertFalse([p for p in block['people'] if p['building_id'] == 'building.invented'])
        self.assertFalse([p for p in block['people']
                          if p['site_uid'] == 'surface-city-0-40-human_heartland' and 'hero_uid' not in p])


class PolicyTests(unittest.TestCase):
    def test_the_post_snapshot_matches_the_live_building_registry(self):
        """The policy copies buildings.json so the package need not import the generator. This
        is the guard that keeps the copy honest; it fails the day the registry moves."""
        registry = json.loads((ROOT / 'Sim/icarus_sim/buildings.json').read_text(encoding='utf-8'))
        live = {}
        for library in ('common', 'rural', 'castle'):
            for block in registry['structure_blocks'][library]['blocks']:
                for structure in block['structures']:
                    roles = [[r['role'], r['target']] for r in (structure.get('staffing') or {}).get('roles', [])]
                    if any(target for _, target in roles):
                        live[structure['id']] = roles
        snapshot = {key: [list(row) for row in value] for key, value in policy.load('posts')['buildings'].items()}
        self.assertEqual(snapshot, live)

    def test_every_expanded_civilization_size_block_resolves_against_the_snapshot(self):
        """Size-block staffing overrides replace the library roster for one entry alone. None
        exists today; this is what notices the first one instead of mislabelling its posts."""
        from icarus_sim import civilization_registry
        snapshot = policy.load('posts')['buildings']
        checked = 0
        for entity_id in civilization_registry.load_registry()['civilization_order']:
            for block in ('small_city', 'medium_city', 'capital_city'):
                for row in civilization_registry.city_plan(entity_id, block)['buildings']:
                    roles = [[r['role'], r['target']] for r in (row.get('staffing') or {}).get('roles', [])]
                    if any(target for _, target in roles):
                        self.assertEqual([list(r) for r in snapshot.get(row['structure_id'], [])], roles,
                                         f'{entity_id}/{block}/{row["structure_id"]} overrides the shared roster')
                        checked += 1
        self.assertGreater(checked, 100)

    def test_every_tagged_verb_is_one_of_the_canonical_ten(self):
        document = policy.load('posts')
        self.assertEqual(len(document['verbs']), 10)
        for role, verbs in document['role_verbs'].items():
            self.assertLessEqual(set(verbs), set(document['verbs']), role)

    def test_every_ranked_giver_building_has_a_roster(self):
        document = policy.load('posts')
        self.assertLessEqual(set(document['giver_rank']), set(document['buildings']))

    def test_broken_policies_fail_loudly(self):
        cases = [
            {'verbs': []},
            {'role_verbs': {'smith': ['invented']}},
            {'giver_rank': ['building.nonexistent']},
            {'caps': {'capital': -1}},
        ]
        for patch in cases:
            document = copy.deepcopy(policy.load('posts'))
            document.update(patch)
            with self.assertRaises(ValueError, msg=str(patch)):
                policy.lint_posts(document)

    def test_a_broken_naming_handover_fails_loudly(self):
        """The sharp case is the last one: race tables reappearing would quietly reinstate the
        parent-race model that gave four peoples human names."""
        cases = (
            {'supersede': None},
            {'supersede': {}},
            {'supersede': {'package': 'heritage'}},
            {'supersede': {'package': 'heritage', 'status': 'pending'}},
            {'races': {'human': {'onsets': ['b']}}},
        )
        for patch in cases:
            document = copy.deepcopy(policy.load('names'))
            document.update(patch)
            with self.assertRaises(ValueError, msg=str(patch)):
                policy.lint_names(document)

    def test_the_shipped_names_policy_carries_no_tables(self):
        document = policy.load('names')
        self.assertNotIn('races', document)
        self.assertEqual(document['supersede']['package'], 'heritage')
        self.assertEqual(document['supersede']['status'], 'complete')


class NameTests(unittest.TestCase):
    def test_names_are_stable_when_an_unrelated_site_changes(self):
        before = {p['uid']: p['name'] for p in npc_roster.generate(world())['people']}
        widened = world()
        widened['city_plans']['cities'][1]['plots'] = [plot(0, 'building.smithy', 2)]
        widened['city_plans']['cities'][1]['status'] = 'complete'
        after = {p['uid']: p['name'] for p in npc_roster.generate(widened)['people']}
        shared = set(before) & set(after)
        self.assertGreater(len(shared), 10)
        self.assertEqual({uid: before[uid] for uid in shared}, {uid: after[uid] for uid in shared})

    def test_each_people_is_named_in_its_own_tongue_and_not_its_parents(self):
        """The defect the genome swap exists to fix.

        Four peoples - tidekin, gnome, hill_dwarf, frosthold_dwarf - had no table of their own
        under the parent-race model and fell through to the human one without comment. Naming
        keyed on civilization id means a people can differ from its parent; this asserts that
        it actually does, rather than that the call merely succeeds.
        """
        draws = [npc_roster.rng(42, f'npc-name-sample-{i}') for i in range(12)]
        by_people = {}
        for civilization_id, parent in (('tidekin', 'elf'), ('elf', 'elf'),
                                        ('hill_dwarf', 'dwarf'), ('dwarf', 'dwarf'),
                                        ('human_desert', 'human'), ('human_cold', 'human')):
            by_people[civilization_id] = [npc_roster.name_for(civilization_id, parent,
                                                              npc_roster.rng(42, f'npc-name-sample-{i}'))
                                          for i in range(12)]
        for child, parent in (('tidekin', 'elf'), ('hill_dwarf', 'dwarf'), ('human_desert', 'human_cold')):
            self.assertNotEqual(by_people[child], by_people[parent],
                                f'{child} is still being named as {parent}')
        for names in by_people.values():
            self.assertTrue(all(name and name[0].isupper() for name in names), names)

    def test_a_roster_repeats_names_the_way_a_population_does(self):
        """Thirteen thousand people drawn uniformly from 88 names left nobody common and
        nobody rare. A roster is where that shows, so the concentration is asserted through
        the call a roster actually makes rather than only on the stock underneath it."""
        draw = npc_roster.rng(42, 'npc-name-concentration')
        counts = {}
        for _ in range(4000):
            name = npc_roster.name_for('human_heartland', 'human', draw)
            counts[name] = counts.get(name, 0) + 1
        shares = sorted((value / 4000 for value in counts.values()), reverse=True)
        self.assertGreater(shares[0], 0.30, shares[:5])
        self.assertGreater(sum(shares[:5]), 0.70, shares[:5])

    def test_a_roster_carries_names_almost_nobody_else_has(self):
        """The tail: without it no name in a world can read as unusual."""
        import heritage
        stock = heritage.name_stock(heritage.resolve('dwarf', 'dwarf'), heritage.lexicon())
        common = {name for name, _ in stock['common']}
        draw = npc_roster.rng(42, 'npc-name-tail')
        drawn = [npc_roster.name_for('dwarf', 'dwarf', draw) for _ in range(4000)]
        outside = [name for name in drawn if name not in common]
        self.assertTrue(outside)
        self.assertLess(len(outside) / len(drawn), 0.06)

    def test_an_unresolvable_people_leaves_its_people_unnamed_rather_than_human(self):
        """The same rule the schema already states for parent_race_id: a guessed parent is a
        wrong tongue, so a name drawn from one is worse than no name at all."""
        broken = world()
        broken['civilizations']['entities'] = []
        broken['settlements']['sites'][0].pop('parent_race_id')
        block = npc_roster.generate(broken)
        resolved = {s['uid']: s['parent_race_id'] for s in block['sites']}
        self.assertIn(None, resolved.values(), 'this world should leave at least one people unresolved')
        staffed = [p for p in block['people'] if p['site_uid'] in resolved]
        self.assertTrue(staffed, 'the sites should still be staffed')
        for person in staffed:
            if person.get('hero_uid'):
                # A member of the cast arrives already named; the genome is not asked.
                self.assertTrue(person['name'], person['uid'])
            elif resolved[person['site_uid']] is None:
                self.assertIsNone(person['name'], person['uid'])
            else:
                self.assertTrue(person['name'], person['uid'])
        self.assertTrue(any(p['name'] is None for p in staffed),
                        'the unresolved site should have left someone unnamed')

    def test_a_person_without_a_civilization_is_not_quietly_named_anyway(self):
        """The silent fallback is the defect; a loud failure is what stops it returning."""
        with self.assertRaises(ValueError):
            npc_roster.name_for(None, 'human', npc_roster.rng(42, 'npc-name-x'))

    def test_a_name_is_drawn_once_per_record_from_its_own_uid(self):
        block = npc_roster.generate(world())
        person = block['people'][0]
        self.assertEqual(person['name'],
                         npc_roster.name_for('human_heartland', 'human',
                                             npc_roster.rng(42, 'npc-name-' + person['uid'])))


class FixtureTests(unittest.TestCase):
    def test_the_pinned_world_yields_the_pinned_roster(self):
        fixture = json.loads((ROOT / 'Fixtures/npc-roster-v1.json').read_text(encoding='utf-8'))
        block = npc_roster.generate(world())
        self.assertEqual(block['policy_revision'], fixture['policy_revision'])
        self.assertEqual(block['summary'], fixture['summary'])
        self.assertEqual([{k: s[k] for k in row} for s, row in zip(block['sites'], fixture['sites'])],
                         fixture['sites'])
        self.assertEqual([{k: p[k] for k in row} for p, row in zip(block['people'], fixture['people'])],
                         fixture['people'])

    def test_the_fixture_pins_no_names(self):
        """A name here would be a tripwire for the naming subsystem this package does not own."""
        fixture = (ROOT / 'Fixtures/npc-roster-v1.json').read_text(encoding='utf-8')
        for name in {p['name'] for p in npc_roster.generate(world())['people'] if 'hero_uid' not in p}:
            self.assertNotIn(f'"{name}"', fixture)


class PackageTests(unittest.TestCase):
    def test_seed_helper_matches_the_generator(self):
        from icarus_sim.terrain_tectonics import child_seed as reference
        for domain in ('npc-name-a', 'npc-name-b', ''):
            self.assertEqual(child_seed(42, domain), reference(42, domain))

    def test_attach_reports_failure_instead_of_raising_and_honours_the_switch(self):
        import os
        self.assertEqual(npc_roster.attach({'config': {'seed': 'not-an-int'}})['status'], 'failed')
        self.assertIn('needs a finished world', npc_roster.attach({})['error'])
        os.environ[npc_roster.ENV_SWITCH] = '0'
        try:
            self.assertIsNone(npc_roster.attach(world()))
        finally:
            del os.environ[npc_roster.ENV_SWITCH]

    def test_a_world_with_no_planned_sites_fails_rather_than_reporting_an_empty_one(self):
        """Silence and emptiness must not look alike: the plans are dropped whenever their
        planner identity moves, and an empty roster would read as a world with no people."""
        self.assertEqual(npc_roster.attach({'config': {'seed': 1}})['status'], 'failed')

    def test_package_reads_only_the_exported_blocks(self):
        for module in Path(npc_roster.__file__).parent.glob('*.py'):
            source = module.read_text(encoding='utf-8')
            for forbidden in ('import icarus_sim', 'from icarus_sim', 'import hero_generator',
                              'from hero_generator', 'import story_web'):
                self.assertNotIn(forbidden, source, f'{module.name} reaches into the generator')

    def test_the_block_satisfies_its_published_schema(self):
        sys.path.insert(0, str(ROOT / 'tests'))
        from schema_subset import validate
        validate(npc_roster.generate(world()),
                 json.loads((ROOT / 'Contracts/schemas/npc-roster.schema.json').read_text(encoding='utf-8')))

    def test_lab_and_core_are_wired_for_the_block(self):
        history = (ROOT / 'Sim/icarus_sim/terrain_history.py').read_text(encoding='utf-8')
        self.assertIn("'npcs'", history.split('STATE_KEYS=')[1].split(')')[0])
        # Both call sites: stage sixteen and the final age of an advance. Missing the second is
        # the trap that makes the block vanish from an aged world with no error.
        self.assertEqual(history.count('            _attach_npcs(result)'), 2)
        html = (ROOT / 'tools/terrain_lab.html').read_text(encoding='utf-8')
        self.assertIn("'npcs'", html.split('const historyStateKeys=')[1].split(';')[0])
        js = (ROOT / 'tools/terrain_world.js').read_text(encoding='utf-8')
        self.assertIn('function renderNpcRoster', js)
        self.assertIn('data.npcs', js)
        self.assertIn('renderNpcRoster()', js.split('function rebuild(')[1])

    def test_every_counter_is_present_even_at_zero(self):
        """A counter that appears only once it is non-zero cannot be told apart from one that
        was never computed, which makes it useless on the day it would have earned its keep."""
        summary = npc_roster.generate(world())['summary']
        for counter in ('unresolved_parent_race', 'unanchored_sites', 'roster_mismatches',
                        'duplicate_site_keys', 'important_capped_out', 'cast_outside_a_planned_site',
                        'cast_located_by_presence', 'cast_presence_unresolved'):
            self.assertIn(counter, summary)
            self.assertIsInstance(summary[counter], int)

    def test_summary_lines_describe_a_block_and_a_failure(self):
        self.assertIn('people across', npc_roster.summary_lines(npc_roster.generate(world()))[0])
        self.assertIn('failed', npc_roster.summary_lines({'status': 'failed', 'error': 'boom'})[0])


if __name__ == '__main__':
    unittest.main()
