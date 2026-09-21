"""`Contracts/blocks.json` against the tree: every column that can be derived, is.

The world contract listed no blocks, so nothing could be missing from it. A consumer
reading `world-output.schema.json` cannot distinguish a block that was never built, a
block that failed and reported `status: failed`, a block switched off by an environment
variable, and a block whose emitter broke this morning. All four validate, because the
envelope root is `additionalProperties: true`.

`Contracts/blocks.json` makes absence representable: one row per top-level key, naming the
contract that describes it or **a stated reason it has none**. The reason column is the
point of the exercise rather than an escape hatch -- decision 029 says a core-emitted block
earns a schema when another published contract derives from it or an outside consumer reads
it, and four blocks qualify today and are deliberately unscheduled. That is a fact about the
product, and it now has somewhere to live other than a card.

**A registry without a failing test is bureaucracy, and a stale registry is worse than none
because it reads as authoritative.** So the drift has to fail in both directions:

- here, against `STATE_KEYS`, the envelope and the files each row names -- no world needed;
- in `tests/test_world_schema_conformance.py`, against a generated world -- emitted-but-
  unregistered, and not-optional-but-absent.

Nothing here claims any block is *correct*. It claims absence is detectable. Those are
different goods and only the second one is on offer.
"""
import ast
import json
from pathlib import Path
import sys
import unittest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'Sim'))

REGISTRY = json.loads((ROOT / 'Contracts/blocks.json').read_text(encoding='utf-8'))
ENVELOPE = json.loads((ROOT / 'Contracts/schemas/world-output.schema.json')
                      .read_text(encoding='utf-8'))
BINDINGS = json.loads((ROOT / 'docs/conformance/version-bindings.json')
                      .read_text(encoding='utf-8'))
ROWS = {block['key']: block for block in REGISTRY['blocks']}


def state_keys():
    """`STATE_KEYS` read out of the source rather than imported.

    Importing it would be cheaper and would also make this test depend on the whole
    simulation importing cleanly, which is a different question from what the tuple says.
    """
    src = (ROOT / 'Sim/icarus_sim/terrain_history.py').read_text(encoding='utf-8')
    for node in ast.walk(ast.parse(src)):
        if isinstance(node, ast.Assign) and any(
                isinstance(t, ast.Name) and t.id == 'STATE_KEYS' for t in node.targets):
            return set(ast.literal_eval(node.value))
    raise AssertionError('STATE_KEYS is no longer a literal assignment in terrain_history')


def written_keys(path):
    """Every string constant this module uses as a place to put something.

    Two shapes, because the repository builds documents both ways: a subscript assignment
    (`result['water'] = ...`, `world['villains'] = ...`) and a key of a dict literal, which
    is how the world skeleton in `terrain_tectonics` and the export document in `cli` are
    written. A string used as a list element or compared against is not writing anything,
    and counting it is what made this check pass for an owner that does not own the block.
    """
    out = set()
    tree = ast.parse(path.read_text(encoding='utf-8'))
    for node in ast.walk(tree):
        targets = []
        if isinstance(node, ast.Assign):
            targets = list(node.targets)
        elif isinstance(node, (ast.AugAssign, ast.AnnAssign)):
            targets = [node.target]
        for target in targets:
            if isinstance(target, ast.Subscript) and isinstance(target.slice, ast.Constant):
                if isinstance(target.slice.value, str):
                    out.add(target.slice.value)
        if isinstance(node, ast.Call):
            # `dict(water=...)` builds a document too.
            for keyword in node.keywords:
                if keyword.arg:
                    out.add(keyword.arg)
            # `result.setdefault('villains', {...})` is how terrain_villains writes its
            # block: it is a write, and the only one that block has.
            if (isinstance(node.func, ast.Attribute) and node.func.attr == 'setdefault'
                    and node.args and isinstance(node.args[0], ast.Constant)
                    and isinstance(node.args[0].value, str)):
                out.add(node.args[0].value)
        if isinstance(node, ast.Dict):
            for key in node.keys:
                if isinstance(key, ast.Constant) and isinstance(key.value, str):
                    out.add(key.value)
    return out


class HarnessControlTests(unittest.TestCase):
    """Passes. Everything below iterates the registry, and iterating an empty list agrees
    with every claim made about it."""

    def test_the_registry_is_populated_and_its_keys_are_unique(self):
        self.assertGreaterEqual(len(REGISTRY['blocks']), 60)
        keys = [block['key'] for block in REGISTRY['blocks']]
        duplicates = sorted({k for k in keys if keys.count(k) > 1})
        self.assertEqual(duplicates, [], f'one key, two rows: {duplicates}')
        self.assertEqual(REGISTRY['schema'], 'fantasy-world-generator.blocks')
        self.assertEqual(REGISTRY['schema_version'], 1)

    def test_the_source_of_truth_it_is_checked_against_is_itself_populated(self):
        self.assertGreaterEqual(len(state_keys()), 40)
        self.assertGreaterEqual(len(ENVELOPE.get('properties') or ()), 40)
        self.assertGreaterEqual(len(BINDINGS.get('bindings') or ()), 20)


