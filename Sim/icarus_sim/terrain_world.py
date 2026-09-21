"""Versioned, partial world recipes. No semantic prompt interpretation or engine I/O."""
import json
import math
from dataclasses import asdict
from functools import lru_cache
from .terrain_profiles import civilization_ids, profile_options
from .terrain_errors import (RequestError, cross_field, invalid_choice, out_of_range,
                             over_capacity, retired_version, unknown_field, wrong_type)

NETWORKS = ('weave', 'umbral', 'infernal', 'radiant', 'fire', 'water', 'earth', 'air')
# The hidden schools carry the same six options, because generate_networks reads them for
# every school in the taxonomy, but their occurrence is locked at zero: min == max == 0
# makes validate_options reject any nonzero override, so no request can raise one at
# generation. Only the corruption API puts a node in these. These names must stay in step
# with HIDDEN_SCHOOLS in terrain_leyline_history; a mismatch is a KeyError at generation,
# and test_terrain_recipes pins the two together.
HIDDEN_NETWORKS = ('blood', 'void', 'rot', 'eldritch')
ZONES = ('demonic', 'draconic', 'pirate', 'steampunk', 'witch_huts', 'red_sands',
         'dead_sea', 'starlight_lakes', 'haunted_sands', 'enchanted', 'fungal', 'crystal', 'haunted_marsh')


def spec(default, low, high, group, description, units='relative'):
    return dict(default=default, min=low, max=high, group=group,
                description=description, units=units, type='integer' if type(default) is int else 'number')


