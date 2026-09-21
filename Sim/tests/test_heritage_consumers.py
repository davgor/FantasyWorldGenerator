"""The consumers heritage now feeds: settlement names, hero names, realms, the report.

None of these build a world. Settlement naming is a pure function of (seed, nodes, points,
peoples), hero naming of (person, draw), so each is exercised directly with synthetic input
rather than by paying 70-120 s for a generated world to look at its names.
"""
import unittest

import heritage
from hero_generator import history as hero_history
from hero_generator.naming import heritage_name
from hero_generator.seeds import rng
from icarus_sim.civilization_registry import entity_rules
from icarus_sim.terrain_civilizations import civilization_report, heritage_of
from icarus_sim.terrain_profiles import civilization_ids
from icarus_sim.terrain_settlements import _settlement_names
from key_locations.core import naming as key_location_naming
from npc_roster import sites as npc_roster_sites

NODES = [41, 7, 19, 88, 3, 56]
POINTS = {n: (n * 13 % 97, n * 7 % 89) for n in NODES}
PEOPLES = ['dwarf', 'elf', 'human_maritime', 'frosthold_dwarf', 'gnome', 'tidekin']


class SettlementNamingTests(unittest.TestCase):
    def setUp(self):
        heritage.reset_cache()

    def test_names_are_deterministic_for_a_seed(self):
        first = _settlement_names(1234, NODES, POINTS, PEOPLES)
        second = _settlement_names(1234, NODES, POINTS, PEOPLES)
        self.assertEqual(first, second)

    def test_founding_a_new_city_renames_nothing(self):
        """The defect in `names[k%24]`: one earlier founding renamed every later city."""
        before = _settlement_names(1234, NODES, POINTS, PEOPLES)
        points = dict(POINTS)
        points[99] = (5, 5)
        after = _settlement_names(1234, NODES + [99], points, PEOPLES + ['dwarf'])
        for node in NODES:
            self.assertEqual(before[node], after[node], node)

    def test_a_name_does_not_depend_on_founding_order(self):
        """Naming runs in node order, so collision redraws cannot depend on the loop."""
        forward = _settlement_names(1234, NODES, POINTS, PEOPLES)
        order = list(reversed(range(len(NODES))))
        reversed_names = _settlement_names(1234, [NODES[i] for i in order], POINTS,
                                           [PEOPLES[i] for i in order])
        self.assertEqual(forward, reversed_names)

    def test_every_name_glosses_to_roots_of_its_own_language(self):
        named = _settlement_names(1234, NODES, POINTS, PEOPLES)
        for node, profile in zip(NODES, PEOPLES):
            resolved = heritage.resolve(profile, entity_rules(profile)['parent_race_id'])
            name, gloss = named[node]
            self.assertTrue(name and name[:1].isupper(), name)
            for slot in gloss.split('-'):
                self.assertIn(slot, resolved['genome']['lexicon'], f'{profile}: {gloss}')

    def test_no_placeholder_english_survives(self):
        named = _settlement_names(1234, NODES, POINTS, PEOPLES)
        for name, _ in named.values():
            self.assertNotIn(' City', name)
            self.assertNotIn('Alder', name)

    def test_names_within_one_world_are_unique(self):
        nodes = list(range(40))
        points = {n: (n * 13 % 97, n * 7 % 89) for n in nodes}
        peoples = ['dwarf'] * 40
        named = _settlement_names(99, nodes, points, peoples)
        values = [n for n, _ in named.values()]
        self.assertEqual(len(set(values)), len(values), 'collision redraw failed')


class RetiredCitySuffixTests(unittest.TestCase):
    """The ` City` disambiguator is retired, and no reader may still answer to it.

    Settlement naming moved off `_settlement_names`' round-robin over twelve English
    nature words plus the literal ` City` and onto `heritage.settlement_name`. The
    producer moved; five readers did not, and two of those were tests making opposite
    claims about the same strings -- `tests/test_terrain_humans.py` asserted every
    settlement name *ends with* ` City`, while `test_no_placeholder_english_survives`
    above asserts none *contains* it. Only the first failed, so the contradiction was
    invisible. Three more strip a suffix that is never there and read to the next
    person as live disambiguation.

    Which convention is live is a measurement, not an opinion, so the first test here
    takes it over a spread of seeds rather than asserting it of one.
    """

    def setUp(self):
        heritage.reset_cache()

    def test_no_seed_produces_the_retired_suffix(self):
        for seed in (1, 42, 99, 1234, 20260921):
            for node, (name, _gloss) in _settlement_names(seed, NODES, POINTS, PEOPLES).items():
                self.assertFalse(name.endswith(' City'), f'seed {seed} node {node}: {name!r}')

    def test_key_locations_does_not_strip_a_suffix_the_generator_never_writes(self):
        """A place genuinely called `Gulf City` reaches a key location's name intact.

        `hero_generator.history.short_name` and `npc_roster.sites._short_name` still cut
        those characters out. Both are the identity on any generated world and both are
        exercised only by synthetic worlds that name their cities in the retired
        convention, so removing them is a fixture change rather than a line change; it is
        named as unfinished on board/backlog/CONTENT-CITY-SUFFIX-DEAD-READERS.md rather than
        asserted here, because an assertion this file cannot make pass is not a pin.
        """
        self.assertEqual(key_location_naming.short_name('Gulf City'), 'Gulf City')
        self.assertEqual(hero_history.short_name('Gulf City'), 'Gulf')
        self.assertEqual(npc_roster_sites._short_name({'name': 'Gulf City'}), 'Gulf')

    def test_the_helpers_still_do_the_jobs_that_are_theirs(self):
        self.assertIsNone(key_location_naming.short_name(None))
        self.assertEqual(key_location_naming.short_name('Ashen wyrm'), 'Ashen wyrm')
        self.assertEqual(npc_roster_sites._short_name({'name': 'Bargdorn (Age 2)'}), 'Bargdorn')


