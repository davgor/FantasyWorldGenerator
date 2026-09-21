"""A rejection sentinel of "one more than the limit" becomes a performance test when the
limit moves. This finds every one of them and fails the instant one goes legal.

A test that checks a bound is enforced needs an input outside the bound, and the obvious
sentinel is the smallest such input. That is correct on the day it is written and wrong,
silently, the day the limit moves: the input is now legal, so instead of being rejected it
is executed, and a rejection test becomes a performance test. There is no signal except a
suite that got slower, which is the one symptom nobody investigates. Raising the grid
ceiling from 257 to 1025 did exactly this to three places at once, and the repair -- moving
the sentinels from 258 and 1025 to 1026 -- re-armed the trap at the new ceiling.

`tools/validate_repo.py`'s `rejection_fixtures()` already covers fixture DATA: every value
under `overrides` in an `invalid_*` list must be outside the domain the registry declares.
This is the other half, and the half the card left open: sentinels written as literals in
test SOURCE, where there is no `invalid_*` list to declare the intent.

The whole legal range, not a sweep near the default. Every control the registry declares a
domain for is enumerated, not `size` alone, because the pattern is not about grids -- it is
about any published bound, and a sample that never crosses the boundary proves invariance
across the band it sampled and nothing else.

Both directions, and the second is the one that fires when it matters:

  * a literal that is one outside a published bound and is NOT recorded below fails, so a
    new instance of the pattern cannot arrive quietly; and
  * a recorded literal that is no longer one outside its bound fails, naming the file --
    which happens on exactly the day the bound moves and the sentinel becomes legal work.

The inventory is deliberately a ratchet rather than a clean bill of health. Deriving the
sentinel from the bound (`registry(3)['size']['max'] + 1`) is still the right repair for
each entry; an entry here says the repair is owed and names who owes it.
"""
import ast
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'Sim'))

from icarus_sim.terrain_world import registry  # noqa: E402

# Where the three unittest discoveries in tools/validate_repo.py look.
SUITES = (('Sim/tests', 'test_*.py'), ('tests', 'test_*.py'), ('tests', 'consumer_*.py'))

# The census: every literal in the suite that is exactly one step outside a published
# bound, surveyed 2026-09-21. The card that raised this recorded three instances, found
# because a ceiling moved and surfaced them, and said plainly that it had not established
# they were the only ones. They were not: there are sixteen, in nine modules.
#
# Most cost nothing if their bound moves -- they are handed straight to a constructor that
# refuses before any work happens, so a newly-legal value builds a Config and the test
# fails loudly on the spot. One does not: a size handed to `patch_request` is generated,
# which is how a rejection test becomes a performance test with no signal at all. `cost`
# records that difference, because it is the actual harm rather than the pattern.
#
# An entry is not an excuse. Deriving the sentinel from the bound is still the repair for
# every one of them; the entry says the repair is owed and, where one exists, what blocks
# it. Delete the entry when the literal is derived -- a stale entry fails too.
REFUSED = 'refused by a constructor before any work; a bound move fails it loudly'
GENERATED = 'reaches a generator, so a bound move turns rejection into silent work'

