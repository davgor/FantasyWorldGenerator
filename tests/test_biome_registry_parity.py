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

    def test_order_is_asserted_not_merely_membership(self):
        """A guard on this test: a set comparison would pass the swap below, so it must not."""
        registry = _registry_catalogue()
        swapped = [registry[1], registry[0]] + registry[2:]
        self.assertEqual(set(x[0] for x in swapped), set(x[0] for x in registry))
        self.assertNotEqual(swapped, registry)


if __name__ == '__main__':
    unittest.main()
