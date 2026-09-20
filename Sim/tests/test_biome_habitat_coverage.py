"""Every biome an animal can stand on has animals authored for it.

This is the assertion whose absence let persistent land ice sit at zero animals for the
whole life of the catalogue. `biome_weight` returns 0.0 for a key that is absent, which
is indistinguishable from a deliberate 0.0 and invisible from either side: the biome
looks like ground nothing chose, and the role table looks complete. Nothing counted the
biomes from the other end.

Nothing here generates a world.
"""
import unittest
from icarus_sim.terrain_nests import profiles, roles, biome_weight
from icarus_sim.terrain_biome_catalogue import NATURAL_BIOMES

# 1 tundra and 6 snow are unreachable, not unloved: terrain_ecology.cold_habitat
# overwrites every cell terrain_biomes.classify would label 1 or 6 with 15, 16 or 17
# before any nest pass runs, in every legal option setting. A key for ground that cannot
# occur is a lie in the data, so they are excluded here rather than authored around.
UNREACHABLE = (1, 6)


class BiomeHabitatCoverageTests(unittest.TestCase):
    def test_every_reachable_biome_has_animals(self):
        covered = {biome for body in roles().values() for biome in body['biome_weights']}
        for bid, core in NATURAL_BIOMES.items():
            if bid in UNREACHABLE:
                continue
            self.assertIn(str(bid), covered, f'biome {bid} {core} is in no animal role table')

    def test_every_reachable_biome_has_a_living_animal(self):
        # The stronger form: a key on a role nothing is authored into would satisfy the
        # test above and still leave the ground empty.
        animals = [p for p in profiles() if p['class'] == 'animal']
        for bid, core in NATURAL_BIOMES.items():
            if bid in UNREACHABLE:
                continue
            reach = [p['name'] for p in animals if biome_weight(p, bid) > 0]
            self.assertTrue(reach, f'biome {bid} {core} has no animal that can stand on it')

    def test_land_ice_stays_below_cold_tundra(self):
        # User ruling 3.0. Land ice is habitat, not a wall -- but it is the harshest
        # ground on the planet and every role has to be rarer there than on the cold
        # tundra beside it. Asserted rather than eyeballed: the two columns are three
        # hundred lines apart in the document.
        LAND_ICE, COLD_TUNDRA = '17', '16'
        tables = {role: body['biome_weights'] for role, body in roles().items()}
        on_ice = {role: table[LAND_ICE] for role, table in tables.items() if LAND_ICE in table}
        self.assertTrue(on_ice, 'no role reaches land ice at all')
        for role, weight in on_ice.items():
            cold = tables[role].get(COLD_TUNDRA)
            if cold is not None:
                self.assertLess(weight, cold, f'{role} is no rarer on land ice than on cold tundra')
        # The ambush predators are the one deliberate near-zero. Land ice has nothing to
        # hide behind, and the temperature bands are coarse enough that raising this
        # admits caracals and ocelots to a glacier before it admits a snow leopard.
        self.assertEqual(on_ice.get('ambush_predator'), 0.05)

    def test_no_role_claims_unreachable_ground_it_alone_would_need(self):
        # Not a ban on the dead keys 1 and 6 -- another lane owns removing them -- but
        # no animal may depend on them for its whole range, or it is authored into a
        # world that cannot happen.
        animals = [p for p in profiles() if p['class'] == 'animal']
        stranded = [p['name'] for p in animals
                    if not any(biome_weight(p, bid) > 0
                               for bid in NATURAL_BIOMES if bid not in UNREACHABLE)]
        self.assertEqual(stranded, [])


if __name__ == '__main__':
    unittest.main()
