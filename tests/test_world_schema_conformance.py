"""Generated documents must satisfy the published Contracts/ schemas.

Before this existed the schemas were hand-edited per section and drifted: the
city-plan contract reached version 6 and gained a fortification pass while
world-output.schema.json still declared version 4 and the old phase order.
Nothing failed, because no test ever compared real output against the schema
that Unreal consumers are told to build against.
"""

import json
from pathlib import Path
import sys
import unittest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'tests'))
sys.path.insert(0, str(ROOT / 'Sim'))

from schema_subset import errors, validate


def schema(name):
    return json.loads((ROOT / 'Contracts/schemas' / name).read_text(encoding='utf-8'))


class WorldSchemaConformanceTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        from fantasy_world_generator.cli import world_document
        # Small enough to stay quick, large enough to populate every planner section.
        # Build stages stay in so the stage-scrubber checks below reuse this one world.
        cls.world = world_document({'recipe_version': 3, 'seed': 42, 'overrides': {'size': 17}}, build_stages=True)

    def test_generated_world_satisfies_the_published_world_schema(self):
        validate(self.world, schema('world-output.schema.json'))

    def test_generated_world_exercises_every_versioned_section(self):
        """A conformance pass is only meaningful if the sections are actually present."""
        for section in ('terrain', 'settlements', 'civilizations', 'city_plans',
                        'hamlet_plans', 'castle_plans', 'world_scene', 'astrology', 'lunar_almanac', 'religion'):
            with self.subTest(section=section):
                self.assertIn(section, self.world)
        self.assertTrue(self.world['city_plans']['cities'], 'seed 42 size 17 must plan at least one city')

    def test_generated_world_carries_exterior_plans_for_every_key_location(self):
        """A location without a plan renders as nothing, which is the failure the plans exist to prevent."""
        from icarus_sim.terrain_history import materialize_stage

        plans = self.world['key_location_plans']
        self.assertEqual(plans['status'], 'ok', plans.get('error'))
        validate(plans, schema('key-location-plans.schema.json'))

        sites = {s['id'] for s in self.world['key_locations']['sites']}
        planned = {p['location_id'] for p in plans['plans']}
        self.assertEqual(planned, sites, 'every placed location needs an arrangement on the ground')
        self.assertTrue(all(p['plots'] for p in plans['plans']))

        for plan in plans['plans']:
            for plot in plan['plots']:
                self.assertGreaterEqual(plot['ground_elevation_m'], plot['foundation_bottom_m'])
                self.assertTrue(0 <= plot['rotation_degrees'] < 360)

        self.assertNotIn('key_location_plans', materialize_stage(self.world, 15))

    def test_generated_world_carries_a_valid_key_locations_block_only_from_stage_sixteen(self):
        from icarus_sim.terrain_history import materialize_stage

        block = self.world['key_locations']
        self.assertEqual(block['status'], 'ok', block.get('error'))
        validate(block, schema('key-locations.schema.json'))
        self.assertTrue(block['sites'], 'seed 42 size 17 has terrain and history, so it must have places')

        claimed = set()
        for group in (self.world.get('ruins', []),
                      self.world.get('beast_nests', {}).get('sites', []),
                      self.world.get('religion', {}).get('sites', []),
                      self.world.get('magic', {}).get('colleges', []),
                      self.world.get('regions', {}).get('landmarks', [])):
            claimed |= {r['node'] for r in group if r.get('node') is not None}
        scattered = [site for site in block['sites'] if site['placement'] == 'node']
        nodes = [site['node'] for site in scattered]
        self.assertEqual(len(nodes), len(set(nodes)), 'two node-placed locations must never share a node')
        self.assertFalse(set(nodes) & claimed, 'ground another module placed on is left to it')

        names = [site['name'] for site in block['sites']]
        self.assertEqual(len(names), len(set(names)), 'a duplicate name makes two places indistinguishable')
        for site in block['sites']:
            if site['placement'] == 'node':
                self.assertEqual(site['id'], f"keyloc-{site['kind']}-{site['node']}")
            self.assertEqual(site['interior'] is not None, site['tier'] == 2)

        by_id = {site['id']: site for site in block['sites']}
        for chain in block['chains']:
            members = [by_id[m] for m in chain['members']]
            self.assertEqual([m['links']['chain_index'] for m in members], list(range(len(members))),
                             f"{chain['id']} must be ordered along its path")
        for cluster in block['clusters']:
            self.assertIn(cluster['anchor'], by_id, 'a cluster must hang off a site that exists')
            for member in cluster['members']:
                self.assertEqual(by_id[member]['links']['anchor'], cluster['anchor'])

        self.assertNotIn('key_locations', materialize_stage(self.world, 15))
        self.assertEqual(materialize_stage(self.world, 16)['key_locations']['summary'], block['summary'])

    def test_generated_world_carries_a_valid_heroes_block_only_from_stage_sixteen(self):
        """The separate hero generator ran, its block validates, and the scrubber hides it earlier."""
        from icarus_sim.terrain_history import materialize_stage
        heroes = self.world['heroes']
        self.assertEqual(heroes['status'], 'ok', heroes.get('error'))
        validate(heroes, schema('hero-generator.schema.json'))
        self.assertEqual(heroes['final_age'], len(self.world['history']['ages']))
        self.assertEqual(len(heroes['people']), sum(heroes['summary'][k] for k in ('living', 'legends')))
        self.assertTrue(heroes['people'], 'seed 42 size 17 has ruins, so it must have heirs')
        humans = self.world['humans']
        ids = {'ruin': {r['id'] for r in self.world['ruins']},
               'war': {w['id'] for age in self.world['history']['ages'] for w in age['wars']},
               'nest': {n['id'] for n in self.world['beast_nests']['sites']},
               'founding': {f"founding-{s['node']}" for s in self.world['settlements']['sites']},
               # `uid`, strictly, never `uid or id`. A hamlet's and a fortress's `id` is an
               # ordinal -- the position in a list `terrain_humans` re-sorts by defence score
               # at every age boundary -- so it cannot anchor a deed across one, and the cast
               # keys on the node instead. A fallback here would pass whether or not the
               # producer mints the uid, which is the whole thing these two lines check.
               #
               # `humans.hamlets` has two producers and only one of them mints a uid.
               # `terrain_humans.record` does; `terrain_society`'s coastal port rows, which
               # `terrain_society.py:215` extends the same list with, do not. Those can never
               # carry a deed -- `wells/countryside.candidates` skips every row whose role
               # contains `harbor` -- so they are excluded by the field only the port builder
               # writes, `sea_node`, rather than by restating the well's gate. The assertion
               # below pins that the exclusion stays exactly that narrow.
               'hamlet': {h['uid'] for h in humans.get('hamlets', []) if 'sea_node' not in h},
               'fortress': {f['uid'] for f in humans.get('fortresses', [])},
               'port': {p['id'] for p in self.world.get('fisheries', {}).get('ports', [])},
               'shrine': {s['id'] for s in self.world.get('religion', {}).get('sites', [])}}
        for person in heroes['people']:
            for deed in person['deeds']:
                self.assertIn(deed['event_id'], ids[deed['event_kind']], (person['uid'], deed))
        # The only rural rows allowed to lack the node-keyed uid are the coastal port rows,
        # which a second producer extends the list with. Without this, dropping the uid from
        # `terrain_humans.record` would shrink the resolution set above rather than emptying
        # it, and a world that happened to precipitate no reeve would still pass.
        self.assertEqual([h['id'] for h in humans.get('hamlets', []) if 'uid' not in h],
                         [h['id'] for h in humans.get('hamlets', []) if 'sea_node' in h],
                         'a generator-made hamlet lost its node-keyed uid')
        self.assertEqual([f['id'] for f in humans.get('fortresses', []) if 'uid' not in f], [],
                         'a fortress lost its node-keyed uid')
        self.assertTrue(ids['fortress'], 'seed 42 size 17 places fortresses, so the set must not be empty')
        self.assertNotIn('heroes', materialize_stage(self.world, 15))
        self.assertEqual(materialize_stage(self.world, 16)['heroes']['summary'], heroes['summary'])

    def test_generated_world_carries_a_valid_story_web_block_only_from_stage_sixteen(self):
        """The separate story-web package ran on the cast, its block validates, and the scrubber hides it earlier."""
        from icarus_sim.terrain_history import materialize_stage
        web = self.world['story_web']
        self.assertEqual(web['status'], 'ok', web.get('error'))
        validate(web, schema('story-web.schema.json'))
        heroes = self.world['heroes']
        living = {p['uid'] for p in heroes['people'] + heroes['dreads'] if p['status'] == 'living'}
        self.assertEqual({w['uid'] for w in web['webs']} | {u['uid'] for u in web['unwoven']}, living)
        self.assertTrue(web['webs'], 'seed 42 size 17 has a living cast, so it must weave someone')
        catalogue = {t['id'] for t in web['tropes']}
        for entry in web['webs']:
            self.assertIn(entry['offered'], catalogue)
            self.assertEqual(entry['offered'], entry['spokes'][0]['trope_id'])
        self.assertNotIn('story_web', materialize_stage(self.world, 15))
        self.assertEqual(materialize_stage(self.world, 16)['story_web']['summary'], web['summary'])

    def test_generated_world_carries_a_valid_npc_roster_only_from_stage_sixteen(self):
        """The roster expanded the planned staffing into people, every join resolves, and the scrubber hides it earlier."""
        from icarus_sim.terrain_history import materialize_stage
        roster = self.world['npcs']
        self.assertEqual(roster['status'], 'ok', roster.get('error'))
        validate(roster, schema('npc-roster.schema.json'))
        sites = {s['uid'] for s in roster['sites']}
        heroes = {p['uid'] for p in self.world['heroes']['people'] + self.world['heroes']['dreads']}
        self.assertTrue(roster['people'], 'seed 42 size 17 plans staffed cities, so it must hold people')
        for person in roster['people']:
            if person['site_uid'] is not None:
                self.assertIn(person['site_uid'], sites)
            if 'hero_uid' in person:
                self.assertIn(person['hero_uid'], heroes)
            else:
                self.assertIsNotNone(person['site_uid'], f"{person['uid']} is a post with no site")
        # The earmark is what a quest generator scans instead of walking the roster, so its
        # boundedness is the contract. The bound is per site on the POST-derived earmark; the
        # cast is always important and is deliberately not capped, so on a small world heroes
        # dominate the fraction and a flat percentage would be measuring the cast, not the cap.
        caps = {'capital': 6, 'medium': 4, 'small': 3, 'fortress': 2, 'hamlet': 1}
        flagged = {}
        for person in roster['people']:
            if person['important'] and 'hero_uid' not in person:
                flagged[person['site_uid']] = flagged.get(person['site_uid'], 0) + 1
        for site in roster['sites']:
            cap = caps[site['city_class']] if site['kind'] == 'city' else caps[site['kind']]
            self.assertLessEqual(flagged.get(site['uid'], 0), cap, site['uid'])
        posts = sum(s['posts'] for s in roster['sites'])
        self.assertEqual(roster['summary']['total'], posts + roster['summary']['heroes_linked'])
        self.assertNotIn('npcs', materialize_stage(self.world, 15))
        self.assertEqual(materialize_stage(self.world, 16)['npcs']['summary'], roster['summary'])

    def test_generated_world_carries_a_valid_nomads_block_only_from_stage_sixteen(self):
        """The ground classified every band, each basis names a real record, and the scrubber hides them earlier."""
        from icarus_sim.terrain_history import materialize_stage
        bands = self.world['nomads']
        validate(bands, schema('nomads.schema.json'))
        self.assertTrue(bands['groups'], 'seed 42 size 17 has ruins and leylines, so it must raise bands')
        gods = {g['id'] for g in self.world['religion']['gods']}
        ruins = {r['uid'] for r in self.world['ruins']}
        sites = {s['uid'] for s in self.world['settlements']['sites']}
        # A placed band comes from a candidate roll. A fission child descends from one and
        # is deliberately absent from `rolls`, which records what the point process
        # considered at a point rather than every band that ended up existing.
        rolled = {r['uid'] for r in bands['rolls'] if r.get('uid')}
        self.assertEqual({b['uid'] for b in bands['groups'] if not b.get('parent_uid')}, rolled)
        for band in bands['groups']:
            if band.get('parent_uid'):
                self.assertIn(band['parent_uid'], rolled, band['uid'])
        for band in bands['groups']:
            # A cult with no god bound to its school is the failure this feature exists to
            # prevent, so that join is asserted rather than assumed.
            if band['classification'] == 'cultists':
                self.assertIn(band['god_id'], gods, band['uid'])
            if band['classification'] == 'survivors':
                self.assertIn(band['basis']['ruin_uid'], ruins, band['uid'])
                # The refuge may itself have been ruined by a later age, so it resolves
                # against both collections: a uid can outlive the record it pointed at.
                self.assertIn(band['basis']['refuge_uid'], sites | ruins, band['uid'])
        for roll in bands['rolls']:
            # Empty ground is a result, not a failure.
            if not roll['eligible']:
                self.assertFalse(roll['precipitated'])
        self.assertNotIn('nomads', materialize_stage(self.world, 15))
        self.assertEqual(materialize_stage(self.world, 16)['nomads']['counts'], bands['counts'])

    def test_generated_world_carries_valid_travelling_groups_only_from_stage_sixteen(self):
        """Beasts that move, the encounter index over both sources, and the scrubber hiding them earlier."""
        from icarus_sim.terrain_history import materialize_stage
        beasts = self.world['beast_movements']
        validate(beasts, schema('beast-movements.schema.json'))
        # Three outcomes, not two: `solitary` is an irruptive group that is not swarming
        # this year, which is its normal state rather than a route that failed.
        self.assertEqual(beasts['routed'] + beasts['stranded'] + beasts['solitary'],
                         len(beasts['groups']))
        for group in beasts['groups']:
            if group['route_status'] == 'solitary':
                self.assertEqual(group['movement'], 'irruptive', group['uid'])
        for group in beasts['groups']:
            if group['movement'] == 'follower' and group['route_status'] == 'routed':
                # A follower derives its circuit; one without a host has nothing to derive
                # from and should have been reported stranded instead.
                self.assertIsNotNone(group['host_uid'], group['uid'])

        index = self.world['encounters']
        validate(index, schema('encounters.schema.json'))
        uids = ({b['uid'] for b in self.world['nomads']['groups']}
                | {g['uid'] for g in beasts['groups']})
        for entry in index['entries']:
            self.assertIn(entry['group_uid'], uids, entry['group_uid'])
        # The indices are the whole point: they must agree with a linear scan, or a
        # consumer that trusts them sees different content from one that does not.
        for month, listed in index['by_month'].items():
            scanned = [i for i, rec in enumerate(index['occupancy']) if int(month) in rec['months']]
            self.assertEqual(sorted(listed), sorted(scanned), 'by_month disagrees at month %s' % month)
        for node, listed in index['by_node'].items():
            scanned = [i for i, rec in enumerate(index['occupancy']) if rec['node'] == int(node)]
            self.assertEqual(sorted(listed), sorted(scanned), 'by_node disagrees at node %s' % node)

        for key in ('beast_movements', 'encounters'):
            self.assertNotIn(key, materialize_stage(self.world, 15))
            self.assertIn(key, materialize_stage(self.world, 16))

    def test_nomad_write_backs_are_reported_rather_than_silent(self):
        """Every write-back says what it did, and no world carries a ley queue."""
        effects = self.world['nomads']['effects']
        for key in ('leyline_edits', 'leyline_edits_hidden', 'towns_under_raid_pressure',
                    'roads_ridden', 'settlement_candidates'):
            self.assertGreaterEqual(effects[key], 0, key)
        # The pending_ley_edits queue is retired: cults of a hidden school write directly,
        # like known-school ones, because the KNOWN_SCHOOLS gate it worked around only ever
        # validated caller-supplied age-advance edits and never the world's own networks.
        self.assertNotIn('pending_ley_edits', self.world)
        for candidate in self.world.get('settlement_candidates', []):
            self.assertIn(candidate['from_band'], {b['uid'] for b in self.world['nomads']['groups']})

    def test_generated_world_carries_a_valid_villains_block(self):
        """The block two published contracts already derive from, checked against its own.

        `key-locations.schema.json` and `nomads.schema.json` describe records read out of
        `villains.people[].claims[]`, `.direction`, `.school` and `.tier`. For as long as
        this block had no contract, the repository published contracts for data derived
        from a source whose shape was unspecified: a consumer could validate the derived
        records and had nothing to validate the source against.
        """
        block = self.world['villains']
        validate(block, schema('villains.schema.json'))
        self.assertTrue(block['people'], 'a default world ends with antagonists standing in it')
        # The joins the derived contracts make, asserted rather than assumed.
        anchors = set(block['tiers'])
        for person in block['people']:
            self.assertIn(person['region'], anchors, person['uid'])
        outlook = block['outlook']
        self.assertEqual(outlook['standing'], sum(1 for row in outlook['regions'] if row['seated']))

    def test_asset_list_satisfies_its_published_schema(self):
        from fantasy_world_generator.asset_list import compile_asset_list
        validate(compile_asset_list(), schema('asset-list.schema.json'))

    def test_capabilities_document_satisfies_its_published_schema(self):
        from fantasy_world_generator.capabilities import capabilities_document
        path = ROOT / 'Contracts/schemas/capabilities.schema.json'
        if not path.is_file():
            self.skipTest('no published capabilities schema')
        validate(capabilities_document(), json.loads(path.read_text(encoding='utf-8')))

    def test_validator_reports_a_drifted_version_constant(self):
        """Guard the guard: a stale const must fail rather than pass silently."""
        drifted = schema('world-output.schema.json')
        drifted['properties']['city_plans']['properties']['version']['const'] = 4
        found = list(errors(self.world, drifted))
        self.assertTrue(any('/city_plans/version' in message for message in found), found)

    def test_every_block_this_world_carries_is_in_the_block_registry(self):
        """Emitted but unregistered. `Contracts/blocks.json` lists what a world contains.

        The envelope root is `additionalProperties: true`, so a key nobody declared
        validates silently -- nine already do. This is the direction that catches the next
        one: an emitter growing a top-level key fails here and is named, instead of arriving
        at a consumer unannounced.

        `tests/test_block_registry.py` holds the half that needs no world.
        """
        registry = json.loads((ROOT / 'Contracts/blocks.json').read_text(encoding='utf-8'))
        listed = {block['key'] for block in registry['blocks']}
        self.assertTrue(listed, 'an empty registry agrees with every world')
        unregistered = sorted(set(self.world) - listed)
        self.assertEqual(unregistered, [],
                         f'this world carries top-level keys the block registry does not list: '
                         f'{unregistered}. Add a row to Contracts/blocks.json naming the schema '
                         'that describes each, or the reason it has none.')

    def test_every_block_the_registry_does_not_call_optional_is_present(self):
        """Registered and not optional, but absent. The other direction, and the harder one.

        `optional` is the single authored column in the registry -- it is a claim about
        worlds that were not built, so nothing can derive it -- and this is what keeps it
        honest: a block that quietly stops being emitted fails here by name rather than
        leaving a consumer to discover the key is missing.
        """
        registry = json.loads((ROOT / 'Contracts/blocks.json').read_text(encoding='utf-8'))
        expected = sorted(b['key'] for b in registry['blocks'] if not b['optional'])
        self.assertTrue(expected, 'every row optional means this test asserts nothing')
        absent = [key for key in expected if key not in self.world]
        self.assertEqual(absent, [],
                         f'the registry says a world always carries these and this one does not: '
                         f'{absent}. Either the emitter stopped writing the block, or the row '
                         'should say `optional: true` and say why.')


