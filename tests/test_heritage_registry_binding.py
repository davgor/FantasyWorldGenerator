"""Repository contract: heritage and the civilization registry describe the same peoples.

`Sim/heritage` is a leaf package - it never imports `icarus_sim`, so nothing at runtime
forces its ids, its parent races or its magic schools to agree with the registry. That
independence is deliberate, and this file is the price of it. Every enum heritage restates
is asserted here in both directions, so a people added on either side without the other
fails the repository suite rather than silently resolving to a parent base forever.

It also pins the property that justified making heritage a package rather than a section of
`civilizations.json`: the registry identity does not move.
"""
import json
from pathlib import Path
import re
import unittest

import heritage
from heritage import policy
from icarus_sim.civilization_registry import load_registry, registry_identity, section
from icarus_sim.terrain_leyline_history import HIDDEN_SCHOOLS, SCHOOLS
from icarus_sim.terrain_profiles import civilization_ids
from icarus_sim.terrain_ruins import culture_schools

# The twelve values `terrain_ruins.CULTURE_SCHOOL` held as a hand-written dict before the
# heritage `magic_school` axis absorbed it, recorded verbatim. The constant is gone and its
# unsynchronised twin in Core/legacy.cpp is going; this literal is what keeps the migration
# honest, because a derived mapping compared against itself proves nothing. A change here
# is a change to the world - ruin legacies seed leylines - and wants to be deliberate.
SHIPPED_CULTURE_SCHOOL = {
    'human_maritime': 'water', 'human_desert': 'fire', 'human_cold': 'water',
    'human_large_island': 'air', 'human_rainforest': 'earth', 'human_heartland': 'radiant',
    'dwarf': 'earth', 'elf': 'weave', 'gnome': 'weave', 'tidekin': 'water',
    'hill_dwarf': 'earth', 'frosthold_dwarf': 'water'}


def _parents():
    entities = load_registry()['entities']
    return {cid: entities[cid]['parent_race_id'] for cid in civilization_ids()}


class IdentifierBindingTests(unittest.TestCase):
    def setUp(self):
        heritage.reset_cache()
        self.traits = policy.load('traits')

    def test_heritage_names_exactly_the_registry_civilizations(self):
        self.assertEqual(set(self.traits['peoples']), set(civilization_ids()))

    def test_heritage_names_exactly_the_registry_parent_races(self):
        self.assertEqual(set(self.traits['races']), set(section('parent_races')))

    def test_appearance_describes_exactly_the_registry_peoples(self):
        """The body table is a second place ids can drift, so it is bound in both directions.

        A civilization added to the registry without a body resolves to a bare parent-race
        appearance forever, which is a silent wrong answer rather than a loud one: the
        concept art, the sprites and the model all come out as the archetype.
        """
        appearance = policy.load('appearance')
        self.assertEqual(set(appearance['peoples']), set(civilization_ids()))
        self.assertEqual(set(appearance['races']), set(section('parent_races')))

    def test_every_lexicon_family_binds_a_real_parent_race(self):
        families = policy.load('lexicon')['families']
        claimed = {entry['parent_race'] for entry in families.values()}
        self.assertEqual(claimed, set(section('parent_races')))

    def test_every_civilization_has_its_own_language_branch(self):
        """Every subrace bears a unique culture, so every subrace needs its own branch."""
        families = policy.load('lexicon')['families']
        branches = {b for entry in families.values() for b in entry['branches']}
        self.assertEqual(branches, set(civilization_ids()))


class SchoolBindingTests(unittest.TestCase):
    def test_known_schools_match_the_leyline_catalogue(self):
        live = tuple(s for s in SCHOOLS if s not in HIDDEN_SCHOOLS)
        self.assertEqual(set(policy.KNOWN_SCHOOLS), set(live))

    def test_no_hidden_school_is_reachable_as_a_trait(self):
        self.assertEqual(set(policy.KNOWN_SCHOOLS) & set(HIDDEN_SCHOOLS), set())
        self.assertEqual(set(policy.HIDDEN_SCHOOLS), set(HIDDEN_SCHOOLS))


class CultureSchoolAbsorptionTests(unittest.TestCase):
    """The pilot's zero-delta proof.

    `terrain_ruins.CULTURE_SCHOOL` is a hand-written dict mirrored verbatim and unsynced in
    `Core/legacy.cpp`. The heritage `magic_school` axis reproduces it exactly, which is what
    makes moving ruin legacies onto the derived layer provable as byte-identity rather than
    as a judgement call. This assertion is what lets that migration happen without a
    generated world in the loop; keep it after the constant is retired, comparing the
    derived mapping against the values recorded here.
    """

    def setUp(self):
        heritage.reset_cache()

    def test_derived_magic_school_reproduces_the_shipped_table(self):
        derived = {cid: heritage.resolve(cid, parent)['traits']['magic_school']
                   for cid, parent in _parents().items()}
        self.assertEqual(derived, SHIPPED_CULTURE_SCHOOL)

    def test_the_live_accessor_still_serves_the_shipped_values(self):
        """What `terrain_ruins` actually reads, not just what heritage could resolve."""
        self.assertEqual(culture_schools(), SHIPPED_CULTURE_SCHOOL)

    def test_every_civilization_declares_a_real_school(self):
        for cid, parent in _parents().items():
            school = heritage.resolve(cid, parent)['traits']['magic_school']
            self.assertIn(school, SCHOOLS, cid)
            self.assertNotIn(school, HIDDEN_SCHOOLS, cid)


