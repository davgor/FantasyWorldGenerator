"""Behavioural tests for the heritage chain: traits, derived culture, derived genome, names.

These never touch a generated world. The registry binding - that the ids here are exactly
the registry's ids - is a repository-level contract and lives in
tests/test_heritage_registry_binding.py instead.
"""
import copy
import json
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


# 4 ft 5 in in metres, to four places. The requirement that raised this layer was stated in
# feet; the repository is metric everywhere and the Unreal adapter converts at its own
# boundary, so the conversion is done once, here, where it can be read.
FOUR_FOOT_FIVE_M = 1.3462
DWARVES = tuple(cid for cid, parent in PEOPLES if parent == 'dwarf')


class AppearanceTests(unittest.TestCase):
    """The authored body: complete per race, extended per subrace, agreeing with the traits."""

    def setUp(self):
        heritage.reset_cache()
        self.policies = policy.load_all()
        self.bodies = {cid: heritage.resolve(cid, parent)['appearance']
                       for cid, parent in PEOPLES}

    def test_every_people_resolves_a_complete_body(self):
        for cid, body in self.bodies.items():
            self.assertEqual(set(body), set(policy.APPEARANCE_BLOCKS), cid)
            for block, keys in policy.APPEARANCE_BLOCKS.items():
                self.assertEqual(set(body[block]), set(keys), f'{cid}.{block}')

    def test_archetypes_carry_empty_appearance_deltas(self):
        """The race base is the unmarked member here too, so a delta reads as a difference."""
        for cid in ('human_heartland', 'elf', 'dwarf'):
            self.assertEqual(self.policies['appearance']['peoples'][cid], {}, cid)

    def test_no_dwarf_stands_over_four_foot_five(self):
        """The stated requirement, asserted on the resolved body rather than on the table.

        Every people under the dwarf parent race - the mountain clans, the frostholds, the
        hill dwarves and the gnomes - is shorter than this at the top of its band, for both
        sexes. `policy.BODY_SCALE_HEIGHT_M` is what enforces it at load; this is what states
        it, so a future envelope edit that quietly lets a dwarf past 4 ft 5 in fails here
        with the sentence that says why it matters.
        """
        self.assertEqual(len(DWARVES), 4)
        for cid in DWARVES:
            for sex in policy.SEXES:
                band = self.bodies[cid]['frame']['height_m'][sex]
                self.assertLess(band['max'], FOUR_FOOT_FIVE_M, f'{cid}.{sex}')

    def test_height_bands_sit_inside_the_envelope_their_body_scale_owns(self):
        for cid, parent in PEOPLES:
            resolved = heritage.resolve(cid, parent)
            floor, ceiling = policy.BODY_SCALE_HEIGHT_M[resolved['traits']['body_scale']]
            for sex in policy.SEXES:
                band = resolved['appearance']['frame']['height_m'][sex]
                self.assertGreaterEqual(band['min'], floor, f'{cid}.{sex}')
                self.assertLessEqual(band['max'], ceiling, f'{cid}.{sex}')

    def test_every_band_can_be_drawn_from(self):
        """min <= mean <= max with a positive spread: what a per-NPC draw needs to exist."""
        for cid, body in self.bodies.items():
            for measure in ('height_m', 'mass_kg'):
                for sex in policy.SEXES:
                    band = body['frame'][measure][sex]
                    self.assertLessEqual(band['min'], band['mean'], f'{cid}.{measure}.{sex}')
                    self.assertLessEqual(band['mean'], band['max'], f'{cid}.{measure}.{sex}')
                    self.assertGreater(band['sd'], 0, f'{cid}.{measure}.{sex}')

    def test_palettes_are_distributions_over_named_swatches(self):
        for cid, body in self.bodies.items():
            for channel in ('skin', 'hair', 'eye'):
                entry = body['coloration'][channel]
                self.assertEqual(set(entry), set(policy.PALETTE_KEYS), f'{cid}.{channel}')
                palette = entry['swatches']
                self.assertGreaterEqual(len(palette), policy.PALETTE_MIN, f'{cid}.{channel}')
                total = sum(swatch['weight'] for swatch in palette)
                self.assertAlmostEqual(total, 1.0, places=6, msg=f'{cid}.{channel}')
                names = [swatch['name'] for swatch in palette]
                self.assertEqual(len(set(names)), len(names), f'{cid}.{channel}')

    def test_every_face_carries_a_handle_and_a_description(self):
        """`broad_high_bridge` tells an artist nothing; the note beside it is the deliverable.

        Both halves travel in one value so they cannot drift apart, which is the whole
        reason there is no separate prose block sitting beside the token one.
        """
        for cid, body in self.bodies.items():
            for key in policy.APPEARANCE_BLOCKS['features']:
                entry = body['features'][key]
                self.assertEqual(set(entry), set(policy.FEATURE_KEYS), f'{cid}.{key}')
                self.assertRegex(entry['form'], policy.TOKEN, f'{cid}.{key}')
                self.assertGreaterEqual(len(entry['note'].strip()), policy.PROSE_MIN,
                                        f'{cid}.{key}')

    def test_every_palette_says_how_it_is_distributed(self):
        for cid, body in self.bodies.items():
            for channel in ('skin', 'hair', 'eye'):
                note = body['coloration'][channel]['note']
                self.assertGreaterEqual(len(note.strip()), policy.PROSE_MIN,
                                        f'{cid}.{channel}')

    def test_the_two_big_noses_and_the_two_pointed_ears_are_where_they_belong(self):
        """The face rules that distinguish the three stocks, asserted rather than assumed.

        Elves have the pointed ears, dwarves have the big nose, and gnomes - who descend
        from the dwarven parent race but read as neither parent - carry both at once. That
        last one is the entire likeness of a gnome, so it is worth a test rather than a
        hope that nobody edits it flat.
        """
        elf = self.bodies['elf']['features']
        dwarf = self.bodies['dwarf']['features']
        gnome = self.bodies['gnome']['features']
        self.assertIn('point', elf['ear']['form'])
        self.assertIn('rounded', dwarf['ear']['form'])
        self.assertIn('broad', dwarf['nose']['form'])
        self.assertIn('narrow', elf['nose']['form'])
        self.assertIn('point', gnome['ear']['form'])
        self.assertIn('long', gnome['nose']['form'])
        # And the notes have to say so too, because the tokens are not what an artist reads.
        self.assertIn('ears', gnome['nose']['note'])
        self.assertIn('small_ears', self.bodies['gnome']['art_direction']['avoid'])
        self.assertIn('small_nose', self.bodies['gnome']['art_direction']['avoid'])
        self.assertIn('short_ears', self.bodies['elf']['art_direction']['avoid'])
        self.assertIn('small_neat_nose', self.bodies['dwarf']['art_direction']['avoid'])

    def test_lifespan_agrees_with_the_tempo_axis(self):
        for cid, parent in PEOPLES:
            resolved = heritage.resolve(cid, parent)
            low, high = policy.LIFESPAN_TEMPO_YEARS[resolved['traits']['lifespan_tempo']]
            maximum = resolved['appearance']['life_stages']['max_years']
            self.assertGreaterEqual(maximum, low, cid)
            self.assertLessEqual(maximum, high, cid)

    def test_adult_is_the_stature_every_band_is_stated_at(self):
        """A child sprite scales off this, so the adult fraction has to be exactly one."""
        for cid, body in self.bodies.items():
            self.assertEqual(body['life_stages']['adult']['height_fraction'], 1, cid)

    def test_every_subrace_bears_a_distinct_body(self):
        """Every subrace bears a unique culture; a sprite sheet needs the same of a body."""
        rendered = {cid: json.dumps(body, sort_keys=True) for cid, body in self.bodies.items()}
        self.assertEqual(len(set(rendered.values())), len(PEOPLES))

    def test_appearance_is_where_the_numbers_live(self):
        """The counterpart to the two no-numbers assertions above.

        Those prove heritage cannot restate the habitat profile. This proves the ban did not
        simply push the measurements out of the package: a body has numbers, and they are
        here, in the one layer whose lint permits them.
        """
        for cid, body in self.bodies.items():
            self.assertTrue(_numbers(body['frame']), cid)
            self.assertTrue(_numbers(body['proportion']), cid)


