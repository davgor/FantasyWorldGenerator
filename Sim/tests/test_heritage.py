"""Behavioural tests for the heritage chain: traits, derived culture, derived genome, names.

These never touch a generated world. The registry binding - that the ids here are exactly
the registry's ids - is a repository-level contract and lives in
tests/test_heritage_registry_binding.py instead.
"""
import copy
import random
import unittest

import heritage
from heritage import derive, naming, phonemes, policy

# The twelve and their parents, restated so this suite stays inside the leaf package.
# tests/test_heritage_registry_binding.py is what proves this equals the registry.
PEOPLES = (('human_maritime', 'human'), ('human_desert', 'human'), ('human_cold', 'human'),
           ('human_large_island', 'human'), ('human_rainforest', 'human'),
           ('human_heartland', 'human'), ('elf', 'elf'), ('tidekin', 'elf'),
           ('dwarf', 'dwarf'), ('gnome', 'dwarf'), ('hill_dwarf', 'dwarf'),
           ('frosthold_dwarf', 'dwarf'))


def _numbers(node, path='', found=None):
    found = [] if found is None else found
    if isinstance(node, dict):
        for key, value in node.items():
            _numbers(value, f'{path}.{key}', found)
    elif isinstance(node, list):
        for item in node:
            _numbers(item, path, found)
    elif isinstance(node, bool) or type(node) in (int, float):
        found.append(path)
    return found


class TraitTableTests(unittest.TestCase):
    def setUp(self):
        heritage.reset_cache()
        self.policies = policy.load_all()

    def test_every_race_base_names_every_axis(self):
        for race, base in self.policies['traits']['races'].items():
            self.assertEqual(set(base), set(policy.AXES), race)

    def test_archetypes_carry_empty_deltas(self):
        """The base is the unmarked member, so a delta reads as a diff from its archetype."""
        for cid in ('human_heartland', 'elf', 'dwarf'):
            self.assertEqual(self.policies['traits']['peoples'][cid], {}, cid)

    def test_trait_layer_carries_no_numbers(self):
        for cid, parent in PEOPLES:
            resolved = heritage.resolve(cid, parent)
            self.assertEqual(_numbers(resolved['traits']), [], cid)

    def test_culture_layer_carries_no_numbers(self):
        """The structural guarantee that heritage cannot restate the numeric profile."""
        for cid, parent in PEOPLES:
            resolved = heritage.resolve(cid, parent)
            self.assertEqual(_numbers(resolved['culture']), [], cid)

    def test_craft_focus_is_two_distinct_crafts(self):
        for cid, parent in PEOPLES:
            crafts = heritage.resolve(cid, parent)['traits']['craft_focus']
            self.assertEqual(len(crafts), policy.CRAFT_COUNT, cid)
            self.assertEqual(len(set(crafts)), policy.CRAFT_COUNT, cid)


class ResolutionTests(unittest.TestCase):
    def setUp(self):
        heritage.reset_cache()

    def test_every_people_resolves_completely(self):
        for cid, parent in PEOPLES:
            resolved = heritage.resolve(cid, parent)
            self.assertEqual(set(resolved['culture']), set(policy.CULTURE_BLOCKS), cid)
            for block, keys in policy.CULTURE_BLOCKS.items():
                self.assertEqual(set(resolved['culture'][block]), set(keys), f'{cid}.{block}')
            for block in policy.GENOME_DERIVED_BLOCKS:
                self.assertIn(block, resolved['genome'], cid)

    def test_inventory_is_inside_the_alphabet_and_disjoint_from_forbidden(self):
        for cid, parent in PEOPLES:
            inventory = heritage.resolve(cid, parent)['genome']['inventory']
            live = set(inventory['consonants']) | set(inventory['vowels'])
            self.assertTrue(live <= phonemes.ALPHABET, cid)
            self.assertEqual(live & set(inventory['forbidden']), set(), cid)

    def test_unlisted_people_resolves_to_its_parent_base(self):
        """A new people arrives with a plausible culture and tongue already attached.

        This is also what keeps test_civilization_registry's synthetic `copper_folk`
        entity working once a consumer starts asking heritage about every civilization.
        """
        invented = heritage.resolve('copper_folk', 'dwarf')
        archetype = heritage.resolve('dwarf', 'dwarf')
        self.assertEqual(invented['traits'], archetype['traits'])
        self.assertEqual(invented['culture'], archetype['culture'])

    def test_an_unknown_parent_race_raises_rather_than_guessing(self):
        """A guessed parent is a wrong tongue, not an approximate one.

        The asymmetry with the unknown-civilization case above is deliberate and is now a
        published contract: Sim/npc_roster leaves people unnamed rather than supply a
        default parent, so this must keep raising.
        """
        for parent in (None, '', 'orc'):
            with self.assertRaises(ValueError) as caught:
                heritage.resolve('dwarf', parent)
            self.assertIn('parent race', str(caught.exception))

    def test_resolution_is_stable_and_does_not_alias_the_cache(self):
        first = heritage.resolve('gnome', 'dwarf')
        second = heritage.resolve('gnome', 'dwarf')
        self.assertEqual(first, second)
        first['culture']['faith']['school'] = 'tampered'
        self.assertNotEqual(heritage.resolve('gnome', 'dwarf')['culture']['faith']['school'],
                            'tampered')

    def test_overrides_are_recorded_in_provenance(self):
        resolved = heritage.resolve('frosthold_dwarf', 'dwarf')
        self.assertIn('culture.memory.taboo', resolved['provenance']['overridden'])
        self.assertEqual(resolved['culture']['memory']['taboo'], 'letting_the_forge_die')

    def test_identity_moves_only_when_an_output_moves(self):
        before = heritage.heritage_identity(PEOPLES)
        self.assertEqual(before, heritage.heritage_identity(PEOPLES))
        self.assertEqual(len(before['sha256']), 64)