class VillainsContractTests(unittest.TestCase):
    """The half of the villains contract a generated world does not reach.

    Deliberately in its own case with no generated world: a world at the default options
    ends with everybody standing, so `status: 'fallen'`, `fell_age`, the `villains.fallen`
    mark and a claim carrying its holder's fall are unreachable from the fixture the class
    above builds -- which is how they went unchecked against anything for as long as they
    did. Driving `terrain_villains` directly takes milliseconds, which also means this test
    can be ablated cheaply.
    """

    class Config:
        settlement_spacing = 1000.

    def fallen_world(self):
        """Seat a villain, let its region go quiet, and let the hold band take it.

        The band is the declared default, not the `hold=99.` the unit tests use as an
        instrument, so this exercises a fall a world can actually be given.
        """
        from icarus_sim import terrain_villains

        world = {
            'effective_config': {'globe_radius': 100000.},
            'settlements': {'sites': [{'id': 'site-1', 'uid': 'city-1', 'node': 7,
                                       'direction': [0., 1., 0.],
                                       'population_profile': 'human_heartland'}]},
            'humans': {'cultures': [{'id': 'culture-1', 'city_ids': ['site-1']}]},
            'magic': {'networks': {'weave': {'nodes': [{'id': 'ley-1', 'direction': [0., 1., 0.]}],
                                             'edges': []}}},
            'threat_assessments': {'cities': [{'city_uid': 'city-1', 'regional_threat': 1.,
                                               'war_risk': 0., 'war_hunger': 0., 'war_pressure': 0.,
                                               'nest_pressure': 1., 'ley_pressure': 0.}]},
        }
        cast = terrain_villains.advance(world, self.Config(), 0, rise=1., hold=.7, density=3.)
        terrain_villains.claim_settlements(world, self.Config(), cast[0], 0)
        world['threat_assessments']['cities'][0].update(regional_threat=0., nest_pressure=0.)
        for age in range(1, 21):
            terrain_villains.advance(world, self.Config(), age, rise=.5, hold=.7, density=3.)
            if not terrain_villains.standing(world['villains']['people']):
                break

        # `advance` seeds the block with an empty `outlook` and `age_transition` writes the
        # real one immediately after; this stands in for that second call, because the
        # contract describes a finished document rather than a half-built block.
        block = world['villains']
        block['outlook'] = terrain_villains.outlook(world, self.Config(), rise=.5, density=3.)
        return block

    def test_the_villains_schema_describes_a_fallen_reign_as_well_as_a_standing_one(self):
        block = self.fallen_world()
        self.assertTrue([p for p in block['people'] if p['status'] == 'fallen'],
                        'the probe never produced a fall, so it checks nothing')
        self.assertTrue(block['fallen'], 'a villain that staked a claim leaves a mark')
        self.assertEqual(block['people'][0]['claims'][0]['holder_status'], 'fallen')
        validate(block, schema('villains.schema.json'))

    def test_the_villains_schema_fails_in_the_direction_an_open_container_cannot(self):
        """Guard the guard. Every container in this contract is closed on purpose.

        An open container is what let `npc-roster`'s `summary` declare six counters
        against eight emitted with a green suite. The property this block needs is the
        reverse one: a field the emitter grows that no contract mentions must fail here,
        and that is the direction this block has never had.
        """
        block = self.fallen_world()
        block['people'][0]['menace'] = 3
        block['outlook']['regions'][0]['dread'] = True
        block['fallen'][0]['left']['curse'] = 'x'
        block['people'][0]['claims'][0]['rent'] = 1
        found = list(errors(block, schema('villains.schema.json')))
        for name in ('menace', 'dread', 'curse', 'rent'):
            self.assertTrue(any("unexpected property %r" % name in message for message in found),
                            (name, found))


if __name__ == '__main__':
    unittest.main()
