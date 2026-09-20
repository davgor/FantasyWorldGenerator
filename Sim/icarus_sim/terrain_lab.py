"""Dependency-free heightfield experiment; no gameplay or hydrology authority."""
from dataclasses import asdict, dataclass, field
from .civilization_registry import default_profile_id
import math
from time import perf_counter


@dataclass(frozen=True)
class Config:
    world_recipe: int = 0
    world_options: str = '{}'
    world_size: str = "small"
    auto_parameters: int = 0
    population_profile: str = field(default_factory=default_profile_id)
    shape: str = 'plane'
    globe_radius: float = 10000.0
    tectonics: int = 0
    phase: int = 9
    magic_enabled: int = 1
    ley_nodes: int = 10
    ley_width: float = 180.0
    magic_instability: float = 0.85
    human_magic_limit: float = 0.45
    college_count: int = 2
    hamlets_per_core: int = 3
    # A ceiling, not a count. The default sits at the bound so it never binds and
    # the generated road network decides how much route defence a world asks for.
    fortress_count: int = 1024
    support_reach: float = 1000.0
    culture_link_cost: float = 1800.0
    urban_food_demand: float = 10.0
    human_adaptation: float = 0.7
    wind_bearing: float = 90.0
    rain_passes: int = 48
    rain_strength: float = 1.0
    settlement_count: int = 6
    settlement_spacing: float = 450.0
    stubbornness: float = 0.2
    road_max_grade: float = 0.35
    bridge_cost: float = 200.0
    river_threshold_km2: float = 0.15
    erosion_passes: int = 6
    erosion_strength: float = 0.5
    temperature_offset: float = 0.0
    moisture_bias: float = 0.0
    plate_count: int = 12
    layout_variation: int = 0
    detail_variation: int = 0
    crust_bias: float = 0.0
    belt_width: float = 0.08
    tectonic_relief: float = 800.0
    mountain_detail: float = 0.65
    # Gain on collision uplift alone. The hypsometric profile puts ocean floor far
    # below continental platform, as Earth's does, so raising tectonic_relief deepens
    # basins as fast as it raises peaks. This lifts orogenic belts without touching
    # the basins, which is how a world gets mountains that answer to its oceans.
    orogeny: float = 1.0
    sea_level: float = 0.0
    world_scale: float = 0.17744123532462844
    seed: int = 42
    size: int = 129
    extent: float = 8000.0
    amplitude: float = 1400.0
    wavelength: float = 4500.0
    octaves: int = 5
    ridge: float = 0.55
    depth: float = 500.0
    width: float = 450.0
    meander: float = 650.0
    radius: float = 500.0

    def __post_init__(self):
        if type(self.world_recipe) is not int or self.world_recipe not in (0,3):
            raise ValueError('world_recipe must be 0 (geometry experiment) or 3; retired worlds must be regenerated')
        if self.world_recipe == 3 and (self.shape != 'globe' or self.tectonics != 1):
            raise ValueError('World recipe 3 requires a tectonic globe')
        if self.world_recipe and self.auto_parameters:
            raise ValueError('World recipe 3 uses explicit defaults and overrides; auto_parameters requires world_recipe 0')
        from .terrain_world import validate_options
        validate_options(self.world_options, self.world_recipe)
        if self.world_size not in ("small","medium","large"):raise ValueError("world_size must be small, medium or large")
        from .terrain_profiles import get_profile
        get_profile(self.population_profile)
        if type(self.auto_parameters) is not int or self.auto_parameters not in (0,1):raise ValueError('auto_parameters must be 0 or 1')
        for key,low,high in (('magic_enabled',0,1),('ley_nodes',3,24),('college_count',0,12)):
            if type(getattr(self,key)) is not int or not low<=getattr(self,key)<=high:raise ValueError(f'{key} must be an integer {low}..{high}')
        for key,low,high in (('ley_width',10,2000),('magic_instability',0,1),('human_magic_limit',0,1)):
            if not math.isfinite(getattr(self,key)) or not low<=getattr(self,key)<=high:raise ValueError(f'{key} must be {low}..{high}')
        for key,high in (('hamlets_per_core',8),('fortress_count',1024)):
            if type(getattr(self,key)) is not int or not 0<=getattr(self,key)<=high:
                raise ValueError(f'{key} must be an integer 0..{high}')
        for key,low,high in (('support_reach',100,100000),('culture_link_cost',1,100000),('urban_food_demand',0,10000),('human_adaptation',0,1)):
            value=getattr(self,key)
            if not math.isfinite(value) or not low<=value<=high:raise ValueError(f'{key} must be {low}..{high}')
        for key,low,high in (('wind_bearing',0,360),('rain_strength',0,3),('settlement_spacing',10,100000),
                             ('stubbornness',0,1),('road_max_grade',.01,1),('bridge_cost',0,10000)):
            value=getattr(self,key)
            if not math.isfinite(value) or not low<=value<=high:raise ValueError(f'{key} must be {low}..{high}')
        if type(self.rain_passes) is not int or not 1<=self.rain_passes<=128:raise ValueError('rain_passes must be 1..128')
        if type(self.settlement_count) is not int or not 0<=self.settlement_count<=24:raise ValueError('settlement_count must be 0..24')
        if not math.isfinite(self.river_threshold_km2) or not .001<=self.river_threshold_km2<=100:
            raise ValueError('river_threshold_km2 must be 0.001..100')
        if not math.isfinite(self.temperature_offset) or not -40<=self.temperature_offset<=40:
            raise ValueError('temperature_offset must be -40..40 C')
        if not math.isfinite(self.moisture_bias) or not -1<=self.moisture_bias<=1:
            raise ValueError('moisture_bias must be -1..1')
        if type(self.erosion_passes) is not int or not 0<=self.erosion_passes<=40:
            raise ValueError('erosion_passes must be an integer 0..40')
        if not math.isfinite(self.erosion_strength) or not 0<=self.erosion_strength<=1:
            raise ValueError('erosion_strength must be 0..1')
        if not math.isfinite(self.mountain_detail) or not 0<=self.mountain_detail<=1:
            raise ValueError('mountain_detail must be 0..1')
        if not math.isfinite(self.orogeny) or not 0<=self.orogeny<=20:
            raise ValueError('orogeny must be 0..20')
        if not math.isfinite(self.sea_level) or not -1e7<=self.sea_level<=1e7:
            raise ValueError('sea_level must be finite within ±10,000,000 metres')
        if not math.isfinite(self.world_scale) or not .001<=self.world_scale<=1000:
            raise ValueError('world_scale must be .001..1000')
        if self.shape not in ('plane', 'globe'):
            raise ValueError('shape must be plane or globe')
        if not math.isfinite(self.globe_radius) or not .01 <= self.globe_radius <= 1e7:
            raise ValueError('globe_radius must be 0.01..10,000,000 metres')
        for name in ('seed', 'size', 'octaves', 'tectonics', 'phase', 'plate_count', 'layout_variation', 'detail_variation'):
            if type(getattr(self, name)) is not int:
                raise ValueError(f'{name} must be an integer')
        if not 0 <= self.seed < 2**32:
            raise ValueError('seed must be 0..4294967295')
        if self.tectonics not in (0,1) or self.phase not in range(1,17 if self.world_recipe==3 else 10) or not 3 <= self.plate_count <= 48:
            raise ValueError('tectonics is 0 or 1; phase is 1..9 (1..16 for recipe 2); plate_count is 3..48')
        if not all(0 <= v < 2**32 for v in (self.layout_variation,self.detail_variation)):
            raise ValueError('variation seeds must be 0..4294967295')
        if not math.isfinite(self.crust_bias) or not -1 <= self.crust_bias <= 1:
            raise ValueError('crust_bias must be -1..1')
        if not math.isfinite(self.belt_width) or not .01 <= self.belt_width <= .3:
            raise ValueError('belt_width must be .01..0.3 of planet radius')
        if not math.isfinite(self.tectonic_relief) or not 0 <= self.tectonic_relief <= 1e7:
            raise ValueError('tectonic_relief must be 0..10,000,000 metres')
        if not 3 <= self.size <= 1025 or not 1 <= self.octaves <= 10:
            raise ValueError('size must be 3..1025; octaves must be 1..10')
        for name in ('extent', 'amplitude', 'wavelength', 'ridge', 'depth', 'width', 'meander', 'radius'):
            v = getattr(self, name)
            if not math.isfinite(v) or not 0 <= v <= 1e7:
                raise ValueError(f'{name} must be finite and between 0 and 10,000,000')
        if min(self.extent, self.wavelength, self.width, self.radius) <= 0 or self.ridge > 1:
            raise ValueError('extent/wavelength/width/radius must be positive; ridge must be 0..1')
        if min(self.extent, self.wavelength, self.width, self.radius) < .01:
            raise ValueError('positive distance controls must be at least 0.01 metres')
        relief_bound = (5*self.tectonic_relief if self.phase>=2 else 0) if self.tectonics else self.depth
        detail_bound = 2*self.amplitude if not self.tectonics or self.phase>=3 else 0
        if self.shape == 'globe' and detail_bound+relief_bound >= .9*self.globe_radius:
            raise ValueError('active relief budget must stay below 90% of globe radius to avoid surface inversion')