OPTIONS = {
    # Counts come from density over habitable ground, so the limit is a safety valve
    # rather than the thing that decides how full a world is: zero means systemic.
    'nest_limit': spec(0, 0, 20000, 'Beast nests', 'Hard cap on habitat anchors per pass; zero lets the ground decide', 'anchors'),
    'animal_density': spec(4.5, 0., 40., 'Beast nests', 'Tier one animal groups per square kilometre of land, and again per square kilometre of water; higher tiers follow the pyramid', 'groups/km2'),
    'monster_density': spec(.53, 0., 40., 'Beast nests', 'Tier one monster lairs per square kilometre of land, and again per square kilometre of water; higher tiers follow the pyramid', 'lairs/km2'),
    'animal_tier_falloff': spec(4., 1.5, 8., 'Beast nests', 'How much rarer each animal danger tier is than the one below it'),
    'monster_tier_falloff': spec(2., 1.5, 8., 'Beast nests', 'How much rarer each monster danger tier is; gentler than the animal pyramid so a greater lair is an event rather than a rumour, and the smallest world can still hold one', ),
    'nest_density': spec(1., 0., 3., 'Beast nests', 'Overall creature density multiplier; zero empties the world'),
    'nest_fantasy': spec(1., 0., 3., 'Beast nests', 'Monster density multiplier; zero leaves only animals'),
    'nest_per_species': spec(0, 0, 64, 'Beast nests', 'Cap on anchors for one species; zero lets density decide', 'anchors'),
    'nest_min_suitability': spec(.3, .05, .95, 'Beast nests', 'Minimum weighted habitat suitability'),
    'nest_spacing': spec(1., .25, 4., 'Beast nests', 'Same-species territory spacing multiplier'),
    'nest_settlement_clearance': spec(250., 0., 3000., 'Beast nests', 'Minimum distance from settled anchors on the same layer', 'm'),
    'nest_variation': spec(0, 0, 4294967295, 'Beast nests', 'Independent nest seed variation', 'seed'),
    'mountain_abundance': spec(1.3, .25, 2., 'Geography', 'Width of mountain collision belts relative to the legacy model'),
    'metal_abundance': spec(1., .1, 2., 'Geography', 'Overall geological metal richness multiplier'),
    'archipelago_count': spec(5, 0, 16, 'Ocean islands', 'Candidate oceanic island clusters', 'clusters'),
    'archipelago_occurrence': spec(.8, 0., 1., 'Ocean islands', 'Probability each candidate cluster manifests'),
    'islands_per_cluster': spec(5, 1, 12, 'Ocean islands', 'Islands in each manifested cluster', 'islands'),
    'island_radius': spec(.035, .008, .1, 'Ocean islands', 'Typical island radius / planet radius'),
    'island_spacing': spec(2.5, 1., 6., 'Ocean islands', 'Spacing relative to island radius'),
    'archipelago_extent': spec(1., .3, 3., 'Ocean islands', 'Cluster footprint multiplier'),
    'volcanic_island_weight': spec(1., 0., 5., 'Ocean islands', 'Relative chance of volcanic island chains'),
    'atoll_weight': spec(1., 0., 5., 'Ocean islands', 'Relative chance of reef islands and atolls'),
    'continental_island_weight': spec(1., 0., 5., 'Ocean islands', 'Relative chance of continental fragments'),
    'cold_island_weight': spec(1., 0., 5., 'Ocean islands', 'Relative chance of cold archipelagos'),
    'sky_clusters': spec(0, 0, 0, 'Sky', 'Candidate elevated archipelagos', 'clusters'),
    'sky_occurrence': spec(0., 0., 0., 'Sky', 'Probability a magically supported cluster manifests'),
    'sky_altitude': spec(450., 100., 2500., 'Sky', 'Island altitude above local ground or sea', 'm'),
    'sky_radius': spec(180., 40., 600., 'Sky', 'Typical independent island surface radius', 'm'),
    'sea_reach': spec(6000., 100., 50000., 'Transport', 'Maximum navigable sea route length', 'm'),
    'air_reach': spec(4500., 100., 50000., 'Transport', 'Maximum air route length', 'm'),
    'sea_draft': spec(1., .1, 10., 'Transport', 'Minimum navigable water depth', 'm'),
    'sea_capacity': spec(8., 0., 100., 'Transport', 'Monthly sea shipment ceiling', 'food units/month'),
    'air_capacity': spec(2., 0., 100., 'Transport', 'Monthly air shipment ceiling', 'food units/month'),
    'fish_productivity': spec(60., 0., 200., 'Coasts', 'Annual productive marine food yield', 'food units/km²/year'),
    'fishing_reach': spec(700., 50., 4000., 'Coasts', 'Ordinary coastal vessel harvesting reach', 'm'),
    'coastal_hamlets': spec(2, 0, 4, 'Coasts', 'Maximum additional coastal support hamlets per city', 'hamlets'),
    'salinity': spec(.65, 0., 1., 'Coasts', 'Arid lake salinization strength'),
    'seasonality': spec(1., 0., 2., 'Cold', 'Latitude-dependent temperature seasonality'),
    'ice_accumulation': spec(.5, 0., 1., 'Cold', 'Moisture required for persistent land ice'),
    'lunar_influence': spec(.5, 0., 1., 'Moon', 'How strongly lunar surges sway the age lottery; zero leaves the moon a spectator'),
    'war_survival': spec(0., 0., 1., 'Communities', 'Chance a defeated city survives a war as its victor\'s vassal instead of a ruin; zero keeps every loser a ruin'),
    'moon_variation': spec(0, 0, 4294967295, 'Moon', 'Independent moon seed variation', 'seed'),
    'moon_synodic_days': spec(0, 0, 34, 'Moon', 'Phase cycle in days; zero lets the seed choose 26..34', 'days'),
    'moon_spin_days': spec(0, 0, 63, 'Moon', 'Spin cycle in days (which meridian faces the world); zero lets the seed choose 15..63', 'days'),
    'moon_nod_days': spec(0, 0, 37, 'Moon', 'Nod cycle in days (which hemisphere leans in); zero lets the seed choose 17..37', 'days'),
    'moon_tilt_degrees': spec(0., 0., 35., 'Moon', 'Maximum lean of the moon toward the world; zero lets the seed choose 10..35', 'degrees'),
    # Super villains. A default world now ends with antagonists standing in it: a
    # generation runs two age transitions, and at seed 42 size 17 the most concentrated
    # region reaches tier 1.198 only at rise 1.0, so nothing below 0.834536 seats anybody
    # by accumulation alone. The rate is therefore the campaign ramp and
    # terrain_villains.promote() is the arrival, running on the final age of a generation
    # and of an advance. Zero is still a real off switch: no block is written at all.
    'villain_rise': spec(.5, 0., 1., 'Communities', "Share of a region's concentrated turmoil that becomes villain tier each age; zero raises none and writes no villains block"),
    'villain_hold': spec(.7, 0., 1., 'Communities', 'Tier a seated villain falls below to lose the world; under the rise band, so a reign is long once established'),
    'villain_density': spec(3., 1., 12., 'Communities', 'Cultural regions per villain permitted at or above the band; the rest stall just beneath it', 'regions'),
    # Nomads. Bands are placed per unit area of habitable land, so the count follows the
    # ground rather than the raster: the same world holds the same bands at any grid size.
    'nomad_occurrence': spec(1., 0., 3., 'Nomads', 'Overall multiplier on travelling bands; zero leaves the world settled'),
    'nomad_density': spec(18., 0., 200., 'Nomads', 'Candidate bands per thousand square kilometres of habitable land', 'bands/1000km2'),
    'nomad_variation': spec(0, 0, 4294967295, 'Nomads', 'Independent nomad seed variation', 'seed'),
    'beast_movement_share': spec(1., 0., 1., 'Nomads', 'Share of eligible creature sites that become travelling groups; wildlife is dense enough that routing every one is mostly volume'),
}
for name in NETWORKS + HIDDEN_NETWORKS:
    hidden = name in HIDDEN_NETWORKS
    for suffix, definition in {
        'occurrence': spec(0., 0., 0., name.title(), 'Locked at zero: a hidden school cannot manifest during generation')
                      if hidden else
                      spec(1., 0., 1., name.title(), 'Probability this magical network manifests'),
        'nodes': spec(8, 3, 24, name.title(), 'Independent ley node count', 'nodes'),
        'width': spec(110., 10., 2000., name.title(), 'Gaussian influence reach', 'm'),
        # A hidden school saturates above the known eight on purpose. At equal strength a
        # corrupted cell cannot clear dominant_school's 0.08 margin over a strong radiant
        # or earth field, so the ground would never mutate and corruption would be invisible.
        'strength': spec(1.15 if hidden else .45 if name in ('umbral','infernal') else .7, 0., 2., name.title(), 'Magical influence amplitude'),
        'instability': spec(.8 if hidden else .65 if name == 'infernal' else .2, 0., 1., name.title(), 'Instability independent of density'),
        'variation': spec(0, 0, 4294967295, name.title(), 'Independent network seed variation', 'seed'),
    }.items():
        OPTIONS[name+'_'+suffix] = definition