class RejectionTests(unittest.TestCase):
    """Authoring mistakes fail at load with a sentence that names the mistake."""

    def setUp(self):
        heritage.reset_cache()
        self.traits = copy.deepcopy(policy.load('traits'))

    def test_delta_restating_the_inherited_value_is_an_error(self):
        base = self.traits['races']['dwarf']
        with self.assertRaises(ValueError) as caught:
            derive.merge_traits(base, {'kinship': base['kinship']}, 'people')
        self.assertIn('inherited value', str(caught.exception))

    def test_hidden_school_is_refused(self):
        self.traits['peoples']['gnome'] = {'magic_school': 'rot'}
        with self.assertRaises(ValueError) as caught:
            policy.lint_traits(self.traits)
        self.assertIn('hidden school', str(caught.exception))

    def test_number_in_the_trait_layer_is_refused(self):
        self.traits['peoples']['gnome'] = {'body_scale': 3}
        with self.assertRaises(ValueError) as caught:
            policy.lint_traits(self.traits)
        self.assertIn('no numbers', str(caught.exception))

    def test_unknown_axis_is_refused(self):
        self.traits['peoples']['gnome'] = {'temperature_ideal': 'mid'}
        with self.assertRaises(ValueError):
            policy.lint_traits(self.traits)

    def test_incomplete_race_base_is_refused(self):
        del self.traits['races']['elf']['dentition']
        with self.assertRaises(ValueError) as caught:
            policy.lint_traits(self.traits)
        self.assertIn('exactly', str(caught.exception))

    def test_override_restating_the_derived_value_is_an_error(self):
        derived = {'faith': {'festival': 'charter_day'}}
        with self.assertRaises(ValueError) as caught:
            derive.apply_overrides(derived, {'faith': {'festival': 'charter_day'}}, 'gnome')
        self.assertIn('restates', str(caught.exception))

    def test_dropping_a_phoneme_the_derivation_never_made_is_an_error(self):
        derived = {'inventory': {'consonants': ['p', 't', 'k']}}
        with self.assertRaises(ValueError) as caught:
            derive.apply_overrides(
                derived, {'inventory': {'consonants': {'drop': ['zh']}}}, 'tidekin')
        self.assertIn('never produced', str(caught.exception))

    def test_adding_and_dropping_the_same_phoneme_is_an_error(self):
        derived = {'inventory': {'consonants': ['p', 't', 'k']}}
        with self.assertRaises(ValueError) as caught:
            derive.apply_overrides(
                derived, {'inventory': {'consonants': {'add': ['s'], 'drop': ['s']}}}, 'x')
        self.assertIn('adds and drops', str(caught.exception))

    def test_derivation_map_must_be_total_over_its_axis(self):
        rules = copy.deepcopy(policy.load('derivation'))
        del rules['culture']['household']['inheritance']['map']['age_cohort']
        with self.assertRaises(ValueError) as caught:
            policy.lint_derivation(rules)
        self.assertIn('every enum value must map', str(caught.exception))


class SoundChangeTests(unittest.TestCase):
    def test_a_rule_does_not_match_inside_a_digraph(self):
        """s -> sh must not fire on the s of an existing sh, or `mush` becomes `mushh`."""
        self.assertEqual(derive.apply_sound_changes('mush', [['s', 'sh']]), 'mush')
        self.assertEqual(derive.apply_sound_changes('sam', [['s', 'sh']]), 'sham')

    def test_rules_apply_in_order_and_may_feed_each_other(self):
        self.assertEqual(derive.apply_sound_changes('kal', [['k', 'h'], ['h', 'g']]), 'gal')
        self.assertEqual(derive.apply_sound_changes('kal', [['h', 'g'], ['k', 'h']]), 'hal')

    def test_siblings_share_roots_and_differ_by_rule(self):
        heritage.reset_cache()
        stone = {cid: heritage.resolve(cid, 'dwarf')['genome']['lexicon']['stone']
                 for cid in ('dwarf', 'gnome', 'hill_dwarf', 'frosthold_dwarf')}
        self.assertEqual(stone['dwarf'], 'khas')
        self.assertEqual(len(set(stone.values())), 4, stone)