_GRADIENTS = ((1,0), (-1,0), (0,1), (0,-1),
              (2**-.5,2**-.5), (-2**-.5,2**-.5), (2**-.5,-2**-.5), (-2**-.5,-2**-.5))


def perlin(x, z, seed):
    """2D gradient noise with quintic interpolation and stable integer hashing."""
    ix, iz = math.floor(x), math.floor(z)
    fx, fz = x-ix, z-iz
    def dot(dx, dz):
        h = ((ix+dx)*374761393 + (iz+dz)*668265263 + seed*1442695041) & 0xffffffff
        h = ((h ^ (h >> 13))*1274126177) & 0xffffffff
        gx, gz = _GRADIENTS[(h ^ (h >> 16)) & 7]
        return gx*(fx-dx) + gz*(fz-dz)
    u, v = fx**3*(fx*(fx*6-15)+10), fz**3*(fz*(fz*6-15)+10)
    a, b, c, d = dot(0,0), dot(1,0), dot(0,1), dot(1,1)
    return (a+(b-a)*u)*(1-v) + (c+(d-c)*u)*v


def carve(base, cfg):
    """Controlled cross-valley profile, NOT a routed river or erosion solver.

    Distance is horizontal x offset from a sinusoidal centerline, not the
    shortest Euclidean distance. Width is cross-section half-width in metres.
    """
    step = cfg.extent/(cfg.size-1)
    result = []
    for z, row in enumerate(base):
        center = cfg.extent/2 + cfg.meander*math.sin(2*math.pi*z/(cfg.size-1))
        result.append([v-cfg.depth*max(0, 1-((x*step-center)/cfg.width)**2)**2
                       for x, v in enumerate(row)])
    return result


