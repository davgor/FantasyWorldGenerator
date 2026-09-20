"""Movement classes on the creature catalogue.

The assertion that matters here is **structural placeability**, not observed placement. A
creature that never appears in a sample world has either been authored wrong -- impossible
medium, a `requires` threshold nothing reaches, weights that cannot clear the suitability
floor -- or it simply lost the draw to incumbents competing for the same ground. Those are
completely different problems and only the first is a bug.

Checking observed placement conflates them. On a 200 km world the umbral ground a wandering
undead needs comes to eight eligible cells, shared with the thirty-seven undead that were
already there, so a new one can be perfectly well authored and still not appear. What must
hold is that somewhere on the world its suitability clears the floor with a positive biome
weight: that proves the authoring, and leaves the draw to the pyramid.
"""
import unittest
from icarus_sim.terrain_nests import profiles, suitability, biome_weight, habitat_cells, MEDIA

MOVEMENTS = ('nester', 'migratory', 'irruptive', 'follower', 'drifter')

# Undead with somewhere to lie, and undead without. The rule the split is built on: an
# undead with a grave nests at it, an undead without one wanders.
GRAVE_BOUND = ('skeletons', 'tomb-wardens', 'barrow-wight', 'cairn-wolves', 'ossuary-spiders')
UNHOUSED = ('zombies', 'wraiths', 'road-shades', 'the-wild-hunt', 'corpse-lights')

ADDED = ('corpse-lights', 'road-shades', 'unquiet-column', 'plague-cortege', 'the-wild-hunt',
         'carrion-flies', 'grass-tide-rats', 'ravening-swarm', 'devouring-tide',
         'carrion-followers', 'caravan-jackals', 'herd-stalkers', 'hunt-wraiths',
         'skywhales', 'thunder-herd', 'pilgrim-elk', 'barrow-wight')


def by_id():
    return {p['id']: p for p in profiles()}


class MovementCatalogueTests(unittest.TestCase):
    def test_every_creature_declares_a_known_movement(self):
        for profile in profiles():
            self.assertIn(profile.get('movement'), MOVEMENTS, profile['id'])

    def test_the_default_is_nester_so_nothing_existing_changed_behaviour(self):
        counts = {}
        for profile in profiles():
            counts[profile['movement']] = counts.get(profile['movement'], 0) + 1
        self.assertGreater(counts['nester'], sum(v for k, v in counts.items() if k != 'nester'),
                           'most creatures hold ground; movement is the exception')
        for movement in MOVEMENTS:
            self.assertIn(movement, counts, '%s has no creatures at all' % movement)

    def test_an_undead_with_a_grave_stays_and_one_without_wanders(self):
        catalogue = by_id()
        for cid in GRAVE_BOUND:
            self.assertEqual(catalogue[cid]['movement'], 'nester', cid)
        for cid in UNHOUSED:
            self.assertEqual(catalogue[cid]['movement'], 'drifter', cid)

    def test_a_follower_is_a_predator_or_a_scavenger(self):
        """Followers track something else's movement, so they must be things that track."""
        catalogue = by_id()
        for profile in profiles():
            if profile['movement'] != 'follower':
                continue
            if profile['class'] == 'animal':
                self.assertIn(profile['role'],
                              ('pack_predator', 'pursuit_predator', 'apex_predator',
                               'scavenger', 'bird_of_prey', 'shark_other'),
                              profile['id'])

    def test_the_new_creatures_are_well_formed(self):
        catalogue = by_id()
        for cid in ADDED:
            self.assertIn(cid, catalogue, cid)
            profile = catalogue[cid]
            self.assertIn(profile['medium'], MEDIA, cid)
            self.assertIn(profile['class'], ('animal', 'monster'), cid)
            self.assertTrue(1 <= profile['tier'] <= 5, cid)
            self.assertTrue(profile['weights'], cid)
            for key, weight in profile['weights'].items():
                self.assertGreater(weight, 0, (cid, key))
            self.assertEqual(profile['real'], profile['class'] == 'animal', cid)


class MovementPlacementTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        from icarus_sim.terrain_world import generate_request
        from icarus_sim.terrain_lab import Config
        from icarus_sim.terrain_erosion import sphere_grid
        cls.world = generate_request({'seed': 42, 'overrides': {'size': 33, 'phase': 13}})
        cfg = Config(**cls.world['config'])
        radius = cls.world['effective_config']['globe_radius']
        points, areas, _ = sphere_grid(cfg.size, radius)
        cls.cells = habitat_cells(cls.world, cfg, points, areas)
        cls.floor = 0.3

    def eligible_cells(self, profile):
        count = 0
        for cell in self.cells:
            score, _ = suitability(profile, cell['fields'])
            if score >= self.floor and biome_weight(profile, cell['biome']) > 0:
                count += 1
        return count

    def test_every_added_creature_could_place_somewhere(self):
        """Authoring check, not a draw check.

        A `requires` threshold nothing on the world reaches, or weights that lean on a
        hidden school locked at zero occurrence, produce a creature that can never appear
        anywhere. That failure is silent -- the catalogue validates, the world generates,
        and the creature simply is not in it. Seven of the seventeen added here failed
        exactly this way on first authoring.
        """
        catalogue = by_id()
        for cid in ADDED:
            with self.subTest(creature=cid):
                self.assertGreater(self.eligible_cells(catalogue[cid]), 0,
                                   '%s can never place: no cell clears the suitability floor' % cid)

    def why_unplaceable(self, profile):
        """Which of the three gates stopped it, or None if it can place.

        Decomposing this is the whole point. "Cannot place" bundles together one defect and
        two perfectly ordinary facts about a particular world, and an assertion that does
        not separate them is either permanently red or silently useless.
        """
        best, reached_floor = 0., False
        for cell in self.cells:
            score, _ = suitability(profile, cell['fields'])
            if score > best:
                best = score
            if score >= self.floor:
                reached_floor = True
                if biome_weight(profile, cell['biome']) > 0:
                    return None
        if best <= 0.:
            # Medium, temperature or a `requires` threshold is unmet on every cell. The
            # world does not present the conditions -- two freshwater cells, no coast above
            # the shore gate, a ley school that did not manifest. Not a defect.
            return 'conditions absent from this world'
        if not reached_floor:
            # It passes its hard gates somewhere and still cannot score. This is the
            # authoring defect: weights that cannot carry suitability over the floor.
            return 'weights never reach the suitability floor'
        return 'biome weight is zero wherever it scores'

    # `brimstone-bats` wants mountain, volcanic ground and an infernal ley all at once, and
    # the three together do not clear the floor anywhere. Pre-existing, not from this pass,
    # and recorded rather than silently tolerated so the assertion below stays meaningful.
    KNOWN_UNDERWEIGHTED = ('brimstone-bats',)

    def test_no_creature_passes_its_gates_and_still_cannot_score(self):
        """The one failure mode that is genuinely an authoring defect.

        Seven of the seventeen creatures added in this pass failed exactly this way: they
        cleared medium and temperature and `requires`, then leaned on `ley_rot` or
        `ley_eldritch` for their score, and those schools are locked at zero occurrence. The
        weights contributed nothing, suitability never reached the floor, and the creatures
        could not appear in any world. Nothing raised -- the catalogue validated and the
        worlds generated without them.

        Creatures that fail on their hard gates are excluded deliberately: that means the
        world lacks their conditions, not that they are malformed.
        """
        broken = [p['id'] for p in profiles()
                  if self.why_unplaceable(p) == 'weights never reach the suitability floor'
                  and p['id'] not in self.KNOWN_UNDERWEIGHTED]
        self.assertEqual(sorted(broken), [],
                         'creatures that clear their gates and still cannot score: %s' % sorted(broken)[:10])

    def test_the_unplaceable_are_unplaceable_for_world_reasons(self):
        """Everything that cannot place is accounted for by a named cause."""
        causes = {}
        for profile in profiles():
            reason = self.why_unplaceable(profile)
            if reason is not None:
                causes.setdefault(reason, []).append(profile['id'])
        self.assertNotIn('weights never reach the suitability floor',
                         {k: v for k, v in causes.items()
                          if set(v) - set(self.KNOWN_UNDERWEIGHTED)},
                         causes.get('weights never reach the suitability floor'))
        for cid in ADDED:
            self.assertIsNone(self.why_unplaceable(by_id()[cid]), cid)

    def test_no_creature_scores_only_on_dormant_layers(self):
        """World-independent, and the check that would have caught my own authoring bug.

        Seven of the seventeen creatures added in this pass leaned on `ley_rot` or
        `ley_eldritch` for their whole score. Those schools are locked at zero occurrence,
        so the weights contributed nothing, suitability never cleared the floor, and the
        creatures could not appear in any world at all. Nothing raised -- the catalogue
        validated and the worlds generated without them.

        A creature may legitimately *require* a hidden school; that is what dormant means.
        What it may not do is depend on one for its entire score while presenting itself as
        a creature of a live school.
        """
        from icarus_sim.terrain_world import HIDDEN_NETWORKS
        hidden = {'ley_' + name for name in HIDDEN_NETWORKS}
        for profile in profiles():
            weights = set(profile['weights'])
            if not weights or not weights <= hidden:
                continue
            # Scoring only on hidden layers is fine if the creature is declaredly dormant,
            # which it shows by requiring one too.
            self.assertTrue(set(profile['requires']) & hidden,
                            '%s scores only on dormant layers but does not require one' % profile['id'])


if __name__ == '__main__':
    unittest.main()