for name in ZONES:
    OPTIONS[name+'_occurrence'] = spec(.55, 0., 1., 'Regions', name.replace('_',' ')+' manifestation probability')
    OPTIONS[name+'_extent'] = spec(.22, .04, .8, 'Regions', name.replace('_',' ')+' angular influence radius', 'radians')
    OPTIONS[name+'_intensity'] = spec(.8, 0., 1., 'Regions', name.replace('_',' ')+' intensity')


@lru_cache(maxsize=64)
def validate_options(raw, version=3):
    if type(version) is not int or version not in (0,3):
        raise retired_version('world_options version',version,(0,3))
    definitions = OPTIONS
    try:
        values = json.loads(raw)
    except (TypeError, ValueError) as exc:
        raise RequestError('INVALID_INPUT','world_options must be a JSON object; '
                           'received text that is not valid JSON.',
                           field='world_options',received=raw) from exc
    if not isinstance(values, dict) or set(values)-set(definitions):
        raise unknown_field(sorted(set(extra)-set(OPTIONS))[0],OPTIONS,noun='world option')
    result = {key: item['default'] for key,item in definitions.items()}
    for key,value in values.items():
        s=definitions[key]
        if type(value) not in (int,float) or not math.isfinite(value) or not s['min']<=value<=s['max']:
            raise out_of_range(key,value,s)
        if s['type']=='integer' and type(value) is not int:
            raise wrong_type(key,value,s)
        result[key]=value
    if sum(result[k] for k in ('volcanic_island_weight','atoll_weight','continental_island_weight','cold_island_weight'))<=0:
        raise cross_field('At least one ocean island character weight must be positive; '
                          'all four are zero, so no cluster can take a character.',
                          ('volcanic_island_weight','atoll_weight',
                           'continental_island_weight','cold_island_weight'))
    return result


def options(cfg):
    return validate_options(cfg.world_options, cfg.world_recipe)


def default_config(version=3):
    if type(version) is not int or version != 3:
        raise retired_version('recipe version',version,(3,))
    from .terrain_lab import Config
    return Config(world_recipe=version, phase=16 if version==3 else 9, shape='globe', tectonics=1, auto_parameters=0,
                  population_profile='mixed', amplitude=1100., wavelength=4300.,
                  magic_instability=.45, belt_width=.08, settlement_count=24)


# Physical distance around the world for each world_size preset. These replace the old
# design-radius multipliers (1x/2x/3x of 10000), which produced 11/22/33 km worlds -- too
# small to hold a capital, let alone the multi-layer cities, and small enough that 142 m
# of relief read as a spike field rather than terrain.
WORLD_SIZE_CIRCUMFERENCE_KM={'small':200.,'medium':400.,'large':600.}
# Relief budget and collision gain behind the presets. Relief stays constant across the
# three sizes rather than scaling with circumference: at 200 km, 4 km peaks are already a
# hundred times Earth's relief-to-circumference ratio, and scaling that linearly would put
# 12 km walls on the large world. A larger world therefore means more land, not taller
# mountains. Ground-level drama is the detail sampler's job, not the relief budget's.
DEFAULT_RELIEF_M=1667.
DEFAULT_OROGENY=10.
# Largest catchment threshold `terrain_lab.Config` and `registry()` admit. The recipe
# default 0.15 km2 is authored for the 11.15 km reference world and scales as the square
# of the width, so this bound is what decides the widest world the recipe can resolve:
# 0.15*(c/11.148961626795008)**2 reaches 10000 km2 at 2878.6 km. The three presets need
# 48.27, 193.08 and 434.44 km2, so all of them clear it with two orders of magnitude to
# spare. Raise both this and the Config bound together if a wider world is ever wanted.
RIVER_THRESHOLD_MAX_KM2=10000.
RIVER_THRESHOLD_MAX_CIRCUMFERENCE_KM=2878.6
# Largest reach `terrain_lab.Config` and `registry()` admit for the three distances that
# scale with the world's width. Unlike the catchment above, the binding width differs per
# key because each has its own reference-world base: 450 m settlement_spacing binds at
# 2477.55 km, 1000 m support_reach at 1114.90 km and 1800 m culture_link_cost at 619.39 km
# -- 3.13% above the 600 km large preset, which is why the silent clamp that used to live
# here was a defect waiting on one authored world rather than a safety net.
REACH_MAX_M=100000.


