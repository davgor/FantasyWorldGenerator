import unittest
from icarus_sim.terrain_nests import profiles, roles, suitability, biome_weight

PASSES=(('wildlife','animal'),('beast_nests','monster'))

class NestRulesTests(unittest.TestCase):
    def test_catalogue_coverage(self):
        import json
        from pathlib import Path
        catalogue=json.loads((Path(__file__).resolve().parents[2]/'docs/catalogue/creatures.json').read_text(encoding='utf-8'))['creatures']
        self.assertEqual({p['name'] for p in profiles()}, {p['name'] for p in catalogue})

    def test_water_and_magic_are_requirements(self):
        p=next(p for p in profiles() if p['name']=='Kraken')
        self.assertEqual(suitability(p, {'medium':'land','temperature':12})[0],0)
        p=next(p for p in profiles() if p['name']=='Glacier dragons')
        self.assertEqual(suitability(p, {'medium':'land','temperature':30})[0],0)
        self.assertEqual(suitability(p, {'medium':'land','temperature':-10})[0],0)

    def test_every_creature_is_classed_and_tiered(self):
        for p in profiles():
            self.assertIn(p['class'],('animal','monster'),p['name'])
            self.assertIn(p['tier'],(1,2,3,4,5),p['name'])
            self.assertEqual(p['class']=='animal',p['real'],p['name'])
            # A role is what an animal eats and therefore where it lives; monsters key
            # off magic and terrain instead, and carry none.
            if p['class']=='animal':self.assertIn(p['role'],roles(),p['name'])
            else:self.assertNotIn('role',p,p['name'])

    def test_biome_tables_are_range_maps(self):
        from icarus_sim.terrain_biome_catalogue import NATURAL_BIOMES
        known={str(bid) for bid in NATURAL_BIOMES}
        for role,body in roles().items():
            table=body['biome_weights']
            self.assertTrue(table,role)
            self.assertFalse(set(table)-known,role)
            for biome,weight in table.items():self.assertTrue(0<weight<=1,(role,biome))
        wolf=next(p for p in profiles() if p['name']=='Gray wolf')
        rabbit=next(p for p in profiles() if p['name']=='European rabbit')
        # The defect this redesign exists to fix: these two shared an identical rule.
        self.assertNotEqual(wolf['tier'],rabbit['tier'])
        self.assertNotEqual(wolf['role'],rabbit['role'])
        # An absent biome is ground the species does not use, not neutral ground.
        self.assertEqual(biome_weight(wolf,17),0.)

    def test_every_monster_names_every_live_biome(self):
        # A monster has no feeding role to fall back on, so before the 2026-09-20 ruling
        # every one of them scored 1.0 everywhere. They now carry their own tables --
        # and the key set has to be the whole live roster, not a subset. An absent key
        # is exclusion, not neutrality, and a hand-authored five-key table was measured
        # to forbid a quarter of the catalogue the ground it was tuned on.
        from icarus_sim.terrain_biome_catalogue import NATURAL_BIOMES
        # 1 tundra and 6 snow are overwritten by terrain_ecology.cold_habitat before any
        # nest pass runs, so no creature may claim them.
        live={str(bid) for bid in NATURAL_BIOMES}-{'1','6'}
        monsters=[p for p in profiles() if p['class']=='monster']
        self.assertTrue(monsters)
        for p in monsters:
            table=p.get('biome_weights')
            self.assertEqual(set(table or {}),live,p['name'])
            for biome,weight in table.items():self.assertTrue(0<weight<=1,(p['name'],biome))
        # Not one table, 369 of them: a family multiplier cancels within its family, so
        # a single shared shape would leave the species that own a tier owning it still.
        self.assertGreater(len({tuple(sorted(p['biome_weights'].items())) for p in monsters}),11)

    def test_danger_ramps_with_distance_instead_of_stepping(self):
        from icarus_sim.terrain_nests import danger_ramp,NEST_DANGER_FLOOR
        span=5000.
        far=[d*1000. for d in range(0,40)]
        # Tier five is drawn outward and tier one inward, monotonically, and the two
        # cross exactly once. A binary clearance can do neither.
        apex=[danger_ramp(5,d,span) for d in far]
        prey=[danger_ramp(1,d,span) for d in far]
        self.assertEqual(apex,sorted(apex))
        self.assertEqual(prey,sorted(prey,reverse=True))
        self.assertLess(apex[0],prey[0])
        self.assertGreater(apex[-1],prey[-1])
        # Nothing becomes impossible: every tier keeps a share of its rate everywhere,
        # including on ground with no settlement anywhere on the planet.
        for tier in (1,2,3,4,5):
            for d in far+[float('inf')]:
                self.assertGreaterEqual(danger_ramp(tier,d,span),NEST_DANGER_FLOOR)
                self.assertLessEqual(danger_ramp(tier,d,span),1.)
        # Tier three sits in the middle of the ramp and therefore does not move at all.
        self.assertEqual({round(danger_ramp(3,d,span),12) for d in far},{round((1+NEST_DANGER_FLOOR)/2,12)})

    def test_the_book_is_a_pyramid_too(self):
        import collections
        # A tier is a share of the world divided among its species, so the catalogue
        # itself has to be widest at the harmless end: authoring forty campaign threats
        # against twenty nuisances gives each dragon a bigger slice than each grave
        # mite, and a player meets the rare thing more often than the common one.
        for klass in ('animal','monster'):
            spread=collections.Counter(p['tier'] for p in profiles() if p['class']==klass)
            self.assertGreater(spread[1],spread[5],klass)
            self.assertGreater(spread[1]+spread[2],spread[4]+spread[5],klass)
        # Every monster family has something a novice can meet and something a
        # kingdom fears; a family authored only at the top is a boss list, not an
        # ecology.
        monsters=[p for p in profiles() if p['class']=='monster']
        for family in sorted({p['family'] for p in monsters}):
            self.assertEqual({p['tier'] for p in monsters if p['family']==family},{1,2,3,4,5},family)

    def test_the_pyramid_falls_geometrically(self):
        from icarus_sim.terrain_nests import tier_density
        for falloff in (2.,4.):
            for tier in range(2,6):
                self.assertAlmostEqual(tier_density(10.,falloff,tier)*falloff,
                                       tier_density(10.,falloff,tier-1))