def measure(h, spacing, radius_cells):
    """Slope in degrees and square-neighborhood TPI in metres, O(cells).

    Interior centered differences; boundary one-sided differences. TPI windows
    clip at the region edge, so edge results lack neighboring-region context.
    """
    n = len(h)
    integral = [[0.0]*(n+1) for _ in range(n+1)]
    for z in range(n):
        acc = 0.0
        for x in range(n):
            acc += h[z][x]
            integral[z+1][x+1] = integral[z][x+1]+acc
    slopes, tpis = [], []
    for z in range(n):
        sr, tr = [], []
        loz, hiz = max(0,z-radius_cells), min(n,z+radius_cells+1)
        zm, zp = max(0,z-1), min(n-1,z+1)
        for x in range(n):
            xm, xp = max(0,x-1), min(n-1,x+1)
            gx = (h[z][xp]-h[z][xm])/((xp-xm)*spacing)
            gz = (h[zp][x]-h[zm][x])/((zp-zm)*spacing)
            sr.append(math.degrees(math.atan(math.hypot(gx,gz))))
            lox, hix = max(0,x-radius_cells), min(n,x+radius_cells+1)
            total = integral[hiz][hix]-integral[loz][hix]-integral[hiz][lox]+integral[loz][lox]
            tr.append(h[z][x]-total/((hiz-loz)*(hix-lox)))
        slopes.append(sr)
        tpis.append(tr)
    return slopes, tpis


def generate(cfg):
    if cfg.world_recipe == 3:
        from .terrain_history import generate_history
        return generate_history(cfg)
    return generate_base(cfg)


def generate_base(cfg):
    """Shared physical pipeline; history calls this only through connected water."""
    if cfg.auto_parameters and not cfg.world_recipe:
        from .terrain_recipes import seed_config
        cfg=seed_config(cfg)
    if cfg.shape == 'globe':
        from .terrain_area import apply_world_scale
        if cfg.tectonics:
            from .terrain_tectonics import generate_tectonics
            return apply_world_scale(generate_tectonics(cfg),cfg)
        from .terrain_globe import generate_globe
        return apply_world_scale(generate_globe(cfg),cfg)
    start = perf_counter()
    step = cfg.extent/(cfg.size-1)
    # Drop sub-Nyquist octaves rather than aliasing them into regional terrain.
    frequencies = [2**k/cfg.wavelength for k in range(cfg.octaves)
                   if cfg.wavelength/2**k >= 2*step]
    base = []
    for z in range(cfg.size):
        row = []
        for x in range(cfg.size):
            height = 0.0
            for k, frequency in enumerate(frequencies):
                n = perlin(x*step*frequency+.173, z*step*frequency+.391, cfg.seed+k*1013)
                ridge = (1-abs(n))**3 - .5
                height += cfg.amplitude*0.5**k*((1-cfg.ridge)*n + cfg.ridge*ridge)
            row.append(height)
        base.append(row)
    noise_end = perf_counter()
    height = carve(base, cfg)
    carve_end = perf_counter()
    radius_cells = max(1, round(cfg.radius/step))
    slope, tpi = measure(height, step, radius_cells)
    end = perf_counter()
    warnings = ['Controlled gorge only: no drainage, erosion, oceans, climate, or settlement simulation.',
                'Heightfield cannot represent caves or overhangs. TPI neighborhoods clip at region edges.']
    if len(frequencies) < cfg.octaves:
        warnings.append(f'Only {len(frequencies)}/{cfg.octaves} noise octaves resolved at this spacing; fine layers omitted.')
    if cfg.width < 3*step:
        warnings.append('Gorge half-width is under 3 cells; increase resolution before judging its shape or slopes.')
    if cfg.meander+cfg.width > cfg.extent/2:
        warnings.append('Gorge footprint leaves the region; some cross-sections are clipped.')
    return {'generator_version':1, 'config':asdict(cfg), 'spacing_m':step,
            'effective_tpi_radius_m':radius_cells*step, 'resolved_octaves':len(frequencies),
            'warnings':warnings,
            'timing_ms':{'noise':(noise_end-start)*1000, 'carve':(carve_end-noise_end)*1000,
                         'measure':(end-carve_end)*1000, 'total':(end-start)*1000},
            'layers':{'base':base, 'height':height, 'slope':slope, 'tpi':tpi}}