# Every published control's unit and description, in one table so a control cannot ship
# with a bound and no meaning. `registry()` asserts the table is total, so adding a knob
# without saying what it does fails at import rather than reaching a consumer.
#
# The audience is the packaged orchestrator: a local model handed a player's intent that
# has to choose a control and a value without a second call. Describe the effect on the
# world, not the field.
CONTROL_PROSE={
 # World shape and identity.
 'seed':('seed','Master uint32 seed. Every subsystem derives its own stream from this, so one seed reproduces the whole world; the *_variation controls reroll a single layer without disturbing the rest.'),
 'size':('cells','Sampling grid along one edge of the sphere. This is a content control as much as a detail control: settlement count tracks cells rather than land area, so raising it yields a fuller world rather than the same world sampled finer.'),
 'phase':('stage','How far through the sixteen generation stages to run. A lower phase stops early and omits every block a later stage would have written.'),
 'shape':('','World topology. Recipe 3 requires a globe.'),
 'world_size':('','Preset physical scale: small, medium or large, resolving to 200, 400 or 600 km of circumference. Sets globe_radius and the terms derived from it unless circumference_km or an explicit override is supplied.'),
 'world_scale':('ratio','Design-space to metre conversion for the heightfield. Rescales the planet geometry without changing which world the seed draws.'),
 'globe_radius':('m','Planet radius in design space. Derived from the physical width; setting it directly bypasses circumference_km and the world_size preset entirely.'),
 'radius':('m','Feature radius for the retired non-tectonic experiment path; recipe 3 does not read it.'),
 'population_profile':('','Which civilization founds the first cities, or mixed to let every eligible profile compete for ground.'),
 # Terrain.
 'plate_count':('plates','Tectonic plates the globe is divided into. Fewer means wider continents and longer collision belts; more means a fragmented world. It also sets the detail wavelength, so with grid size it decides how many noise octaves can resolve.'),
 'layout_variation':('seed','Rerolls plate layout and crust distribution without changing the master seed, so the same world can be given a different continental arrangement.'),
 'detail_variation':('seed','Rerolls surface noise without changing the master seed or the continents beneath it.'),
 'crust_bias':('relative','Shifts the continental against oceanic balance of newly drawn crust. Negative sinks more of the world under ocean; positive raises more land.'),
 'belt_width':('radius fraction','Angular half-width of the collision belts raised where plates meet. Wider belts give broad cordillera; narrow ones give sharp isolated ranges.'),
 'tectonic_relief':('m','Total relief budget from ocean floor to continental platform. The hypsometric profile puts the floor far below the platform, so raising this deepens basins as fast as it raises peaks.'),
 'mountain_detail':('relative','How strongly collision uplift is modulated along and across a belt. Higher values break a smooth ridge into distinct massifs.'),
 'orogeny':('gain','Gain on collision uplift alone. Unlike tectonic_relief it lifts orogenic belts without deepening the basins, which is how a world gets mountains that answer to its oceans.'),
 'sea_level':('m','Datum offset applied to the finished heightfield. Raising it drowns coastline; lowering it exposes shelf.'),
 'amplitude':('m','Peak-to-trough amplitude of the surface noise laid over the tectonic base.'),
 'wavelength':('m','Base wavelength of the surface noise. Octave k is admitted only while wavelength/2**k stays at least twice the cell step, so this and grid size together decide how much detail survives.'),
 'octaves':('octaves','How many halvings of the base wavelength to accumulate. Octaves finer than the grid can represent are discarded rather than aliased; resolved_octaves reports how many survived.'),
 'ridge':('relative','Blends the surface noise between rounded hills at 0 and sharp ridgelines at 1.'),
 # Climate.
 'temperature_offset':('C','Uniform shift applied to the latitude and elevation temperature model. Negative cools the whole world toward ice.'),
 'moisture_bias':('relative','Uniform shift applied to modelled rainfall before biomes are classified. Negative dries the world toward desert.'),
 'wind_bearing':('degrees','Prevailing wind direction carrying moisture inland, clockwise from north.'),
 'rain_passes':('passes','How many transport steps the rainfall model takes. More passes carry moisture further inland and sharpen rain shadows.'),
 'rain_strength':('relative','Multiplier on the moisture each transport pass carries.'),
 # Drainage.
 'erosion_passes':('passes','How many hydraulic erosion steps run over the finished heightfield.'),
 'erosion_strength':('relative','How much material each erosion pass moves.'),
 'river_threshold_km2':('km2','Upstream catchment a cell must drain before it counts as a river. It is an area, so it scales as the square of world width; left absolute on a wide world every land cell becomes a river and freshwater distance collapses to zero everywhere.'),
 # Communities.
 'college_count':('colleges','Maximum magical colleges seated across the world.'),
 'hamlets_per_core':('hamlets','Maximum support hamlets packed around each core city.'),
 'human_magic_limit':('relative','Highest magical hazard a road or settlement tolerates. Ground above it is routed around and never settled.'),
 'support_reach':('m','How far a city reaches for the rural land feeding it. Authored against the reference world and scaled with world width.'),
 'culture_link_cost':('m','Road cost budget within which two cities count as one cultural region.'),
 'settlement_spacing':('m','Minimum separation enforced between founded cities.'),
 'road_max_grade':('grade','Steepest gradient a road segment may climb. Steeper ground is routed around or left unconnected.'),
 'bridge_cost':('cost','Extra traversal cost charged when a road segment crosses a river.'),
 # Read only by the retired automatic-parameter path, which recipe 3 forbids at
 # terrain_lab.Config.__post_init__. It validates, it is published, and it changes
 # nothing. Say so rather than letting a caller spend a request finding out.
 # Flags and ceilings. The two counts carried a description and no unit, set ad hoc after
 # the table was built; they live here now so every control is described in one place.
 'tectonics':('flag','Whether plate tectonics run. Recipe 3 requires them, so this is fixed at 1 and rejects any other value.'),
 'magic_enabled':('flag','Whether leylines, magical biomes and every system reading them run at all. Zero yields a mundane world.'),
 'settlement_count':('cities','Maximum surface cities; actual counts require habitat and productive capacity.'),
 'fortress_count':('fortresses','Maximum route-defence fortresses; road length, crossings and city count ask for fewer unless this is lowered.'),
 'stubbornness':('relative','Willingness to settle difficult ground. Read only by the retired automatic-parameter path, which recipe 3 forbids, so on this recipe the control is accepted and has no effect.'),
}
# The thirteen regional characters share one shape: occurrence decides whether a region
# appears, extent how far it reaches, intensity how strongly it reads once placed.
for _zone in ZONES:
    CONTROL_PROSE[_zone+'_intensity']=('relative','How strongly the '+_zone.replace('_',' ')
        +' character is expressed where it manifests. Paired with '+_zone+'_occurrence, which '
        'decides whether it appears at all, and '+_zone+'_extent, which sets how far it reaches.')


