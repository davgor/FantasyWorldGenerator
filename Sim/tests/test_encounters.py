"""The encounter index has to say what kind of thing it is answering with.

These run against a hand-built block rather than a generated world, deliberately. The
claim `CONTENT-ENCOUNTERS-ARE-FISH` makes is about a *split* -- that a land query can drop
the marine majority without joining back through two blocks -- and a generated world is a
bad fixture for a split, because it is 98.6% one disposition and roughly three quarters one
domain. A test written against those proportions passes for almost any mapping, including a
constant one. So the fixture carries one group per medium and per class, in equal numbers,
and every assertion is per entry: a constant domain, or a swapped one, fails on a named
uid rather than moving a percentage.
"""
import unittest

from icarus_sim import terrain_encounters as E
from icarus_sim.terrain_lab import Config
from icarus_sim.terrain_nests import profiles

# One real species per medium, and one flyer, so the fixture exercises every branch of the
# mapping. Real ids because the domain is resolved from the catalogue, not from the group.
OCEAN = 'abyssal-choir-worms'     # marine monster
LAKE = 'armored-river-crabs'      # freshwater monster
SHORE = 'atlantic-puffin'         # shore animal: lives on land, feeds at sea
GROUND = 'aardvark'               # land animal
FLYER = 'ash-crows'               # land monster that flies

MEDIUM_TO_DOMAIN = {'marine': 'ocean', 'freshwater': 'lake', 'land': 'land', 'shore': 'land'}


def profile(species_id):
    return next(p for p in profiles() if p['id'] == species_id)


def camp(uid, node, arrive, depart, kind='base'):
    return {'id': '%s-camp-%d' % (uid, node), 'node': node, 'kind': kind,
            'arrive_day': arrive, 'depart_day': depart}


def beast(species_id, node, movement='migratory'):
    p = profile(species_id)
    uid = 'beastmove-%s-%d' % (species_id, node)
    return {'uid': uid, 'species_id': species_id, 'name': p['name'], 'movement': movement,
            'family': p['family'], 'tier': p['tier'], 'kind': p['class'], 'source': 'wildlife',
            'host_uid': None, 'node': node, 'x': 0, 'z': 0, 'direction': [1., 0., 0.],
            'size': 40, 'speed_m_per_day': 17000., 'column_length_m': 12.,
            'disposition': 'hostile' if p['class'] == 'monster' else 'wary',
            'role': p.get('role'), 'route_status': 'routed', 'legs': [],
            'camps': [camp(uid, node, 10, 100), camp(uid, node + 1, 120, 200, 'terminal')]}


def band(uid, node, classification='merchants'):
    return {'uid': uid, 'classification': classification, 'disposition': 'tradeable',
            'size': 30, 'carries': ['salt'], 'seeks': ['grain'], 'god_id': None,
            'speed_m_per_day': 24000., 'column_length_m': 60.,
            'camps': [camp(uid, node, 5, 90)]}


def build():
    """One index over five creature groups and one band, evenly spread over the media."""
    cfg = Config(world_recipe=3, phase=16, shape='globe', tectonics=1)
    world = {'timing_ms': {'total': 0.},
             'nomads': {'groups': [band('nomad-0', 7)]},
             'beast_movements': {'groups': [beast(OCEAN, 1), beast(LAKE, 2), beast(SHORE, 3),
                                            beast(GROUND, 4), beast(FLYER, 5)]}}
    E.add_encounters(world, cfg)
    return world['encounters']


class EncounterEntryTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.index = build()
        cls.by_uid = {e['group_uid']: e for e in cls.index['entries']}

    def test_the_index_is_at_version_two(self):
        # Two fields were added to every entry; a consumer pinned to version 1 has to be
        # told, because `domain` is the field that changes what a land query returns.
        self.assertEqual(self.index['version'], 2)

    def test_every_creature_entry_carries_the_domain_its_species_lives_in(self):
        """Per entry, against the catalogue. A constant mapping dies on the first one."""
        self.assertEqual(len(self.by_uid), 6)
        for species_id in (OCEAN, LAKE, SHORE, GROUND, FLYER):
            entry = self.by_uid['beastmove-%s-%d'
                                % (species_id, [OCEAN, LAKE, SHORE, GROUND, FLYER].index(species_id) + 1)]
            expected = MEDIUM_TO_DOMAIN[profile(species_id)['medium']]
            self.assertEqual(entry['domain'], expected,
                             '%s lives in %s so its entry is %s, not %r'
                             % (species_id, profile(species_id)['medium'], expected, entry['domain']))

    def test_the_three_domains_are_all_present_and_distinct(self):
        # The fixture is built so they are: an index that collapses them is the defect,
        # and a share-based assertion on a generated world would not notice.
        domains = sorted({e['domain'] for e in self.index['entries']})
        self.assertEqual(domains, ['lake', 'land', 'ocean'])

    def test_a_land_query_drops_the_water_without_joining_another_block(self):
        """The card's acceptance test: reachable on foot, from the entry alone."""
        walkable = sorted(e['group_uid'] for e in self.index['entries'] if e['domain'] == 'land')
        self.assertEqual(walkable, ['beastmove-aardvark-4', 'beastmove-ash-crows-5',
                                    'beastmove-atlantic-puffin-3', 'nomad-0'])
        wet = sorted(e['group_uid'] for e in self.index['entries'] if e['domain'] != 'land')
        self.assertEqual(wet, ['beastmove-abyssal-choir-worms-1',
                               'beastmove-armored-river-crabs-2'])

    def test_a_shore_species_is_reachable_on_foot_and_a_marine_one_is_not(self):
        # The one mapping that is a judgement rather than a rename: `shore` is a land
        # medium in `suitability`, which refuses a shore species every water cell, so a
        # puffin colony is on the beach and a traveller can walk to it.
        self.assertEqual(self.by_uid['beastmove-%s-3' % SHORE]['domain'], 'land')
        self.assertEqual(self.by_uid['beastmove-%s-1' % OCEAN]['domain'], 'ocean')

    def test_every_entry_says_what_kind_of_thing_it_is(self):
        """animal / monster / people, on the word `beast_nests` and `wildlife` already use.

        `kind` on an entry is already spent on the species id or the band classification,
        and the class was lost there: a consumer asking "what could threaten a traveller"
        got `abyssal-choir-worms` and had to know the bestiary to read it.
        """
        for species_id, node in ((OCEAN, 1), (LAKE, 2), (SHORE, 3), (GROUND, 4), (FLYER, 5)):
            entry = self.by_uid['beastmove-%s-%d' % (species_id, node)]
            self.assertEqual(entry['class'], profile(species_id)['class'], species_id)
        self.assertEqual(self.by_uid['nomad-0']['class'], 'people')
        self.assertEqual(sorted({e['class'] for e in self.index['entries']}),
                         ['animal', 'monster', 'people'])

    def test_a_flyer_is_marked_and_nothing_else_is(self):
        airborne = sorted(e['group_uid'] for e in self.index['entries'] if e['airborne'])
        self.assertEqual(airborne, ['beastmove-ash-crows-5'])

    def test_the_limits_say_the_threat_histogram_describes_movers_only(self):
        # 94 tier-five nests produce no tier-five encounter, because nests are static and
        # only movers are indexed. Correct, surprising, and previously unstated.
        limits = self.index['limits']
        self.assertIn('threat_tier', limits)
        self.assertIn('static', limits)

    def test_the_occupancy_index_is_unchanged_by_the_added_fields(self):
        # The split is on the entry, not on the occupancy record: a consumer that joins
        # by_node -> occupancy -> entry keeps working.
        # One band with one camp, five creature groups with two camps each.
        self.assertEqual(len(self.index['occupancy']), 11)
        for record in self.index['occupancy']:
            self.assertIn(record['entry'], range(len(self.index['entries'])))
        self.assertEqual(sorted(self.index['by_node'], key=int),
                         sorted({str(r['node']) for r in self.index['occupancy']}, key=int))
        # Every occupancy record still resolves to an entry that now carries the split, so
        # "what is near node 4, on foot" is one join and one field test.
        near = [self.index['entries'][self.index['occupancy'][i]['entry']]
                for i in self.index['by_node']['4']]
        # Node 4 holds the aardvark's base and the puffin's terminal camp, both walkable.
        self.assertEqual(sorted(e['group_uid'] for e in near),
                         ['beastmove-aardvark-4', 'beastmove-atlantic-puffin-3'])
        self.assertEqual({e['domain'] for e in near}, {'land'})
        # Node 2 holds the river crabs' base and the choir worms' terminal camp: two
        # different waters at one node, and neither of them walkable.
        wet = [self.index['entries'][self.index['occupancy'][i]['entry']]
               for i in self.index['by_node']['2']]
        self.assertEqual({e['domain'] for e in wet}, {'lake', 'ocean'})


if __name__ == '__main__':
    unittest.main()
