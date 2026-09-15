"""Reference-sphere land footprint and shared physical scaling across worlds."""
import math
from time import perf_counter


def land_area(h,radius,sea_level):
    n=len(h); dlat=math.pi/(n-1); dlon=2*math.pi/(n-1)
    land=0.; max_sample=0.
    for z,row in enumerate(h):
        lat=math.pi/2-z*dlat
        north=min(math.pi/2,lat+dlat/2); south=max(-math.pi/2,lat-dlat/2)
        weight=radius*radius*dlon*(math.sin(north)-math.sin(south))
        max_sample=max(max_sample,weight)
        land+=weight*sum(value>sea_level for value in row[:-1])
    total=4*math.pi*radius*radius
    return {'land_km2':land/1e6,'submerged_km2':(total-land)/1e6,
            'total_km2':total/1e6,'land_fraction':land/total,
            'largest_sample_km2':max_sample/1e6,
            'method':'latitude-weighted nodal footprint; duplicate longitude excluded; height > sea level',
            'meaning':'reference-sphere footprint, not slope surface area, connected land, or walkability'}


def apply_world_scale(result,cfg):
    """Keep input config for regeneration; expose scaled effective physical config."""
    started=perf_counter()
    if cfg.shape!='globe':
        return result
    factor=cfg.world_scale
    effective=dict(result['config'])
    for key in ('globe_radius','extent','amplitude','wavelength','depth','width','meander','radius','tectonic_relief','sea_level'):
        effective[key]*=factor
    for key in ('base','height','structure','interaction','noise','tpi','boundary_distance','continental','surface','erosion','deposition','erosion_delta','archipelago_relief'):
        if key in result['layers']:
            result['layers'][key]=[[v*factor for v in row] for row in result['layers'][key]]
    if 'catchment' in result['layers']:
        result['layers']['catchment']=[[v*factor**2 for v in row] for row in result['layers']['catchment']]
    if result.get('sediment_budget'):
        for key in ('eroded_m3','deposited_m3','stored_sediment_m3','balance_error_m3'):
            result['sediment_budget'][key]*=factor**3
    result['spacing_m']*=factor
    result['effective_tpi_radius_m']*=factor
    result['topology']['radius_m']=effective['globe_radius']
    result['effective_config']=effective
    result['physical_scale']={'factor':factor,
                             'note':'same factor for every seed; config retains design inputs; effective_config uses physical metres'}
    if not (cfg.tectonics and cfg.phase==1):
        result['area']=land_area(result['layers']['height'],effective['globe_radius'],effective['sea_level'])
        result['layers']['land']=[[int(v>effective['sea_level']) for v in row] for row in result['layers']['height']]
    elapsed=(perf_counter()-started)*1000
    result['timing_ms']['area_scale']=elapsed
    result['timing_ms']['total']+=elapsed
    from .terrain_biomes import add_terrain_labels
    from .terrain_water import add_water
    from .terrain_recipes import initialize_derivation,derive_water,derive_population,derive_institutions
    initialize_derivation(result,cfg)
    cfg=derive_water(result,cfg)
    result=add_water(result,cfg)
    from .terrain_climate import add_climate
    from .terrain_settlements import add_settlements
    result=add_climate(result,cfg)
    from .terrain_magic import add_colleges
    result=add_terrain_labels(result,cfg)
    if cfg.phase>=6 and result.get('climate'):
        extra_start=perf_counter()
        from .terrain_leyline_history import generate_networks
        from .terrain_ecology import add_environment
        from .terrain_history import add_biome_variants
        generate_networks(result,cfg)
        add_environment(result,cfg)
        add_biome_variants(result,cfg)
        elapsed=(perf_counter()-extra_start)*1000
        result['timing_ms']['world_ecology']=elapsed;result['timing_ms']['total']+=elapsed
    cfg=derive_population(result,cfg)
    from .terrain_humans import add_humans
    result=add_settlements(result,cfg)
    cfg=derive_institutions(result,cfg)
    from .terrain_seasons import add_seasonal_food
    result=add_seasonal_food(add_colleges(add_humans(result,cfg),cfg),cfg)
    if cfg.world_recipe:
        extra_start=perf_counter()
        from .terrain_society import add_world_society
        add_world_society(result,cfg)
        from .terrain_nests import add_nests
        add_nests(result,cfg)
        elapsed=(perf_counter()-extra_start)*1000
        result['timing_ms']['world_society']=elapsed;result['timing_ms']['total']+=elapsed
        from .terrain_world import registry,options
        definitions=registry();resolved={**result['config'],**options(cfg)}
        overrides={k:resolved[k] for k,v in definitions.items() if k!='seed' and resolved[k]!=v['default']}
        result.setdefault('recipe',{'version':3,'seed':cfg.seed,'overrides':overrides,'parameters':definitions,
                                   'resolved':resolved,'provenance':{k:'override' if k in overrides else 'default' for k in definitions}})
    result['generator_version']=8
    return result
