"""`biomes.json` and `Core/biomes.cpp` are two sources of truth for one catalogue.

Extracting the identities to data left the C++ port hardcoded, which is a deliberate trade:
making `Core/` read JSON is far larger than the extraction it would serve. The debt is real
and recorded -- the fix is `Core/` reading the registry -- so this test exists to turn a
silent divergence into a loud one.

It compares the FULL tuple in ORDER, not as a set, because order is the contract:
`biome_variant` stores a flat index into the natural-biomes-by-schools cross product, so a
reordering that a set comparison would accept renumbers every variant in every saved world.
"""
import json
import re
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
ENTRY = re.compile(r'\{\s*(\d+)\s*,\s*"(\w+)"\s*,\s*\{\s*(\d+)\s*,\s*(\d+)\s*,\s*(\d+)\s*\}\s*\}')


def _native_catalogue():
    """The ordered contents of natural_catalogue() in the C++ port."""
    source = (ROOT / 'Core/biomes.cpp').read_text(encoding='utf-8')
    start = source.index('catalogue{')
    body = source[start:source.index('};', start)]
    return [(int(i), core, [int(r), int(g), int(b)]) for i, core, r, g, b in ENTRY.findall(body)]


def _registry_catalogue():
    """The ordered contents of the Python registry."""
    document = json.loads((ROOT / 'Sim/icarus_sim/biomes.json').read_text(encoding='utf-8'))
    return [(row['id'], row['core'], list(row['color'])) for row in document['natural_biomes']]


class BiomeRegistryParityTests(unittest.TestCase):
    def test_native_and_registry_agree_entry_for_entry_in_order(self):
        native, registry = _native_catalogue(), _registry_catalogue()
        self.assertTrue(native, 'failed to parse Core/biomes.cpp natural_catalogue()')
        # Ordered equality catches a reorder; the per-entry loop names which row drifted.
        self.assertEqual(len(native), len(registry), 'entry count differs between Core and biomes.json')
        for position, (left, right) in enumerate(zip(native, registry)):
            self.assertEqual(left, right, f'Core/biomes.cpp and biomes.json disagree at position {position}')
        self.assertEqual(native, registry)

    def test_registry_matches_the_python_catalogue_it_feeds(self):
        import sys
        sys.path.insert(0, str(ROOT / 'Sim'))
        from icarus_sim.terrain_biome_catalogue import natural_catalogue
        loaded = [(e['id'], e['core'], list(e['color'])) for e in natural_catalogue()]
        self.assertEqual(loaded, _registry_catalogue())

    def test_the_tombstone_is_a_catalogue_statement_not_a_classifier_one(self):
        """Biomes 1 and 6 stop commissioning art; nothing else about them moves.

        Every clause here is a thing the tombstone must NOT have done. The ordered id list and
        the thirteen rows are the `biome_variant` flat-index contract. The two `return` lines in
        the C++ classifier are load-bearing: terrain_biomes.py derives the "Snow region" feature
        marker from biome 6, so deleting that branch silently empties world output of it.
        """
        import sys
        sys.path.insert(0, str(ROOT / 'Sim'))
        from icarus_sim.terrain_biome_catalogue import (UNREACHABLE_BIOMES, natural_catalogue,
                                                        reachable_natural_catalogue,
                                                        biome_catalogue, reachable_biome_catalogue)
        self.assertEqual(UNREACHABLE_BIOMES, frozenset({1, 6}))
        self.assertEqual([row[0] for row in _registry_catalogue()],
                         [0, 1, 2, 3, 4, 5, 6, 7, 8, 13, 15, 16, 17])
        self.assertEqual(len(natural_catalogue()), 13)
        self.assertEqual(len(reachable_natural_catalogue()), 11)
        self.assertEqual(len(biome_catalogue()), 156)
        self.assertEqual(len(reachable_biome_catalogue()), 132)
        # natural_catalogue()'s dicts are world-output bytes; the flag must not leak into them.
        for entry in natural_catalogue():
            self.assertEqual(set(entry), {'id', 'core', 'name', 'color', 'asset_id'}, entry['id'])
        source = (ROOT / 'Core/biomes.cpp').read_text(encoding='utf-8')
        self.assertIn('return 1;', source)
        self.assertIn('return 6;', source)

    def test_the_tombstone_is_unreachable_in_practice_and_not_by_proof(self):
        """Guard on the justification, which has now been derived wrongly twice.

        The tempting proof is that the seventh-largest month equals the mean exactly, so a cell
        below 5 C can never show seven warm months. It does not: cos(2*pi*(3-6)/12) evaluates to
        +6.12e-17, not 0, so a mean a few ulps below 5.0 at large amplitude does survive the cold
        pass as biome 1. The tombstone rests on no world ever showing it, not on impossibility.
        """
        import sys
        sys.path.insert(0, str(ROOT / 'Sim'))
        from icarus_sim.terrain_biomes import classify
        from icarus_sim.terrain_ecology import monthly_temperatures, cold_habitat
        survivor = 4.999999999999999
        self.assertEqual(classify(1.0, 0.0, survivor, 0.0), 1)
        temperatures = monthly_temperatures(survivor, 90, 0.0, 2.0)
        self.assertEqual(sum(t > 5 for t in temperatures), 7)
        self.assertIsNone(cold_habitat(temperatures, 0.0, 0.0))
        # Biome 6 has no such band: it needs mean <= 0, and mean + amplitude*6.12e-17 < 5 always.
        self.assertEqual(classify(1.0, 0.0, 0.0, 0.0), 6)
        self.assertIsNotNone(cold_habitat(monthly_temperatures(0.0, 90, 0.0, 2.0), 0.0, 0.0))

    def test_order_is_asserted_not_merely_membership(self):
        """A guard on this test: a set comparison would pass the swap below, so it must not."""
        registry = _registry_catalogue()
        swapped = [registry[1], registry[0]] + registry[2:]
        self.assertEqual(set(x[0] for x in swapped), set(x[0] for x in registry))
        self.assertNotEqual(swapped, registry)


if __name__ == '__main__':
    unittest.main()
