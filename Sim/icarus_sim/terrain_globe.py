"""Spherical terrain sampled in Cartesian space; latitude/longitude export grid."""
from dataclasses import asdict
import math
from time import perf_counter


def direction(x, z, n):
    if z == 0:
        return (0., 1., 0.)
    if z == n-1:
        return (0., -1., 0.)
    lon = 2*math.pi*(x % (n-1))/(n-1)-math.pi
    lat = math.pi/2-math.pi*z/(n-1)
    return (math.cos(lat)*math.cos(lon), math.sin(lat), math.cos(lat)*math.sin(lon))


_INV_ROOT2 = 2**-.5


def perlin3(x, y, z, seed):
    # Millions of calls per world, so the corner hash and the blend weights are
    # built up incrementally instead of from scratch in the innermost loop. The
    # integer sums and the left-to-right float products are the same ones the
    # straightforward form evaluates, so results are bit-for-bit identical.
    ix, iy, iz = math.floor(x), math.floor(y), math.floor(z)
    f0, f1, f2 = x-ix, y-iy, z-iz
    b0 = f0**3*(f0*(f0*6-15)+10)
    b1 = f1**3*(f1*(f1*6-15)+10)
    b2 = f2**3*(f2*(f2*6-15)+10)
    weight0 = (1-b0, b0); weight1 = (1-b1, b1); weight2 = (1-b2, b2)
    hash_x = ix*374761393; hash_y = iy*668265263; hash_z = iz*2147483647 + seed*1442695041
    value = 0.
    for a in (0, 1):
        hash_a = hash_x + a*374761393 + hash_y
        offset0 = f0-a
        blend_a = weight0[a]
        for b in (0, 1):
            hash_b = hash_a + b*668265263 + hash_z
            offset1 = f1-b
            blend_ab = blend_a*weight1[b]
            for c in (0, 1):
                h = (hash_b + c*2147483647)&0xffffffff
                h = ((h^(h>>13))*1274126177)&0xffffffff
                h ^= h>>16
                # Twelve unit edge gradients of a cube.
                axis = h % 3
                u, v = (axis+1)%3, (axis+2)%3
                offsets = (offset0, offset1, f2-c)
                dot = (offsets[u]*(1 if h&4 else -1)+offsets[v]*(1 if h&8 else -1))*_INV_ROOT2
                value += dot*(blend_ab*weight2[c])
    return value


def sample(h, p):
    n = len(h)
    x = ((math.atan2(p[2],p[0])+math.pi)/(2*math.pi)*(n-1)) % (n-1)
    z = (math.pi/2-math.asin(max(-1,min(1,p[1]))))/math.pi*(n-1)
    z = max(0,min(n-1,z))
    ix, iz = int(x), int(z)
    fx, fz = x-ix, z-iz
    jz = min(n-1,iz+1)
    return ((1-fx)*h[iz][ix]+fx*h[iz][ix+1])*(1-fz)+((1-fx)*h[jz][ix]+fx*h[jz][ix+1])*fz


def measure_globe(h, radius, neighborhood):
    """Reference-sphere grade and eight-point geodesic-ring TPI approximation.

    Samples interpolated heights along great circles, avoiding pole singularities.
    This is a ring mean, not the planar square-area mean or an area-weighted cap.
    """
    n = len(h)
    angle = math.pi/(n-1)
    ring = min(math.pi/2,max(angle,neighborhood/radius))
    slope, tpi = [], []
    for z in range(n):
        sr, tr = [], []
        for x in range(1 if z in (0,n-1) else n-1):
            p = direction(x,z,n)
            norm = math.hypot(p[0],p[2])
            e = (-p[2]/norm,0,p[0]/norm) if norm > 1e-10 else (1,0,0)
            v = (p[1]*e[2]-p[2]*e[1],p[2]*e[0]-p[0]*e[2],p[0]*e[1]-p[1]*e[0])
            def around(theta, azimuth):
                c, s = math.cos(theta), math.sin(theta)
                ca, sa = math.cos(azimuth), math.sin(azimuth)
                return sample(h, tuple(p[j]*c+(e[j]*ca+v[j]*sa)*s for j in range(3)))
            gx = (around(angle,0)-around(angle,math.pi))/(2*radius*angle)
            gy = (around(angle,math.pi/2)-around(angle,3*math.pi/2))/(2*radius*angle)
            sr.append(math.degrees(math.atan(math.hypot(gx,gy))))
            tr.append(h[z][x]-sum(around(ring,j*math.pi/4) for j in range(8))/8)
        if z in (0,n-1):
            sr, tr = sr*n, tr*n
        else:
            sr.append(sr[0]); tr.append(tr[0])
        slope.append(sr); tpi.append(tr)
    return slope, tpi