class BlockRegistryTests(unittest.TestCase):

    def test_every_state_key_has_a_row_and_every_row_saying_so_is_a_state_key(self):
        """Adding a key to `STATE_KEYS` without a registry row fails here, by name."""
        state = state_keys()
        unregistered = sorted(state - set(ROWS))
        self.assertEqual(unregistered, [],
                         f'the simulation carries these across an age boundary and the registry '
                         f'does not list them: {unregistered}')
        wrong = sorted(key for key, block in ROWS.items()
                       if block['state_key'] != (key in state))
        self.assertEqual(wrong, [],
                         f'the `state_key` column disagrees with terrain_history.STATE_KEYS for: '
                         f'{wrong}. The column is measured, so a disagreement means the tuple moved '
                         'and the registry did not.')

    def test_every_row_names_a_contract_or_states_why_it_has_none(self):
        """`reason_if_unspecified` is non-null exactly when `schema` is null.

        Both null is a row that says nothing; both set is a row that contradicts itself.
        """
        for key, block in sorted(ROWS.items()):
            with self.subTest(key=key):
                schema, reason = block['schema'], block['reason_if_unspecified']
                self.assertNotEqual(schema is None, reason is None,
                                    'exactly one of `schema` and `reason_if_unspecified`')
                if schema is not None:
                    self.assertTrue((ROOT / schema).is_file(), f'{key}: {schema} does not exist')
                else:
                    self.assertGreater(len(reason), 40,
                                       f'{key}: "{reason}" is a placeholder, not a reason')

    def test_every_named_version_binding_exists(self):
        ids = {b['id'] for b in BINDINGS['bindings']}
        named = {key: block['version_binding'] for key, block in ROWS.items()
                 if block['version_binding']}
        self.assertTrue(named, 'no row names a binding, so this test proves nothing')
        dangling = sorted(f'{key} -> {value}' for key, value in named.items() if value not in ids)
        self.assertEqual(dangling, [],
                         f'rows pin a version binding that version-bindings.json does not '
                         f'declare: {dangling}')

    def test_every_owner_exists_and_writes_the_key_it_is_credited_with(self):
        """A wrong owner is the failure a registry invites, so it is checked rather than read.

        Two weaker predicates were tried and both answer a different question:

        - *the file exists* passes for any module in the repository;
        - *the file contains the string* passes for `water` against `terrain_astrology.py`,
          which has it as an element of `HEMISPHERES`. That ablation came back green, which
          is how the check got tightened -- a near-miss match silently answers a different
          question.

        So the key must appear as something that **writes** it: the constant subscript of an
        assignment target (`result['water'] = ...`), or a key of a dict literal, which is how
        the world skeleton and the export document are built.
        """
        for key, block in sorted(ROWS.items()):
            with self.subTest(key=key):
                owner = ROOT / block['owner']
                self.assertTrue(owner.is_file(), f'{key}: {block["owner"]} does not exist')
                self.assertIn(key, written_keys(owner),
                              f'{key}: {block["owner"]} never writes it -- it is credited with a '
                              'key it does not emit')

    def test_the_envelope_columns_are_what_the_envelope_says(self):
        declared = set(ENVELOPE.get('properties') or ())
        required = set(ENVELOPE.get('required') or ())
        wrong = sorted(key for key, block in ROWS.items()
                       if (block['declared_in_envelope'], block['required_by_envelope'])
                       != (key in declared, key in required))
        self.assertEqual(wrong, [],
                         f'the registry and world-output.schema.json disagree about what is '
                         f'declared or required: {wrong}')

    def test_a_key_the_envelope_requires_is_never_marked_optional(self):
        """The two would contradict each other, and a consumer would have to pick one."""
        contradictory = sorted(key for key, block in ROWS.items()
                               if block['required_by_envelope'] and block['optional'])
        self.assertEqual(contradictory, [],
                         f'required by the envelope and optional in the registry: {contradictory}')

    def test_the_undeclared_keys_are_recorded_as_undeclared(self):
        """Nine keys reach a consumer that `world-output.schema.json` has never heard of.

        This is the live form of the gap the registry was asked for: they arrive unannounced
        and unvalidated, because the envelope root is open. The registry does not fix that --
        closing the root is a compatibility decision with its own cost and belongs to whoever
        owns `Contracts/` -- it records it.
        """
        undeclared = sorted(key for key, block in ROWS.items()
                            if not block['declared_in_envelope'])
        self.assertTrue(undeclared, 'no undeclared key, so this test is describing a tree that '
                                    'no longer exists and should be retired rather than kept')
        for key in undeclared:
            with self.subTest(key=key):
                self.assertIsNone(ROWS[key]['schema'])
                self.assertIn('declared by nothing', ROWS[key]['reason_if_unspecified'])


if __name__ == '__main__':
    unittest.main()