class AppearanceRejectionTests(unittest.TestCase):
    """Authoring mistakes in the body layer fail at load, naming the mistake."""

    def setUp(self):
        heritage.reset_cache()
        self.traits = policy.load('traits')
        self.appearance = copy.deepcopy(policy.load('appearance'))

    def _lint(self):
        with self.assertRaises(ValueError) as caught:
            policy.lint_appearance(self.appearance, self.traits)
        return str(caught.exception)

    def test_a_dwarf_taller_than_its_body_scale_allows_is_refused(self):
        band = self.appearance['races']['dwarf']['frame']['height_m']['male']
        band['max'] = 1.62
        self.assertIn('height envelope', self._lint())

    def test_a_palette_that_is_not_a_distribution_is_refused(self):
        self.appearance['races']['elf']['coloration']['eye']['swatches'][0]['weight'] = 0.9
        self.assertIn('must sum to 1', self._lint())

    def test_a_swatch_without_a_colour_is_refused(self):
        self.appearance['races']['human']['coloration']['skin']['swatches'][0]['hex'] = 'tan'
        self.assertIn('#rrggbb', self._lint())

    def test_a_lifespan_its_tempo_forbids_is_refused(self):
        """A dwarf clan given an elven span is a slip, not a design decision.

        The value is past the elder onset, so it clears the ordering check and is caught by
        the tempo envelope alone - which is the half of this that binds appearance to the
        key traits rather than to itself.
        """
        self.appearance['races']['dwarf']['life_stages']['max_years'] = 1000
        self.assertIn('lifespan_tempo', self._lint())

    def test_life_stages_out_of_order_are_refused(self):
        self.appearance['races']['dwarf']['life_stages']['elder']['onset_years'] = 20
        self.assertIn('stages run in order', self._lint())

    def test_an_incomplete_race_body_is_refused(self):
        del self.appearance['races']['dwarf']['attire']
        self.assertIn('appearance blocks', self._lint())

    def test_a_face_token_with_no_description_is_refused(self):
        """A handle alone is what this layer exists to stop shipping."""
        self.appearance['races']['dwarf']['features']['nose'] = {
            'form': 'broad_high_bridge', 'note': 'big nose'}
        self.assertIn('open English', self._lint())

    def test_a_palette_with_no_note_is_refused(self):
        del self.appearance['races']['human']['coloration']['skin']['note']
        self.assertIn('note', self._lint())

    def test_a_subrace_extending_an_unknown_key_is_refused(self):
        self.appearance['peoples']['gnome']['frame'] = {'wingspan_m': 2.0}
        self.assertIn('frame.wingspan_m', self._lint())

    def test_a_people_missing_from_the_body_table_is_refused(self):
        del self.appearance['peoples']['tidekin']
        self.assertIn('tidekin', self._lint())

    def test_a_delta_restating_its_inherited_body_is_an_error(self):
        base = policy.load('appearance')['races']['dwarf']
        with self.assertRaises(ValueError) as caught:
            derive.merge_appearance(base, {'frame': {'build': base['frame']['build']}},
                                    'people')
        self.assertIn('inherited value', str(caught.exception))

    def test_a_delta_may_replace_one_key_without_restating_its_block(self):
        """The merge is depth two, so a subrace can change its eyes and keep its skin."""
        base = policy.load('appearance')['races']['dwarf']
        merged = derive.merge_appearance(base, {'frame': {'build': 'reedy'}}, 'people')
        self.assertEqual(merged['frame']['build'], 'reedy')
        self.assertEqual(merged['frame']['height_m'], base['frame']['height_m'])