SENTINELS = (
    # Sim/tests/test_terrain_patch.py held the one instance that reached a generator --
    # size=1026 against a (3, 1025) bound. It was derived from registry(3)['size']['max'] + 1
    # on 2026-09-21 with the provenance revision row that a pinned file needs, so it is no
    # longer fragile and is deliberately absent. Do not re-add it as a literal.
    {'path': 'Sim/tests/test_terrain_biomes.py', 'control': 'moisture_bias', 'value': 2,
     'cost': REFUSED, 'note': 'test_invalid_climate_controls, one past a (-1, 1) bound.'},
    {'path': 'Sim/tests/test_terrain_climate_sites.py', 'control': 'rain_passes', 'value': 0,
     'cost': REFUSED, 'note': 'test_control_validation, one below a (1, 128) floor.'},
    {'path': 'Sim/tests/test_terrain_climate_sites.py', 'control': 'settlement_count',
     'value': 25, 'cost': REFUSED,
     'note': 'test_control_validation, one past a (0, 24) ceiling.'},
    {'path': 'Sim/tests/test_terrain_climate_sites.py', 'control': 'stubbornness', 'value': 2,
     'cost': REFUSED, 'note': 'test_control_validation, one past a (0, 1) ceiling.'},
    {'path': 'Sim/tests/test_terrain_drainage.py', 'control': 'erosion_passes', 'value': -1,
     'cost': REFUSED, 'note': 'one below a (0, 40) floor.'},
    {'path': 'Sim/tests/test_terrain_drainage.py', 'control': 'erosion_strength', 'value': 2,
     'cost': REFUSED, 'note': 'one past a (0, 1) ceiling.'},
    {'path': 'Sim/tests/test_terrain_humans.py', 'control': 'hamlets_per_core', 'value': 9,
     'cost': REFUSED, 'note': 'test_validation, one past a (0, 8) ceiling.'},
    {'path': 'Sim/tests/test_terrain_humans.py', 'control': 'fortress_count', 'value': -1,
     'cost': REFUSED, 'note': 'test_validation, one below a (0, 1024) floor.'},
    {'path': 'Sim/tests/test_terrain_lab.py', 'control': 'octaves', 'value': 0,
     'cost': REFUSED, 'note': 'one below a (1, 10) floor.'},
    {'path': 'Sim/tests/test_terrain_magic.py', 'control': 'magic_enabled', 'value': 2,
     'cost': REFUSED, 'note': 'one past a (0, 1) flag.'},
    {'path': 'Sim/tests/test_terrain_magic.py', 'control': 'human_magic_limit', 'value': 2,
     'cost': REFUSED, 'note': 'one past a (0, 1) ceiling.'},
    {'path': 'Sim/tests/test_terrain_scale.py', 'control': 'relief_m', 'value': -1.0,
     'cost': REFUSED, 'note': 'test_rejects_nonsense_inputs, one below a (0, 1e6) floor.'},
    {'path': 'Sim/tests/test_terrain_tectonics.py', 'control': 'phase', 'value': 0,
     'cost': REFUSED, 'note': 'test_invalid_phase_controls, one below a (1, 16) floor.'},
    {'path': 'Sim/tests/test_terrain_tectonics.py', 'control': 'tectonics', 'value': 2,
     'cost': REFUSED, 'note': 'one past a (1, 1) pin.'},
    {'path': 'Sim/tests/test_terrain_tectonics.py', 'control': 'crust_bias', 'value': 2,
     'cost': REFUSED, 'note': 'one past a (-1, 1) ceiling.'},
)


def domains():
    """Every control the registry declares a closed numeric domain for."""
    return {name: (spec['min'], spec['max'])
            for name, spec in registry(3).items() if 'min' in spec and 'max' in spec}


def _number(node):
    """The literal a node holds, unwrapping a unary minus. Not a folded expression.

    A sentinel written as `max + 1` is the repair, not the defect, so only bare literals
    are read here: `-1` is a literal and `registry(3)['size']['max'] + 1` is not.
    """
    negative = False
    if isinstance(node, ast.UnaryOp) and isinstance(node.op, ast.USub):
        node, negative = node.operand, True
    if isinstance(node, ast.Constant) and isinstance(node.value, (int, float)) \
            and not isinstance(node.value, bool):
        return -node.value if negative else node.value
    return None


def control_literals(tree):
    """(control, value, line) for every numeric literal bound to a control's name.

    Two shapes carry a control in this suite: a dict entry `{'size': 1026}` and a keyword
    argument `size=1026`. The dict form is the one that matters -- the instance this card
    is about sits in a tuple of request bodies iterated by a `for`, several lines above
    the `assertRaises` that consumes it, so anything scoped to the `with` block misses it.
    """
    known = domains()
    for node in ast.walk(tree):
        if isinstance(node, ast.Dict):
            for key, value in zip(node.keys, node.values):
                if isinstance(key, ast.Constant) and key.value in known:
                    number = _number(value)
                    if number is not None:
                        yield key.value, number, getattr(value, 'lineno', node.lineno)
        elif isinstance(node, ast.Call):
            for keyword in node.keywords:
                if keyword.arg in known:
                    number = _number(keyword.value)
                    if number is not None:
                        yield keyword.arg, number, getattr(keyword.value, 'lineno', node.lineno)


def one_outside(control, value):
    """Is this literal exactly one step outside the control's declared domain?

    One above the ceiling or one below the floor. That is the fragile form: correct today,
    legal the moment the bound moves. A value further out stays out when a bound moves by
    one and is not what this guard is for.
    """
    low, high = domains()[control]
    return value == high + 1 or value == low - 1


def fragile_sentinels():
    """Every fragile sentinel in every module the suites actually run."""
    found = []
    for directory, pattern in SUITES:
        for path in sorted((ROOT / directory).glob(pattern)):
            try:
                tree = ast.parse(path.read_text(encoding='utf-8'))
            except (SyntaxError, UnicodeDecodeError):
                continue
            name = path.relative_to(ROOT).as_posix()
            for control, value, line in control_literals(tree):
                if one_outside(control, value):
                    found.append((name, control, value, line))
    return found