def registry(version=3):
    cfg=asdict(default_config(version))
    inactive={'world_recipe','world_options','auto_parameters','ley_nodes','ley_width','magic_instability',
              'extent','depth','width','meander','urban_food_demand','human_adaptation'}
    result={k:dict(default=v,group='World',description='',
                   type='integer' if type(v) is int else 'number' if type(v) is float else 'string',units='')
            for k,v in cfg.items() if k not in inactive}
    for key,choices in {'world_size':['small','medium','large'], 'shape':['globe'],
                        'population_profile':['mixed',*civilization_ids()]}.items():
        result[key]['choices']=choices
    result['population_profile']['choice_labels']={p['id']:p['name'] for p in profile_options()}
    # Authored world shape. These are not Config fields: they are consumed by the request
    # builder, which derives globe_radius, tectonic_relief, amplitude and wavelength from
    # them. Zero keeps the world_size preset, so every existing request is unaffected.
    result['circumference_km']={'default':0.,'group':'World','type':'number','units':'km',
        'description':'Physical distance around the world; zero keeps the world_size preset'}
    result['relief_m']={'default':0.,'group':'World','type':'number','units':'m',
        'description':'Physical relief budget from ocean floor to continental platform; zero keeps the tectonic_relief default'}
    bounds={'seed':(0,4294967295),'size':(3,1025),'phase':(1,16 if version==3 else 9),'tectonics':(1,1),'magic_enabled':(0,1),
            'circumference_km':(0,100000),'relief_m':(0,1e6),
            'plate_count':(3,48),'layout_variation':(0,4294967295),'detail_variation':(0,4294967295),
            'crust_bias':(-1,1),'belt_width':(.01,.3),'mountain_detail':(0,1),'temperature_offset':(-40,40),
            'moisture_bias':(-1,1),'wind_bearing':(0,360),'rain_passes':(1,128),'rain_strength':(0,3),
            'erosion_passes':(0,40),'erosion_strength':(0,1),'ley_nodes':(3,24),'ley_width':(10,2000),
            'magic_instability':(0,1),'human_magic_limit':(0,1),'college_count':(0,12),
            'hamlets_per_core':(0,8),'fortress_count':(0,1024),'settlement_count':(0,24),
            'support_reach':(100,100000),'culture_link_cost':(1,100000),'urban_food_demand':(0,10000),
            'human_adaptation':(0,1),'settlement_spacing':(10,100000),'stubbornness':(0,1),
            'road_max_grade':(.01,1),'bridge_cost':(0,10000),'river_threshold_km2':(.001,10000),
            'world_scale':(.001,1000),'globe_radius':(.01,1e7),'extent':(.01,1e7),
            'amplitude':(0,1e7),'wavelength':(.01,1e7),'depth':(0,1e7),'width':(.01,1e7),
            'meander':(0,1e7),'radius':(.01,1e7),'tectonic_relief':(0,1e7),'sea_level':(-1e7,1e7),
            'ridge':(0,1),'octaves':(1,10),'orogeny':(0,20)}
    for key,(low,high) in bounds.items():
        if key in result:result[key].update(min=low,max=high)
    for group,keys in {'Terrain':'plate_count layout_variation detail_variation crust_bias belt_width tectonic_relief mountain_detail orogeny sea_level amplitude wavelength octaves ridge radius world_scale',
                       'Climate':'temperature_offset moisture_bias wind_bearing rain_passes rain_strength',
                       'Drainage':'erosion_passes erosion_strength river_threshold_km2',
                       'Communities':'population_profile human_magic_limit college_count hamlets_per_core fortress_count support_reach culture_link_cost settlement_count settlement_spacing stubbornness road_max_grade bridge_cost'}.items():
        for key in keys.split():result[key]['group']=group
    result.update(OPTIONS)
    # Prose last, so it wins over whatever a definition carried, and total, so a control
    # added without a description fails here instead of reaching a consumer as its own name.
    for key,(units,description) in CONTROL_PROSE.items():
        if key in result:
            result[key]['description']=description
            if units:result[key]['units']=units
    undescribed=sorted(k for k,v in result.items() if not v.get('description'))
    if undescribed:
        raise ValueError('controls published with no description: '+', '.join(undescribed)
                         +'. Add them to CONTROL_PROSE; a control whose description is its '
                         'own name tells a caller nothing it did not already have.')
    return result