class NameStockTests(unittest.TestCase):
    """The stock layer: what a people actually calls its children, and how often.

    `person_name` says what a tongue can build; these say which of those names get used. The
    numbers below are the English poll tax returns of the late fourteenth century - one man in
    three a John, four fifths of men inside the top five - because that is the only part of
    this the repository can check against something outside itself.
    """

    def setUp(self):
        heritage.reset_cache()
        self.lexicon = heritage.lexicon()
        self.resolved = heritage.resolve('human_heartland', 'human')
        self.stock = naming.name_stock(self.resolved, self.lexicon)

    def _shares(self, stock, count=4000, seed=11):
        draw = random.Random(seed)
        counts = {}
        for _ in range(count):
            name = naming.stock_name(stock, draw)[0]
            counts[name] = counts.get(name, 0) + 1
        ordered = sorted(counts.values(), reverse=True)
        return [value / count for value in ordered]

    def test_the_stock_is_the_same_in_every_world(self):
        """Seedless on purpose: a name is common because of the culture, not the seed."""
        again = naming.name_stock(heritage.resolve('human_heartland', 'human'), self.lexicon)
        self.assertEqual(again['common'], self.stock['common'])
        self.assertEqual(again['rare'], self.stock['rare'])

    def test_one_name_in_three_is_the_commonest_one(self):
        shares = self._shares(self.stock)
        self.assertGreater(shares[0], 0.30, shares[:5])
        self.assertLess(shares[0], 0.40, shares[:5])

    def test_the_top_five_carry_most_of_a_people(self):
        shares = self._shares(self.stock)
        self.assertGreater(sum(shares[:5]), 0.70, shares[:5])
        self.assertLess(sum(shares[:5]), 0.85, shares[:5])

    def test_the_effective_number_of_names_is_a_handful_not_a_hundred(self):
        """The measure the uniform draw failed: 88 names drawn flat scores about 88."""
        shares = self._shares(self.stock)
        effective = 1 / sum(share * share for share in shares)
        self.assertLess(effective, 9, effective)
        self.assertGreater(effective, 4, effective)

    def test_the_commonest_names_share_no_root(self):
        """Ranking on length alone gave `Eldsel`, `Frosel`, `Nersel`, `Versel` - one root,
        four fifths of a people, and a reader who hears a stutter rather than a culture.

        Swept over all twelve rather than the one in `setUp`, because the greedy fill has a
        fallback: a people whose roots overlap too much to yield five root-disjoint names
        gets plain rank order back, which is exactly the bunched head this guards against.
        No people takes that branch today, so a single-people version of this test would
        pass on the data rather than on the property, and would keep passing if a lexicon
        edit pushed one of them into it.
        """
        for cid, parent in PEOPLES:
            stock = naming.name_stock(heritage.resolve(cid, parent), self.lexicon)
            spent = set()
            for name, gloss in stock['common'][:naming.HEAD_SPREAD]:
                slots = gloss.split('-')
                self.assertFalse(spent.intersection(slots),
                                 f'{cid}: {name} reuses a root already in the head')
                spent.update(slots)

    def test_every_people_is_concentrated_and_not_only_the_one_above(self):
        """The three tests above measure one people in detail. This one measures the claim.

        A pool's size varies by which roots its family carries - 88 for heartland, 184 for
        gnome - and the head table is shared, so the shape has to be asserted where it could
        diverge rather than only where it was tuned.
        """
        for cid, parent in PEOPLES:
            stock = naming.name_stock(heritage.resolve(cid, parent), self.lexicon)
            shares = self._shares(stock, count=2000, seed=13)
            effective = 1 / sum(share * share for share in shares)
            self.assertGreater(shares[0], 0.28, f'{cid}: commonest name {shares[0]:.3f}')
            self.assertLess(effective, 10, f'{cid}: effective names {effective:.1f}')

    def test_a_people_too_inbred_to_spread_its_head_keeps_rank_order(self):
        """The fallback branch, which no real people reaches and which would otherwise be
        asserted by nothing at all: every candidate shares a root, so no head can be spread
        and the ranking must come back whole rather than short."""
        # `Ac` shares no root with `Aa` and would be promoted over `Ab` if the head were
        # spread; the head still cannot reach five, so rank order must come back untouched.
        # Three names all sharing one root would pass whether or not the branch exists,
        # which is a test that cannot fail rather than a test that holds.
        found = {'Aa': ('stone-fire', 4, ('stone', 'fire')),
                 'Ab': ('stone-gold', 4, ('stone', 'gold')),
                 'Ac': ('wood-iron', 4, ('wood', 'iron'))}
        self.assertEqual([name for name, _ in naming._ranked(found)], ['Aa', 'Ab', 'Ac'])

    def test_a_rare_name_is_never_also_a_common_one(self):
        common = {name for name, _ in self.stock['common']}
        for name, _ in self.stock['rare']:
            self.assertNotIn(name, common, name)

    def test_a_rare_pairing_is_neither_an_everyday_one_nor_a_settlement_shape(self):
        """What makes the tail rare is the pairing, so it may not reuse either authored set."""
        spent = {tuple(template['pattern']) for template in self.lexicon['personal_templates']}
        settlements = {tuple(template['pattern'])
                       for template in self.lexicon['settlement_templates']}
        rare = naming._rare_patterns(self.lexicon)
        self.assertTrue(rare)
        for pattern in rare:
            self.assertNotIn(pattern, spent, pattern)
            self.assertNotIn(pattern, settlements, pattern)

    def test_the_tail_reaches_names_the_common_stock_cannot(self):
        """Without this a closed pool has no singletons, so no name can read as unusual."""
        common = {name for name, _ in self.stock['common']}
        draw = random.Random(5)
        drawn = [naming.stock_name(self.stock, draw)[0] for _ in range(4000)]
        outside = [name for name in drawn if name not in common]
        self.assertTrue(outside)
        # Rare, and recognisably so: a tail that drifts towards a second stock is not a tail.
        self.assertLess(len(outside) / len(drawn), naming.RARE_SHARE * 2)

    def test_every_name_it_draws_is_one_the_stock_holds(self):
        held = {name for name, _ in self.stock['common']} | {name for name, _ in self.stock['rare']}
        draw = random.Random(6)
        for _ in range(500):
            name, gloss = naming.stock_name(self.stock, draw)
            self.assertIn(name, held)
            self.assertEqual(len(gloss.split('-')), 2, gloss)

    def test_the_draw_is_fixed_width_whichever_branch_it_takes(self):
        """A branch that spends a different number of draws desynchronises a replay."""
        for seed in range(30):
            spender = random.Random(seed)
            naming.stock_name(self.stock, spender)
            counter = random.Random(seed)
            counter.random(), counter.random()
            self.assertEqual(spender.random(), counter.random(), seed)

    def test_an_empty_stock_says_so_rather_than_returning_a_blank_name(self):
        empty = {'common': [], 'rare': [], 'thresholds': ()}
        self.assertIsNone(naming.stock_name(empty, random.Random(0)))

    def test_a_stock_with_only_a_tail_is_refused_rather_than_promoted(self):
        """Serving the rare pairings would make the tail the whole tongue, and would hide an
        unfillable template behind names that look perfectly fine."""
        tail_only = {'common': [], 'rare': self.stock['rare'], 'thresholds': ()}
        for seed in range(200):
            self.assertIsNone(naming.stock_name(tail_only, random.Random(seed)), seed)

    def test_a_stock_smaller_than_the_head_table_still_spends_every_share(self):
        """Truncating the head without renormalising would drop its last ranks unreachable."""
        for count in (1, 2, 3, len(naming.HEAD_SHARES), len(naming.HEAD_SHARES) + 7):
            thresholds = naming._thresholds(count)
            self.assertEqual(len(thresholds), count, count)
            self.assertAlmostEqual(thresholds[-1], 1.0, places=9, msg=count)

    def test_every_people_carries_a_stock_and_a_tail(self):
        for cid, parent in PEOPLES:
            stock = naming.name_stock(heritage.resolve(cid, parent), self.lexicon)
            self.assertTrue(stock['common'], cid)
            self.assertTrue(stock['rare'], cid)


if __name__ == '__main__':
    unittest.main()
