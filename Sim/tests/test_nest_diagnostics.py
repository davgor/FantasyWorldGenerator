"""What the two nest passes report about themselves.

Two claims, both of which exist because the number a reader would reach for first is the
wrong one.

**The danger gradient.** `danger_ramp` slides a tier's rate outward from settled ground,
and the obvious way to check it is the median distance from a placed site to the nearest
settlement. That measurement cannot see it. Placement resolves at the raster cell and a
tier holds at most one lair per cell, so at every width this product ships the bottom
tiers are saturated -- the placed set is the set of cells the tier reaches, and every tier
reaches nearly the same ground, because the only tier-keyed gate on a cell is a clearance
of 250 m to 1250 m against a pitch of kilometres. Measured on the reference world:
ablating the ramp entirely moves the spread of tier medians by 0.02 km. So the gradient is
asserted where it is exact, on the rate, exactly as the pyramid is asserted on
`saturation.drawn` rather than on the placed histogram.

**Reachability.** A catalogue count is authored entries. What a world can hold is smaller
and was never stated, and absence was indistinguishable from a creature that lost the
draw. `diagnostics` now carries a reason per species and the block carries the counts.
`eligible` and `placed` are properties of THIS world, not of every world: 53 of 680
profiles change eligibility across five seeds at one raster, so a per-world count is a
sample and says so. The only world-independent proof available is `never satisfiable`, and
it covers 25 profiles against the 62 this world merely lacks.

The fifth reason is the one nobody predicted, and it is why the vocabulary is not four
values: monster profiles can be refused by `nest_settlement_clearance` rather than by the
world, because their `graves` habitat is the ground settlements stand on. Filing those as a
world reason sends a reader to look at terrain that is fine. How many there are is itself a
per-world number -- 57 on seed 42, 32 on seed 7, 1 on seed 73 -- so this test asserts that
whichever profiles the gate accounts for are named, not how many there are.
"""
import unittest

from icarus_sim.terrain_nests import (profiles, REACH_REASONS, NEVER_SATISFIABLE,
                                      LOST_THE_DRAW, ABSENT_FROM_THIS_WORLD, PLACED,
                                      CLEARED_OUT)

PASSES = (('wildlife', 'animal'), ('beast_nests', 'monster'))


def build(**overrides):
    from icarus_sim.terrain_world import generate_request
    return generate_request({'seed': 42, 'overrides': {'size': 33, 'phase': 13, **overrides}})


class NestDiagnosticsTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.world = build()

    def rows(self, key):
        return sorted(self.world[key]['saturation'], key=lambda r: r['tier'])

    # ------------------------------------------------------------------ gradient

    # Tier three is the ramp's pivot: `danger_ramp(3, d, span)` is exactly
    # `(1 + NEST_DANGER_FLOOR) / 2` at every distance, which
    # `test_terrain_nests.test_danger_ramps_with_distance_instead_of_stepping` asserts
    # directly. A tier the mechanism does not move cannot be ordered by it, so it is
    # excluded by construction and not because it is inconvenient -- and its
    # `rate_distance_m` is identical in every ablation arm, 5051 m for monsters and 5771 m
    # for animals, which is the proof that the exclusion is the mechanism's, not the test's.
    PIVOT_TIER = 3

    # Top of the ladder minus the bottom, in metres, on the reference world. Shipped: 1274
    # for monsters and 544 for animals. With `danger_ramp` ablated to a constant the same
    # quantity is 236 and -76 -- what is left is habitat, which has its own opinion about
    # where a tier lives and no opinion at all about danger.
    RATE_SPAN_M = {'beast_nests': 700., 'wildlife': 300.}

    def test_the_danger_gradient_is_carried_by_the_rate(self):
        """The claim `danger_ramp` actually makes, on the quantity it actually moves.

        `rate_distance_m` is the mean distance from settled ground of the groups the
        intensity asks for, weighted by the rate itself: the ramp integrated over the
        world.

        Two assertions, because the card this closes asked for two things. The order holds
        across every tier the ramp moves -- 4910 / 5285 / 5565 / 6184 m for monsters, four
        tiers strictly increasing -- and the span from the bottom of that ladder to the top
        is 1.27 km, against 236 m with the ramp ablated, where the order also collapses.
        Neither assertion survives the ablation, so neither is measuring habitat.

        What is deliberately NOT asserted is an order across all five tiers. Tier three is
        the pivot and is unmoved by construction, so a five-tier ladder is not something
        this mechanism can make at any tuning on any world. That is the shape of the thing,
        and a test that hid it behind a weaker claim would be hiding the finding.
        """
        for key, _ in PASSES:
            rows = [r for r in self.rows(key)
                    if r['drawn'] and r['rate_distance_m'] is not None
                    and r['tier'] != self.PIVOT_TIER]
            self.assertGreater(len(rows), 2, key)
            seq = [r['rate_distance_m'] for r in rows]
            self.assertEqual(seq, sorted(seq),
                             '%s: the rate does not move danger outward tier by tier: %s'
                             % (key, [(r['tier'], round(r['rate_distance_m'])) for r in rows]))
            self.assertGreater(seq[-1] - seq[0], self.RATE_SPAN_M[key],
                               '%s: the rate puts the top tier only %d m further from people '
                               'than tier one, which is what habitat alone does: %s'
                               % (key, round(seq[-1] - seq[0]),
                                  [(r['tier'], round(r['rate_distance_m'])) for r in rows]))

    def test_the_raster_clips_the_gradient_out_of_the_placed_set(self):
        """The finding, pinned so it is not rediscovered as a regression.

        At the widths this product ships the placed set is the cells a tier reaches, and
        those are nearly the same cells for every tier, so the gradient the rate carries
        does not survive into `sites`. Asserting the inequality rather than a literal
        keeps it readable if the raster ever moves: flipping it means placement started
        expressing the gradient, which is a deliberate change and not a silent one.
        """
        rows = [r for r in self.rows('beast_nests')
                if r['placed'] and r['rate_distance_m'] is not None]
        self.assertTrue(rows)
        rate = [r['rate_distance_m'] for r in rows]
        placed = [r['placed_distance_m'] for r in rows]
        self.assertLess(max(placed) - min(placed), max(rate) - min(rate),
                        'the placed set carries as much of the gradient as the rate does, '
                        'which the one-lair-per-cell ceiling should make impossible at this '
                        'raster: rate %s placed %s'
                        % ([round(v) for v in rate], [round(v) for v in placed]))
        # And the mechanism that clips it: every tier is at or near its cell ceiling.
        for row in self.rows('beast_nests'):
            self.assertLessEqual(row['placed'], row['cells'], row)

    # -------------------------------------------------------------- reachability

    def test_every_profile_is_accounted_for_with_a_reason(self):
        for key, klass in PASSES:
            block = self.world[key]
            catalogue = [p for p in profiles() if p['class'] == klass]
            rows = {row['species_id']: row for row in block['diagnostics']}
            self.assertEqual(sorted(rows), sorted(p['id'] for p in catalogue), key)
            for row in rows.values():
                self.assertIn(row['reason'], REACH_REASONS, row)
                self.assertGreaterEqual(row['cells'], 0, row)
                if row['placed']:
                    self.assertEqual(row['reason'], PLACED, row)
                    self.assertGreater(row['cells'], 0, row)
                elif row['cells']:
                    self.assertEqual(row['reason'], LOST_THE_DRAW, row)
                else:
                    self.assertIn(row['reason'],
                                  (ABSENT_FROM_THIS_WORLD, NEVER_SATISFIABLE, CLEARED_OUT), row)

    def test_a_species_refused_by_the_clearance_is_not_reported_as_a_world_reason(self):
        """The near-miss this vocabulary exists to avoid.

        `graves` is a field that exists where people bury people, so the graveyard and
        barrow creatures can score only on the cells settlements stand on -- and those are
        exactly the cells `nest_settlement_clearance` refuses. On the reference world that
        is 57 profiles, every one eligible on the same 7 cells and placeable on none; on
        seed 73 it is one. It is a placement rule refusing them, not the world lacking
        their conditions, and the two send a reader to different places.

        Checked by recomputing eligibility with the clearance gate removed and requiring
        that every profile the gate alone accounts for says so.
        """
        from icarus_sim.terrain_lab import Config
        from icarus_sim.terrain_erosion import sphere_grid
        from icarus_sim.terrain_nests import habitat_cells, suitability, biome_weight
        from icarus_sim.terrain_world import options
        cfg = Config(**self.world['config'])
        radius = self.world['effective_config']['globe_radius']
        floor = options(cfg)['nest_min_suitability']
        points, areas, _ = sphere_grid(cfg.size, radius)
        cells = habitat_cells(self.world, cfg, points, areas)
        rows = {row['species_id']: row for row in self.world['wildlife']['diagnostics']}
        rows.update({row['species_id']: row for row in self.world['beast_nests']['diagnostics']})
        named = 0
        for p in profiles():
            row = rows[p['id']]
            if row['cells']:
                continue
            without_clearance = any(biome_weight(p, c['biome']) > 0
                                    and suitability(p, c['fields'])[0] >= floor
                                    for c in cells)
            if without_clearance:
                self.assertEqual(row['reason'], CLEARED_OUT, p['id'])
                named += 1
            else:
                self.assertNotEqual(row['reason'], CLEARED_OUT, p['id'])
        self.assertGreater(named, 0, 'no profile is refused by the clearance alone, so either '
                                     'the clearance stopped biting or the check stopped looking')

    def test_the_three_integers_agree_with_the_rows_and_the_sites(self):
        for key, klass in PASSES:
            block = self.world[key]
            summary = block['reachability']
            rows = block['diagnostics']
            self.assertEqual(summary['authored'], len(rows), key)
            self.assertEqual(summary['authored'], block['catalogue_count'], key)
            self.assertEqual(summary['eligible'], sum(1 for r in rows if r['cells']), key)
            self.assertEqual(summary['placed'], sum(1 for r in rows if r['placed']), key)
            self.assertEqual(summary['placed'], len({s['species_id'] for s in block['sites']}), key)
            self.assertLessEqual(summary['placed'], summary['eligible'], key)
            self.assertLessEqual(summary['eligible'], summary['authored'], key)
            self.assertTrue(summary['scope'], key)

    def test_absence_from_this_world_is_not_a_proof_of_unreachability(self):
        """The honesty the card turns on, as an assertion rather than a sentence.

        `never_satisfiable` is decided from the catalogue alone -- a profile that requires
        a ley school generation can never raise. Everything else that is missing is missing
        from THIS world. Measured across five seeds at size 33: 579 profiles are eligible
        on all five, 53 on some but not all, and 48 on none -- and only 25 of that 48 are
        provable. A report that called all 48 unreachable would be wrong about 23 of them.
        So the provable set must stay strictly smaller than the absent set, or the block is
        claiming a proof it does not have.
        """
        authored = eligible = provable = 0
        for key, _ in PASSES:
            summary = self.world[key]['reachability']
            authored += summary['authored']
            eligible += summary['eligible']
            provable += summary['never_satisfiable']
        self.assertGreater(authored - eligible, provable,
                           'every profile absent from this world is claimed as provably '
                           'unreachable, which absence cannot establish')
        self.assertGreater(provable, 0, 'the dormant-school profiles are provable and should be named')

    def test_a_dormant_school_requirement_is_the_world_independent_verdict(self):
        from icarus_sim.terrain_world import HIDDEN_NETWORKS
        dormant = {'ley_' + name for name in HIDDEN_NETWORKS}
        seen = 0
        for key, klass in PASSES:
            rows = {row['species_id']: row for row in self.world[key]['diagnostics']}
            for p in profiles():
                if p['class'] != klass:
                    continue
                if any(k in dormant and v > 0 for k, v in p['requires'].items()):
                    self.assertEqual(rows[p['id']]['reason'], NEVER_SATISFIABLE, p['id'])
                    seen += 1
                else:
                    self.assertNotEqual(rows[p['id']]['reason'], NEVER_SATISFIABLE, p['id'])
        self.assertGreater(seen, 0)


if __name__ == '__main__':
    unittest.main()