def generate_request(body):
    from .terrain_lab import Config, generate
    if not isinstance(body,dict) or set(body)-{'seed','recipe_version','overrides'}:
        if isinstance(body,dict):
            raise unknown_field(sorted(set(body)-{'seed','recipe_version','overrides'})[0],
                                ('seed','recipe_version','overrides'),noun='request field')
        raise RequestError('INVALID_INPUT','A generate request is an object with seed, '
                           'recipe_version and optional overrides.',received=type(body).__name__)
    if type(body.get('recipe_version',3)) is not int or body.get('recipe_version',3) != 3:
        raise retired_version('recipe_version',body.get('recipe_version'),(3,))
    version=body.get('recipe_version',3)
    option_defs=OPTIONS
    seed=body.get('seed',42)
    if type(seed) is not int:
        raise wrong_type('seed',seed,{'type':'integer'})
    if not 0<=seed<2**32:
        raise out_of_range('seed',seed,{'type':'integer','min':0,'max':4294967295,'units':'seed'})
    overrides=body.get('overrides',{})
    if not isinstance(overrides,dict):
        raise wrong_type('overrides',overrides,{'type':'object'})
    definitions=registry(version)
    if set(overrides)-set(definitions):
        raise unknown_field(sorted(set(overrides)-set(definitions))[0],definitions)
    if 'seed' in overrides:
        raise RequestError('INVALID_INPUT','Supply seed at the top level of the request, '
                           'not inside overrides.',field='seed',received=overrides['seed'],
                           expected={'location':'request root'},
                           suggestion={'kind':'none'})
    raw=asdict(default_config(version)); extra={}; definitions=registry(version)
    for key,value in overrides.items():
        definition=definitions[key]
        kind=definition['type']
        if kind=='string':
            if not isinstance(value,str):raise wrong_type(key,value,definition)
            if 'choices' in definition and value not in definition['choices']:
                raise invalid_choice(key,value,definition)
        else:
            if type(value) not in (int,float) or not math.isfinite(value):
                raise wrong_type(key,value,definition)
            if kind=='integer' and type(value) is not int:raise wrong_type(key,value,definition)
            if not definition.get('min',-math.inf)<=value<=definition.get('max',math.inf):
                raise out_of_range(key,value,definition)
        if key in option_defs:extra[key]=value
        else:raw[key]=value
    raw['seed']=seed
    # Authored world shape. Physical circumference and relief in, design-space radius and
    # relief out, including the wavelength that Core/genesis.cpp:148-167 never derives --
    # leave it fixed and a world past about 150 km resolves no surface noise at all.
    # An explicit globe_radius still bypasses all of this, and an explicit override of any
    # derived key wins, so a width can be authored and one term hand-tuned.
    circumference=raw.pop('circumference_km',0.)*1000.;relief=raw.pop('relief_m',0.)
    if circumference<=0 and 'globe_radius' not in overrides:
        circumference=WORLD_SIZE_CIRCUMFERENCE_KM.get(raw['world_size'],WORLD_SIZE_CIRCUMFERENCE_KM['small'])*1000.
    if circumference>0:
        from .terrain_scale import shape_overrides
        derived=shape_overrides(circumference,relief or DEFAULT_RELIEF_M,
                                raw['orogeny'] if 'orogeny' in overrides else DEFAULT_OROGENY,
                                raw['plate_count'],raw['world_scale'])
        for key in ('globe_radius','tectonic_relief','amplitude','wavelength','orogeny'):
            if key not in overrides:raw[key]=derived[key]
        # Distances that decide how far a city reaches are authored against the reference
        # world and have to grow with it. derive_population would have scaled them, but it
        # is unreachable on recipe 3 (auto_parameters is forbidden there), so they are
        # derived here instead. Left absolute, the rural layer disappears completely.
        from .terrain_scale import reach_scale,runoff_scale,REFERENCE_CIRCUMFERENCE_M
        factor=reach_scale(circumference)
        # Do NOT clamp, for the same reason river_threshold_km2 below does not. The old
        # min(REACH_MAX_M, raw*factor) was the min(<absolute>,<relative>) arm swap this
        # block exists to undo: past the width where the ceiling binds, the reach stops
        # growing with the planet, silently, and cultural regions quietly stop scaling
        # while everything around them keeps going. It was one preset from firing --
        # culture_link_cost resolves 96870.01 m at the 600 km large preset, 3.13% below
        # the ceiling, so a world authored at 620 km would have hit it. Each key binds at
        # REACH_MAX_M/base reference circumferences: 2477.55 km for settlement_spacing,
        # 1114.90 km for support_reach, 619.39 km for culture_link_cost. Below those
        # widths this is bit-for-bit what the clamp produced, because min() of a value
        # under the ceiling returns that value itself: no generated world moves.
        for key in ('settlement_spacing','support_reach','culture_link_cost'):
            if key in overrides:continue
            base=raw[key];scaled=base*factor
            if scaled>REACH_MAX_M:
                binds_km=REACH_MAX_M/base*REFERENCE_CIRCUMFERENCE_M/1000. if base>0 else 0.
                raise RequestError(
                    'STATE_CAPACITY',
                    f'A {circumference/1000:g} km world resolves {key} to {scaled:g} m, '
                    f'above the {REACH_MAX_M:g} m maximum; widths above {binds_km:.0f} km '
                    f'need that bound raised in terrain_lab.Config and in registry(), or '
                    f'an explicit {key} override',
                    field=key,received=scaled,
                    expected={'max':REACH_MAX_M,'max_circumference_km':binds_km},
                    suggestion={'kind':'clamp','value':REACH_MAX_M})
            raw[key]=scaled
        # river_threshold_km2 is an AREA, not a reach, so it takes the SQUARE of the same
        # factor. Left absolute it stopped spanning anything: at the 200 km default every
        # land cell drains more than 0.15 km2, so every land cell is a river, every land
        # cell is its own freshwater source, freshwater_distance is 0 across all land and
        # flood_risk saturates at 1. Three published layers had become constants.
        #
        # TARGET this was calibrated to: a land-river fraction that is neither saturated
        # nor empty at sizes 17, 33 and 65, and that does not drift with world width.
        # Measured (phase 9, seed 42, land-river fraction at 17/33/65):
        #     0.15 km2 unscaled, 200/400/600 km:  100/99.6/85.2, 100/100/93.8, 100/100/96.6
        #     scaled,            200/400/600 km:  68.1/47.8/16.0 at ALL THREE widths
        # Width-invariance is exact because runoff follows cell area exactly at a fixed
        # raster (measured ratios 4.000000 and 9.000000 at 2x and 3x width). See
        # terrain_scale.runoff_scale for the measurement and for what is NOT claimed.
        #
        # Re-derive rather than transcribe: sweeping the factor at 200 km gives 17/33/65
        # fractions of 91.5/63.8/33.1 at 100x, 78.7/53.7/21.8 at 220x, 68.1/47.8/16.0 at
        # the 321.8x this resolves, 59.6/29.9/0.9 at 1000x and 2.1/0.0/0.0 at 10000x. The
        # band that satisfies the target at every raster is roughly 100x to 1000x.
        if 'river_threshold_km2' not in overrides:
            scaled=raw['river_threshold_km2']*runoff_scale(circumference)
            # Do NOT clamp. A silent ceiling here is the same defect class being fixed:
            # it would quietly stop scaling past a width and re-saturate the rivers.
            if scaled>RIVER_THRESHOLD_MAX_KM2:
                raise RequestError(
                    'STATE_CAPACITY',
                    f'A {circumference/1000:g} km world resolves river_threshold_km2 to '
                    f'{scaled:g} km2, above the {RIVER_THRESHOLD_MAX_KM2:g} km2 maximum; '
                    f'widths above {RIVER_THRESHOLD_MAX_CIRCUMFERENCE_KM:.0f} km need that '
                    f'bound raised in terrain_lab.Config and in registry(), or an explicit '
                    f'river_threshold_km2 override',
                    field='river_threshold_km2',received=scaled,
                    expected={'max':RIVER_THRESHOLD_MAX_KM2,
                              'max_circumference_km':RIVER_THRESHOLD_MAX_CIRCUMFERENCE_KM},
                    suggestion={'kind':'clamp','value':RIVER_THRESHOLD_MAX_KM2})
            raw['river_threshold_km2']=scaled
    elif relief>0:
        raise cross_field('relief_m needs circumference_km; a relief budget alone cannot '
                          'size a world. Give both, or neither and take the world_size preset.',
                          ('relief_m','circumference_km'))
    # Explicit requests for stronger regions bias prerequisites. Direct prerequisite
    # overrides always win, and the original requested overrides remain auditable.
    biases={}
    prerequisites={'draconic':('mountain_abundance',.6),'demonic':('infernal_strength',.8),
                   'haunted_sands':('umbral_strength',.8),'steampunk':('metal_abundance',.7),
                   'dead_sea':('salinity',.6),'starlight_lakes':('weave_strength',.6),
                   'pirate':('archipelago_occurrence',.4),'red_sands':('moisture_bias',-.5)}
    for zone,(target,gain) in prerequisites.items():
        delta=max([float(overrides[k])-OPTIONS[k]['default'] for k in (zone+'_occurrence',zone+'_intensity') if k in overrides]+[0.])
        if delta>0 and target not in overrides:
            s=definitions[target];value=max(s['min'],min(s['max'],s['default']+delta*gain))
            if target in option_defs:extra[target]=value
            else:raw[target]=value
            biases[target]={'value':value,'source':zone+' request biases suitable conditions; placement remains conditional'}
    if raw['shape']!='globe' or raw['tectonics']!=1:
        raise cross_field('Recipe 3 requires a tectonic globe: shape must be globe and '
                          'tectonics must be 1.',('shape','tectonics'))
    # 257 stays the INTERACTIVE ceiling (tools/terrain_lab.py), not the world's: larger
    # grids are for offline worlds and cost roughly the square of the size. Age
    # advancement accepts the same 1025 generation does, so a world can hold both its
    # history and all five of its noise octaves.
    #
    # Octave admission needs step <= wavelength/2^k, and the globe radius cancels out of
    # that comparison -- wavelength is radius*1.6/sqrt(plate_count) and step is
    # 2*pi*radius/(n-1), so wavelength/step = 1.6*(n-1)/(2*pi*sqrt(plate_count)). It is a
    # function of grid size and plate count only, identical on an 11 km world and a 200 km
    # one, and apply_world_scale scales radius and wavelength together so it survives
    # scaling. Do not restate it as a metre figure for one planet: a reader on another
    # radius recomputes and gets crossovers this generator will never produce for them.
    #
    # The ladder depends on plate_count, so name the band rather than "the default".
    # Swept over the legal range 3..48 with terrain_scale.resolved_octaves:
    #
    #   plate_count    17   33   65  129  257  513  1025   octaves of 5
    #        3-4        1    2    3    4    5    5     5
    #        5-16       0    1    2    3    4    5     5   <- contains the default 12
    #       17-48       0    0    1    2    3    4     5
    #
    # 34 of the 46 legal plate counts do not follow the middle row, a full octave either
    # way at the ends. In the default band 513 resolves everything and 1025 only buys a
    # finer cell step at four times the cells -- but above plate_count 16, 513 stops at
    # four and 1025 is the first size that resolves all five. So "1025 adds no octave" is
    # true for the default and false for most of the legal range.
    if type(raw['size']) is not int:
        raise wrong_type('size',raw['size'],{'type':'integer'})
    if raw['size']>1025:
        raise over_capacity('size',raw['size'],1025,'grid')
    raw['world_options']=json.dumps(extra,sort_keys=True)
    cfg=Config(**raw)
    result=generate(cfg)
    result['recipe']={'version':version,'seed':seed,'overrides':overrides,
                      'resolved':{**asdict(cfg),**options(cfg)},'parameters':registry(version),
                      'provenance':{k:'override' if k in overrides else 'default' for k in registry(version)}}
    result['recipe']['biases']=biases
    for key,item in biases.items():result['recipe']['provenance'][key]=item['source']
    if 'globe_radius' not in overrides and raw['world_size']!='small':result['recipe']['provenance']['globe_radius']='world_size preset'
    result['recipe']['provenance']['seed']='request'
    return result