class ThePatternCannotSpread(unittest.TestCase):
    def test_every_fragile_sentinel_is_recorded(self):
        """A new "bound plus one" literal fails on arrival rather than years later."""
        recorded = {(e['path'], e['control'], e['value']) for e in SENTINELS}
        surprises = [hit for hit in fragile_sentinels()
                     if (hit[0], hit[1], hit[2]) not in recorded]
        self.assertEqual(
            surprises, [],
            'a rejection sentinel written as one-past-a-published-bound is correct today '
            'and becomes legal work the day the bound moves, silently. Derive it instead '
            "-- registry(3)[<control>]['max'] + 1 -- or record it in SENTINELS with the "
            'reason it cannot be derived yet.')

    def test_every_recorded_sentinel_is_still_armed(self):
        """The direction that fires when the bound moves.

        The day the grid ceiling leaves 1025, the recorded 1026 stops being one-past-the
        bound and becomes a legal size that the test executes instead of rejecting. That
        is the failure this whole card exists to catch, and it lands here at the moment
        the ceiling moves rather than an hour later when the suite is slow.
        """
        found = {(name, control, value) for name, control, value, _ in fragile_sentinels()}
        known = domains()
        for entry in SENTINELS:
            key = (entry['path'], entry['control'], entry['value'])
            if key in found:
                continue
            self.assertIn(entry['control'], known,
                          '%s records control %r, which the registry no longer declares'
                          % (entry['path'], entry['control']))
            low, high = known[entry['control']]
            self.assertFalse(
                low <= entry['value'] <= high,
                '%s: %s=%s was a rejection sentinel one step outside the bound and is now '
                'INSIDE the declared domain (%s..%s). It is no longer rejected: %s'
                % (entry['path'], entry['control'], entry['value'], low, high,
                   entry['cost']))
            self.fail(
                '%s no longer holds %s=%s one step outside its bound (%s..%s); if the '
                'literal is now derived from the bound, delete this SENTINELS entry -- a '
                'stale entry claims a debt that is already paid'
                % (entry['path'], entry['control'], entry['value'], low, high))

    def test_every_recorded_sentinel_says_what_it_costs_and_names_a_live_file(self):
        """An entry with no note is an unexplained exception, and one naming a blocker
        that has been deleted is a debt with no owner."""
        for entry in SENTINELS:
            self.assertTrue(entry.get('note'), '%s has no note' % entry['path'])
            self.assertIn(entry.get('cost'), (REFUSED, GENERATED),
                          '%s does not say what a bound move costs' % entry['path'])
            self.assertTrue((ROOT / entry['path']).exists(),
                            'recorded sentinel file is gone: %s' % entry['path'])
            if entry.get('blocker'):
                self.assertTrue(
                    (ROOT / entry['blocker']).exists(),
                    '%s names a blocker that does not exist: %s'
                    % (entry['path'], entry['blocker']))


class TheGuardItselfFires(unittest.TestCase):
    """A guard that has not been shown to fire is not a guard."""

    def test_one_outside_recognises_both_ends_and_nothing_else(self):
        low, high = domains()['size']
        self.assertTrue(one_outside('size', high + 1))
        self.assertTrue(one_outside('size', low - 1))
        self.assertFalse(one_outside('size', high))
        self.assertFalse(one_outside('size', low))
        self.assertFalse(one_outside('size', high + 2))

    def test_a_moved_ceiling_disarms_the_recorded_sentinel(self):
        """The failure this exists for, forced rather than waited for.

        `one_outside` is asked the question it would be asked after a ceiling move, and
        has to answer that 1026 is no longer a sentinel -- which is what makes
        test_every_recorded_sentinel_is_still_armed fail on that day.
        """
        entry = SENTINELS[0]
        low, high = domains()[entry['control']]
        self.assertTrue(one_outside(entry['control'], entry['value']),
                        'the recorded sentinel is not currently one past %s' % high)
        moved = {entry['control']: (low, 2049)}
        self.assertFalse(
            moved[entry['control']][0] - 1 == entry['value']
            or moved[entry['control']][1] + 1 == entry['value'],
            'with the ceiling at 2049, %s is no longer one past it' % entry['value'])
        self.assertIn(entry['value'], range(int(low), 2050),
                      'with the ceiling at 2049 the sentinel is a legal size that the '
                      'test would generate rather than reject')

    def test_a_derived_sentinel_is_not_read_as_a_literal(self):
        """`registry(3)['size']['max'] + 1` is the repair; it must not be flagged as the
        defect. Only bare literals are read."""
        tree = ast.parse("from icarus_sim.terrain_world import registry\n"
                         "body = {'size': registry(3)['size']['max'] + 1}\n")
        self.assertEqual(list(control_literals(tree)), [])

    def test_the_scan_reaches_the_shape_the_instance_is_written_in(self):
        """The armed instance sits in a tuple of bodies iterated by a `for`, above the
        `assertRaises` that consumes it. A scan of the `with` block never sees it."""
        tree = ast.parse("for body in ({'config': {'shape': 'globe', 'size': 1026}},):\n"
                         "    with self.assertRaises(ValueError):\n"
                         "        patch_request(body)\n")
        self.assertEqual([(c, v) for c, v, _ in control_literals(tree)], [('size', 1026)])


if __name__ == '__main__':
    unittest.main()