class NativeCultureSchoolTests(unittest.TestCase):
    """Close the drift between the Python schools and their hand-copied C++ twin.

    `Core/legacy.cpp` holds its own literal copy of the culture-school table with no sync
    mechanism of any kind - not the exported catalogue, not `export_catalogues --check`,
    not a parity test. The two have simply been kept equal by hand.

    This reads the C++ source as text rather than compiling it. That is a deliberately
    narrow instrument: it cannot prove the native *behaviour* matches, only that the two
    tables still say the same thing, which is exactly the failure that has been possible
    here. It needs no toolchain, so it runs even while the native suite is red, and it
    retires itself the moment that table is replaced by a catalogue read.
    """

    SOURCE = Path(__file__).resolve().parents[1] / 'Core' / 'legacy.cpp'

    def _native_table(self):
        text = self.SOURCE.read_text(encoding='utf-8')
        match = re.search(r'culture_school\(\)\s*\{(.*?)return table;', text, re.S)
        if match is None:
            return None
        return dict(re.findall(r'\{"([a-z_]+)","([a-z_]+)"\}', match.group(1)))

    def test_the_native_copy_agrees_with_the_heritage_layer(self):
        if not self.SOURCE.is_file():
            self.skipTest('Core/legacy.cpp is not present')
        native = self._native_table()
        if not native:
            self.skipTest('Core/legacy.cpp no longer holds a literal culture-school table; '
                          'it presumably reads the exported catalogue, so this guard is spent')
        self.assertEqual(native, SHIPPED_CULTURE_SCHOOL)
        self.assertEqual(native, culture_schools())

    def test_the_exported_catalogue_carries_the_same_schools(self):
        """The route the native side should eventually read instead of its own literal."""
        catalogue = Path(__file__).resolve().parents[1] / 'Contracts' / 'catalogues' \
            / 'native-catalogues-v1.json'
        if not catalogue.is_file():
            self.skipTest('native catalogue has not been exported')
        shipped = json.loads(catalogue.read_text(encoding='utf-8'))['heritage']
        exported = {cid: entry['traits']['magic_school'] for cid, entry in shipped.items()}
        self.assertEqual(exported, SHIPPED_CULTURE_SCHOOL)


class RegistryIdentityTests(unittest.TestCase):
    """Introducing heritage must not invalidate a single saved world.

    `registry_identity()` is a sha256 over the whole resolved registry document, and
    `terrain_history` refuses to advance a saved world whose registry hash moved. Holding
    the heritage tables outside `civilizations.json` is what keeps that hash still, and is
    the reason this layer is a package rather than an eleventh entity section.
    """

    def test_registry_document_carries_no_heritage_data(self):
        document = load_registry()
        self.assertNotIn('heritage', document)
        for cid, entity in document['entities'].items():
            self.assertNotIn('heritage', entity, cid)
            self.assertNotIn('culture', entity, cid)

    def test_registry_identity_is_unmoved_by_resolving_heritage(self):
        before = registry_identity()
        for cid, parent in _parents().items():
            heritage.resolve(cid, parent)
        self.assertEqual(registry_identity(), before)

    def test_heritage_identity_is_reported_separately(self):
        identity = heritage.heritage_identity(tuple(_parents().items()))
        self.assertEqual(set(identity), {'revision', 'sha256'})
        self.assertEqual(set(identity['revision']), set(policy.POLICY_FILES))


class ExportShapeTests(unittest.TestCase):
    def test_the_exported_catalogue_carries_a_body_for_every_people(self):
        """The channel the art pipeline actually reads.

        Appearance ships through the native catalogue rather than through the world
        document: it is the same for every seed, and putting it in each generated world
        would move the `civilizations` block version and reject every saved world for data
        no generation step reads. A catalogue exported before this layer landed fails here
        rather than quietly serving traits with no body attached.
        """
        catalogue = Path(__file__).resolve().parents[1] / 'Contracts' / 'catalogues'             / 'native-catalogues-v1.json'
        if not catalogue.is_file():
            self.skipTest('native catalogue has not been exported')
        shipped = json.loads(catalogue.read_text(encoding='utf-8'))['heritage']
        self.assertEqual(set(shipped), set(civilization_ids()))
        for cid, entry in shipped.items():
            self.assertEqual(set(entry['appearance']), set(policy.APPEARANCE_BLOCKS), cid)

    def test_resolved_peoples_serialise_as_finite_json(self):
        """What ships to the native side has to survive the catalogue writer unchanged."""
        heritage.reset_cache()
        resolved = {cid: heritage.resolve(cid, parent) for cid, parent in _parents().items()}
        text = json.dumps(resolved, sort_keys=True, separators=(',', ':'), allow_nan=False)
        self.assertEqual(json.loads(text), resolved)


if __name__ == '__main__':
    unittest.main()