def build(**overrides):
    from icarus_sim.terrain_world import generate_request
    return generate_request({'seed':42,'overrides':{'size':33,'phase':13,**overrides}})


def surface_km2(world):
    return 4*3.141592653589793*(world['effective_config']['globe_radius']/1000)**2


class NestWorldTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.world=build()
        # Three times the surface, so the population claims below have room to show a
        # shape. Expressed against whatever the default world currently is rather than a
        # fixed radius: surface goes as circumference squared, so sqrt(3) times around.
        # A hardcoded width silently became NARROWER than the default when the world
        # grew from 11 km to 200 km, which inverted this whole comparison.
        cls.wide_circumference_km=200.*3**.5
        cls.wide=build(circumference_km=cls.wide_circumference_km)

    def test_replay_and_isolation(self):
        from icarus_sim.terrain_lab import generate,Config
        a=self.world;replayed=generate(Config(**a['config']))
        for key,_ in PASSES:self.assertEqual(a[key],replayed[key])
        b=build(nest_variation=8)
        for key,_ in PASSES:self.assertNotEqual(a[key]['sites'],b[key]['sites'],key)
        for k in ['layers','sky','settlements','world_economy']:self.assertEqual(a[k],b[k])

    def test_constraints_and_finite(self):
        import json
        from icarus_sim.terrain_nests import distance
        from icarus_sim.terrain_world import options
        from icarus_sim.terrain_lab import Config
        w=self.wide;o=options(Config(**w['config']));r=w['effective_config']['globe_radius']
        pp={p['id']:p for p in profiles()}
        for key,klass in PASSES:
            sites=w[key]['sites'];self.assertTrue(sites,key)
            json.dumps(w[key],allow_nan=False)
            self.assertEqual(len({(s['layer'],s['node'],s['species_id']) for s in sites}),len(sites),key)
            for s in sites:
                self.assertEqual(s['class'],klass)
                self.assertEqual(s['real'],klass=='animal')
                self.assertGreaterEqual(s['suitability'],.3)
                self.assertGreater(s['range_m'],0)
                self.assertEqual(s['range_m'],pp[s['species_id']]['spacing_m']*o['nest_spacing']/2)
                if s['layer']=='surface':
                    wt=w['layers']['water_type'][s['z']][s['x']]
                    self.assertEqual(wt==1,pp[s['species_id']]['medium']=='marine')
                    if pp[s['species_id']]['medium'] in ['land','shore']:self.assertEqual(wt,0)
                # Clearance grows with danger, and it is folded into the intensity, so
                # it holds exactly rather than on average.
                clearance=o['nest_settlement_clearance']*s['tier']/(3 if klass=='animal' else 1)
                for t in w['settlements']['sites']:
                    self.assertGreaterEqual(distance(s['direction'],t['direction'],r)+1e-5,clearance)
            self.assertEqual(sum(d['placed'] for d in w[key]['diagnostics']),len(sites),key)

    def test_animals_are_territorial_only_within_a_species(self):
        from icarus_sim.terrain_nests import distance
        sites=self.wide['wildlife']['sites'];r=self.wide['effective_config']['globe_radius']
        crowded=0
        for i,s in enumerate(sites):
            for t in sites[i+1:]:
                if s['layer']!=t['layer']:continue
                apart=distance(s['direction'],t['direction'],r)
                if s['species_id']==t['species_id']:
                    self.assertGreaterEqual(apart+1e-5,max(s['range_m'],t['range_m']))
                elif apart<max(s['range_m'],t['range_m']):crowded+=1
        # Different species sharing ground is the map working, not a collision.
        self.assertGreater(crowded,100)

    def test_greater_monsters_hold_ground_against_equals_only(self):
        from icarus_sim.terrain_nests import distance
        sites=self.wide['beast_nests']['sites'];r=self.wide['effective_config']['globe_radius']
        nested=[]
        for i,s in enumerate(sites):
            for t in sites[i+1:]:
                if s['layer']!=t['layer']:continue
                if distance(s['direction'],t['direction'],r)>=max(s['range_m'],t['range_m']):continue
                self.assertNotEqual(s['tier'],t['tier'],(s['name'],t['name']))
                nested.append((s['tier'],t['tier']))
        # A lesser lair inside a greater territory is the feature, not a leak.
        self.assertTrue(nested)

    def test_pyramid_and_overlap(self):
        import collections
        from icarus_sim.terrain_nests import distance
        w=self.wide;r=w['effective_config']['globe_radius']
        for key,_ in PASSES:
            spread=collections.Counter(s['tier'] for s in w[key]['sites'])
            self.assertGreater(spread[1],spread[max(spread)],key)
            # The shape survives the noise of one world even where a middle tier
            # happens to draw nothing: the harmless outnumber the lethal.
            self.assertGreater(spread[1]+spread[2],2*(spread[4]+spread[5]),key)
        # The two passes never read each other, so hunting grounds and territory overlap.
        self.assertTrue(any(distance(a['direction'],m['direction'],r)<max(a['range_m'],m['range_m'])
                            for a in w['wildlife']['sites'] for m in w['beast_nests']['sites']))

    def test_population_scales_with_the_ground(self):
        # The count is an integral over habitable ground, so it tracks area rather
        # than any constant. This is the defect the redesign removed: a fixed ceiling
        # made a world thirty times emptier simply for being larger.
        area=surface_km2(self.wide)/surface_km2(self.world)
        for key,_ in PASSES:
            small=len(self.world[key]['sites']);large=len(self.wide[key]['sites'])
            self.assertTrue(.7<(large/small)/area<1.4,(key,small,large,area))

    def test_disabled_and_capped(self):
        w=build(nest_density=0)
        for key,_ in PASSES:self.assertEqual(w[key]['sites'],[],key)
        w=build(nest_fantasy=0)
        self.assertTrue(w['wildlife']['sites'])
        self.assertEqual(w['beast_nests']['sites'],[])
        # The cap is a safety valve applied per pass. It runs after placement, so it
        # keeps exactly the most notable of the anchors the world already chose.
        w=build(circumference_km=self.wide_circumference_km,nest_limit=12)
        for key,_ in PASSES:
            kept=sorted(self.wide[key]['sites'],key=lambda a:(-a['tier'],a['id']))[:12]
            self.assertEqual([a['id'] for a in w[key]['sites']],sorted(a['id'] for a in kept),key)
            self.assertEqual(sum(d['placed'] for d in w[key]['diagnostics']),12,key)
        w=build(circumference_km=self.wide_circumference_km,nest_per_species=1)
        for key,_ in PASSES:
            ids=[s['species_id'] for s in w[key]['sites']]
            self.assertTrue(ids,key)
            self.assertEqual(len(ids),len(set(ids)),key)

    def test_phase_gate(self):
        w=build(phase=6)
        self.assertNotIn('beast_nests',w)
        self.assertNotIn('wildlife',w)
