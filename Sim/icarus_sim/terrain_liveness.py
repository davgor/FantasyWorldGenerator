"""One predicate for "is this person still here", across four blocks that disagree.

Four packages answer the same question in three vocabularies and no caller can ask it
once: `heroes.people[].status` is `living` or `legend`, `npcs.people[].status` is `alive`
or `dead`, and `villains.people[].status` is `living` or `fallen`. A tick crossing many
ages asks this constantly, so it is asked here instead of at every call site.

Read-only. Nothing in this module writes to a world, and no vocabulary is migrated: the
per-package predicates stay authoritative and this delegates to them where one exists.

Two traps this module exists to survive:

**`status` means two different things at two depths of one block.** `hero_generator`
writes a block-level `status` of `'ok'` or `'failed'` and a person-level `status` of
`'living'` or `'legend'` under the same key name, at two different depths of one block.
`npc_roster` does the same. A predicate that matched on the string alone would read a
failed block as a living person, so dispatch here is on the block a record came from and
never on the shape of the record, and `liveness` rejects a block handed to it in place of
a person.

**Absent status means present.** A record written before a package recorded departure at
all described someone who stood. `terrain_villains.is_standing` says so explicitly and
`key_locations.villain_holdings` inlines the same rule; both would break if this module
read a missing key as gone, and every world generated before the fall pair landed would
be read as a world of ghosts.
"""

PRESENT = 'present'
GONE = 'gone'

# The value each block writes for a person who is still here. `dreads` is the antagonist
# cast inside the heroes block and shares its vocabulary. A block absent from this table
# is not one whose records carry liveness, and asking about it is a caller error rather
# than a default.
PRESENT_STATUS = {
    'heroes': 'living',
    'dreads': 'living',
    'npcs': 'alive',
    'villains': 'living',
}

# The value each block writes for a person who is no longer here. Three words for one
# event, two of them carrying a judgement the third does not, and that is the published
# surface rather than a choice made here: `tests/test_status_vocabulary.py` enumerates it.
#
# This table exists so that a *writer* has one place to ask which word a block uses. The
# only translation between two published contracts in this repository is a hand-written
# expression inside `Sim/npc_roster/__init__.py`, which maps a hero's `living` to a roster
# record's `alive`. That expression cannot be replaced by a call: the leaf packages are
# forbidden from importing the generator (`npc_roster/policy.py` states the rule, and
# `hero_generator/seeds.py` duplicates `child_seed` rather than break it). So the mapping is
# published here and `Sim/tests/test_person_state.py` binds the roster's copy to it, the
# same shape `test_npc_roster` uses for that package's `posts.json` snapshot.
GONE_STATUS = {
    'heroes': 'legend',
    'dreads': 'legend',
    'npcs': 'dead',
    'villains': 'fallen',
}

# Keys that only ever appear on a block, never on a person. Used to catch the depth
# confusion loudly instead of answering a question about the wrong object.
BLOCK_ONLY_KEYS = ('people', 'quest_hooks', 'policy_revision')


def token(block, state):
    """The word `block` writes for `'present'` or `'gone'`. The published translation.

    The inverse of `liveness`, and deliberately the only one: a writer that picked a word
    by matching on a string would put `dead` on a hero or `legend` on an npc, and both
    read back through `liveness` as the wrong answer rather than as an error.
    """
    if block not in PRESENT_STATUS:
        raise ValueError('Unknown liveness block: ' + repr(block))
    if state not in (PRESENT, GONE):
        raise ValueError('Unknown liveness state: ' + repr(state))
    return PRESENT_STATUS[block] if state == PRESENT else GONE_STATUS[block]


def liveness(record, block):
    """`'present'` or `'gone'` for one person record drawn from `block`.

    `block` is the name of the list the record came from, not a guess at its shape. A
    record with no `status` reads as present.
    """
    if block not in PRESENT_STATUS:
        raise ValueError('Unknown liveness block: ' + repr(block))
    if not isinstance(record, dict):
        raise ValueError('liveness expects a person record')
    if any(key in record for key in BLOCK_ONLY_KEYS):
        # A block was passed where a person belongs. Its `status` is 'ok' or 'failed' and
        # answering from it would report a failed package as a living person.
        raise ValueError('liveness expects a person record, not the ' + block + ' block')
    if block == 'villains':
        # The villain rule is authored in the module that writes it, including its own
        # absent-reads-as-standing clause. Two implementations of one rule is the defect
        # this module exists to prevent, so it delegates rather than restating.
        from .terrain_villains import is_standing
        return PRESENT if is_standing(record) else GONE
    return PRESENT if (record.get('status') or PRESENT_STATUS[block]) == PRESENT_STATUS[block] else GONE


def is_present(record, block):
    """True while this person is still in the world."""
    return liveness(record, block) == PRESENT


def present(records, block):
    """The still-here records of `records`, in the order given."""
    return [record for record in (records or []) if is_present(record, block)]


def census(world):
    """Per-block `{present, gone}` counts, over whatever blocks this world carries.

    A block that failed to generate carries `status: 'failed'` and no `people`; it is
    reported as absent rather than as an empty cast, because zero present people and no
    package at all are different facts and a tick must not confuse them.
    """
    out = {}
    for block, key in (('heroes', 'heroes'), ('dreads', 'heroes'), ('npcs', 'npcs'), ('villains', 'villains')):
        container = world.get(key)
        if not isinstance(container, dict):
            continue
        if key != 'villains' and container.get('status') != 'ok':
            continue
        people = container.get('people') if block != 'dreads' else container.get('dreads')
        if people is None:
            continue
        counts = {PRESENT: 0, GONE: 0}
        for record in people:
            counts[liveness(record, block)] += 1
        out[block] = counts
    return out