class HeroNamingTests(unittest.TestCase):
    def setUp(self):
        heritage.reset_cache()

    def _person(self, cid, race):
        return {'uid': 'p-' + cid, 'civilization_id': cid, 'race_id': race}

    def test_two_peoples_of_one_race_no_longer_share_a_name_pool(self):
        """Keyed on the parent race, a desert human and a cold human drew from one table."""
        desert = [heritage_name(self._person('human_desert', 'human'), rng(42, 'n')) for _ in range(6)]
        cold = [heritage_name(self._person('human_cold', 'human'), rng(42, 'n')) for _ in range(6)]
        self.assertNotEqual(desert, cold)

    def test_the_four_peoples_that_silently_got_human_names_now_have_their_own(self):
        human = [heritage_name(self._person('human_heartland', 'human'), rng(7, 'n')) for _ in range(6)]
        for cid, race in (('tidekin', 'elf'), ('gnome', 'dwarf'),
                          ('hill_dwarf', 'dwarf'), ('frosthold_dwarf', 'dwarf')):
            own = [heritage_name(self._person(cid, race), rng(7, 'n')) for _ in range(6)]
            self.assertNotEqual(own, human, cid)

    def test_a_record_without_a_civilization_raises_rather_than_falling_back(self):
        """The silent human fallback is the defect; a loud failure is the fix."""
        with self.assertRaises(ValueError) as caught:
            heritage_name({'uid': 'p', 'race_id': 'elf'}, rng(1, 'n'))
        self.assertIn('civilization_id', str(caught.exception))

    def test_every_registry_civilization_can_name_a_person(self):
        for cid in civilization_ids():
            person = self._person(cid, entity_rules(cid)['parent_race_id'])
            self.assertTrue(heritage_name(person, rng(3, 'n')), cid)


class RealmNamingTests(unittest.TestCase):
    def test_a_realm_is_its_seat_plus_the_realm_morpheme(self):
        heritage.reset_cache()
        resolved = heritage.resolve('dwarf', 'dwarf')
        self.assertEqual(heritage.realm_name(resolved, 'Bargdorn'), 'Bargdornrik')

    def test_the_seam_follows_the_tongue_on_geminates(self):
        """Whether the doubled letter survives is the language's call, not the joiner's."""
        gnome = heritage.resolve('gnome', 'dwarf')
        dwarf = heritage.resolve('dwarf', 'dwarf')
        self.assertFalse(gnome['genome']['phonotactics']['geminates'])
        self.assertTrue(dwarf['genome']['phonotactics']['geminates'])
        self.assertEqual(heritage.realm_name(gnome, 'Bor'), 'Borik')
        self.assertEqual(heritage.realm_name(dwarf, 'Bor'), 'Borrik')

    def test_each_family_has_its_own_realm_morpheme(self):
        names = {parent: heritage.realm_name(heritage.resolve(cid, parent), 'Ador')
                 for cid, parent in (('dwarf', 'dwarf'), ('elf', 'elf'),
                                     ('human_heartland', 'human'))}
        self.assertEqual(len(set(names.values())), 3, names)


class ReportTests(unittest.TestCase):
    def setUp(self):
        heritage.reset_cache()
        self.report = civilization_report([])

    def test_the_block_declares_version_three(self):
        self.assertEqual(self.report['version'], 3)

    def test_every_entity_carries_its_heritage(self):
        for entity in self.report['entities']:
            self.assertEqual(set(entity['heritage']),
                             {'traits', 'culture', 'genome', 'provenance'}, entity['id'])

    def test_the_report_records_which_heritage_tables_produced_it(self):
        identity = self.report['heritage']
        self.assertEqual(len(identity['sha256']), 64)
        self.assertTrue(all(v >= 1 for v in identity['revision'].values()))

    def test_heritage_of_covers_every_civilization(self):
        for cid in civilization_ids():
            self.assertIn('culture', heritage_of(cid))


if __name__ == '__main__':
    unittest.main()
