"""Pure coordinate-contract v1 oracle; no generation or engine dependencies."""
import math


_ANCHOR = {'latitude_degrees', 'longitude_degrees'}
_FIELDS = {
    'globe_position': _ANCHOR | {'radius_m', 'height_m'},
    'tangent_frame': _ANCHOR,
    'city_direction': _ANCHOR | {'radius_m', 'x_m', 'z_m'},
    'patch_direction': _ANCHOR | {'radius_m', 'x_m', 'z_m'},
    'local_position': _ANCHOR | {'radius_m', 'origin_height_m', 'position_m'},
    'tile_direction': {'level', 'x', 'z'},
    'height_above_sea': {'height_m', 'sea_level_m'},
    'metres_to_centimetres': {'value_m'},
}


def _finite(value):
    if type(value) not in (int, float):
        raise ValueError('coordinate values must be finite numbers, not booleans or strings')
    try:
        number = float(value)
    except (OverflowError, ValueError):
        raise ValueError('coordinate number is outside finite float range') from None
    if not math.isfinite(number):
        raise ValueError('coordinate arithmetic must remain finite')
    return number


def _frame(latitude, longitude):
    if not -90 <= latitude <= 90 or not -180 <= longitude <= 180:
        raise ValueError('latitude/longitude outside degree bounds')
    lat = math.radians(latitude)
    lon = math.radians(-180 if longitude == 180 else longitude)
    up = [math.cos(lat)*math.cos(lon), math.sin(lat), math.cos(lat)*math.sin(lon)]
    if abs(latitude) == 90:
        up = [0., 1. if latitude > 0 else -1., 0.]
    return {'up': up, 'east': [-math.sin(lon), 0., math.cos(lon)],
            'north': [-math.sin(lat)*math.cos(lon), math.cos(lat), -math.sin(lat)*math.sin(lon)]}


def _radial_distance(radius, height):
    distance = _finite(radius + height)
    if distance <= 0:
        raise ValueError('radius plus radial height must be positive')
    return distance


def resolve_coordinate(request: dict):
    """Resolve one strict versioned coordinate operation without mutating input."""
    if not isinstance(request, dict) or set(request) != {'coordinate_version', 'operation', 'values'}:
        raise ValueError('coordinate request requires exactly coordinate_version, operation and values')
    if type(request['coordinate_version']) is not int or request['coordinate_version'] != 1:
        raise ValueError('unsupported coordinate_version')
    operation, values = request['operation'], request['values']
    if not isinstance(operation, str) or operation not in _FIELDS:
        raise ValueError('unknown coordinate operation')
    if not isinstance(values, dict) or set(values) != _FIELDS[operation]:
        raise ValueError('coordinate operation requires its exact declared fields')
    if operation == 'tile_direction':
        level, x, z = values['level'], values['x'], values['z']
        if any(type(v) is not int for v in (level, x, z)) or not 1 <= level <= 24:
            raise ValueError('tile sample requires integer level 1..24 and indices')
        rows = 2**level
        if not 0 <= x <= 2*rows or not 0 <= z <= rows:
            raise ValueError('tile sample lies outside global grid')
        return _frame(90-180*z/rows, -180+180*(x % (2*rows))/rows)['up']
    numbers = {k: _finite(v) for k, v in values.items() if k != 'position_m'}
    if operation == 'height_above_sea':
        return _finite(numbers['height_m'] - numbers['sea_level_m'])
    if operation == 'metres_to_centimetres':
        return _finite(numbers['value_m'] * 100)
    frame = _frame(numbers['latitude_degrees'], numbers['longitude_degrees'])
    if operation == 'tangent_frame':
        return frame
    radius = numbers['radius_m']
    if radius <= 0:
        raise ValueError('radius_m must be positive')
    up, east, north = frame['up'], frame['east'], frame['north']
    if operation == 'globe_position':
        distance = _radial_distance(radius, numbers['height_m'])
        return [_finite(distance*p) for p in up]
    if operation == 'local_position':
        position = values['position_m']
        if not isinstance(position, list) or len(position) != 3:
            raise ValueError('position_m must be a three-element array')
        position = [_finite(v) for v in position]
        distance = _radial_distance(radius, numbers['origin_height_m'])
        delta = [_finite(p - distance*u) for p, u in zip(position, up)]
        return [_finite(sum(_finite(d*a) for d, a in zip(delta, axis))) for axis in (east, up, north)]
    x, z = numbers['x_m'], numbers['z_m']
    if operation == 'city_direction':
        x, z = _finite(x/radius), _finite(z/radius)
        point = [_finite(u + e*x + n*z) for u, e, n in zip(up, east, north)]
        length = _finite(math.hypot(*point))
        return [v/length for v in point]
    distance = _finite(math.hypot(x, z))
    if distance == 0:
        return up
    angle = _finite(distance/radius)
    return [_finite(u*math.cos(angle) + (e*(x/distance)+n*(z/distance))*math.sin(angle))
            for u, e, n in zip(up, east, north)]