def generate_globe(cfg):
    start = perf_counter()
    r, n = cfg.globe_radius, cfg.size
    step = 2*math.pi*r/(n-1)  # largest longitudinal spacing (equator)
    frequencies = [2**k/cfg.wavelength for k in range(cfg.octaves) if cfg.wavelength/2**k >= 2*step]
    base, height = [], []
    for z in range(n):
        row = []
        for x in range(1 if z in (0,n-1) else n-1):
            p = direction(x,z,n)
            value = 0.
            for k,f in enumerate(frequencies):
                noise = perlin3(p[0]*r*f+.173,p[1]*r*f+.391,p[2]*r*f+.719,cfg.seed+k*1013)
                value += cfg.amplitude*.5**k*((1-cfg.ridge)*noise+cfg.ridge*((1-abs(noise))**3-.5))
            row.append(value)
        row = row*n if z in (0,n-1) else row+[row[0]]
        base.append(row)
    noise_end = perf_counter()
    for z,row in enumerate(base):
        lat = math.pi/2-math.pi*z/(n-1)
        carved = []
        for x,value in enumerate(row):
            lon = 2*math.pi*(x%(n-1))/(n-1)-math.pi
            # Smooth periodic latitude-band gorge. Not a drainage channel.
            offset = r*lat-cfg.meander*math.sin(2*lon)*math.cos(lat)**2
            carved.append(value-cfg.depth*max(0,1-(offset/cfg.width)**2)**2)
        if z in (0,n-1):
            carved = [carved[0]]*n
        height.append(carved)
    carve_end = perf_counter()
    slope,tpi = measure_globe(height,r,cfg.radius)
    end = perf_counter()
    warnings = ['Globe uses 3D gradient noise; the latitude/longitude grid oversamples poles.',
                'Gorge is a periodic latitude-band experiment, not a river or erosion simulation.',
                'Slope is relative to the reference sphere; TPI uses 8 interpolated geodesic-ring samples, not an area mean.',
                'No oceans, climate, drainage, caves or overhangs. Zero elevation is an arbitrary datum.']
    if len(frequencies)<cfg.octaves:
        warnings.append(f'Only {len(frequencies)}/{cfg.octaves} noise octaves resolved at equatorial spacing; fine layers omitted.')
    if cfg.width<3*step:
        warnings.append('Gorge half-width is under 3 equatorial cells; increase resolution for detailed slopes.')
    return {'generator_version':2,'config':asdict(cfg),'spacing_m':step,
            'effective_tpi_radius_m':min(math.pi*r/2,max(math.pi*r/(n-1),cfg.radius)),
            'resolved_octaves':len(frequencies),'warnings':warnings,
            'topology':{'type':'sphere','radius_m':r,'longitude_deg':[-180,180],
                        'latitude_deg':[90,-90],'duplicate_seam':True,'tpi_method':'8-point geodesic ring'},
            'timing_ms':{'noise':(noise_end-start)*1000,'carve':(carve_end-noise_end)*1000,
                         'measure':(end-carve_end)*1000,'total':(end-start)*1000},
            'layers':{'base':base,'height':height,'slope':slope,'tpi':tpi}}