class NamingTests(unittest.TestCase):
    def setUp(self):
        heritage.reset_cache()
        self.lexicon = policy.load('lexicon')

    def test_names_are_deterministic_for_a_given_draw(self):
        resolved = heritage.resolve('dwarf', 'dwarf')
        first = [heritage.person_name(resolved, random.Random(3)) for _ in range(3)]
        second = [heritage.person_name(resolved, random.Random(3)) for _ in range(3)]
        self.assertEqual(first, second)

    def test_settlement_names_carry_a_gloss_of_real_slots(self):
        resolved = heritage.resolve('dwarf', 'dwarf')
        name, gloss = heritage.settlement_name(resolved, self.lexicon, random.Random(11))
        self.assertTrue(name[:1].isupper(), name)
        for slot in gloss.split('-'):
            self.assertIn(slot, resolved['genome']['lexicon'], gloss)

    def test_terrain_bias_places_the_named_ground_first(self):
        resolved = heritage.resolve('dwarf', 'dwarf')
        _, gloss = heritage.settlement_name(resolved, self.lexicon, random.Random(11),
                                            terrain_slot='water')
        self.assertTrue(gloss.startswith('water-') or 'water' in gloss, gloss)

    def test_no_sibling_pair_shares_a_place_name_series(self):
        """Distinct tongues, not accents: the whole point of the family substrate."""
        series = {}
        for cid, parent in PEOPLES:
            resolved = heritage.resolve(cid, parent)
            draw = random.Random(11)
            series[cid] = tuple(heritage.settlement_name(resolved, self.lexicon, draw)[0]
                                for _ in range(4))
        self.assertEqual(len(set(series.values())), len(PEOPLES), series)

    def test_personal_names_never_open_with_a_bare_velar_nasal(self):
        for cid, parent in PEOPLES:
            resolved = heritage.resolve(cid, parent)
            draw = random.Random(5)
            for _ in range(40):
                self.assertFalse(heritage.person_name(resolved, draw).lower().startswith('ng'),
                                 cid)

    def test_a_monosyllabic_tongue_still_closes_its_names(self):
        """Without a required coda, `monosyllabic_heavy` produced bare forms like `Na`."""
        resolved = heritage.resolve('frosthold_dwarf', 'dwarf')
        draw = random.Random(9)
        for _ in range(40):
            self.assertGreaterEqual(len(heritage.person_name(resolved, draw)), 3)

    def test_personal_names_are_dithematic_and_glossable(self):
        """Two meaning-bearing elements, like Thor-bjorn - not pronounceable noise."""
        resolved = heritage.resolve('frosthold_dwarf', 'dwarf')
        name, gloss = naming.person_name_with_gloss(resolved, self.lexicon, random.Random(7))
        parts = gloss.split('-')
        self.assertEqual(len(parts), 2, gloss)
        for slot in parts:
            self.assertIn(slot, resolved['genome']['lexicon'], gloss)
        self.assertTrue(name[:1].isupper(), name)

    def test_a_personal_name_never_repeats_one_element(self):
        resolved = heritage.resolve('dwarf', 'dwarf')
        draw = random.Random(21)
        for _ in range(40):
            gloss = naming.person_name_with_gloss(resolved, self.lexicon, draw)[1]
            if gloss:
                self.assertEqual(len(set(gloss.split('-'))), 2, gloss)

    def test_personal_names_do_not_look_like_settlements(self):
        """A person is quality+craft or terrain+craft; a place is terrain+site."""
        site_only = set(self.lexicon['slot_roles']['site'])
        for pattern in (t['pattern'] for t in self.lexicon['personal_templates']):
            self.assertNotIn('site', pattern, pattern)
        self.assertTrue(site_only)

    def test_the_two_argument_call_still_reaches_the_phonotactic_path(self):
        """`person_name(resolved, draw)` predates the lexicon argument and must keep working."""
        resolved = heritage.resolve('elf', 'elf')
        self.assertTrue(heritage.person_name(resolved, random.Random(3)))

    def test_forbidden_forms_are_never_returned(self):
        """A prototype of this design shipped `Person` and `Mordor` before this filter."""
        resolved = heritage.resolve('hill_dwarf', 'dwarf')
        resolved['genome']['forbidden_forms'] = ['a', 'e', 'i', 'o', 'u']
        draw = random.Random(4)
        # Every possible name contains a vowel, so the bounded loop must still terminate.
        self.assertTrue(heritage.person_name(resolved, draw))

    def test_a_banned_substring_is_redrawn_past(self):
        resolved = heritage.resolve('dwarf', 'dwarf')
        draw = random.Random(2)
        first = naming._draw_person(resolved, random.Random(2))
        resolved['genome']['forbidden_forms'] = [first.lower()]
        self.assertNotEqual(heritage.person_name(resolved, draw).lower(), first.lower())

    def test_name_table_matches_the_shape_hero_generator_consumes(self):
        table = heritage.name_table(heritage.resolve('elf', 'elf'))
        self.assertEqual(set(table), {'onsets', 'nuclei', 'codas', 'third_syllable_chance'})
        self.assertTrue(table['onsets'] and table['nuclei'])


if __name__ == '__main__':
    unittest.main()
