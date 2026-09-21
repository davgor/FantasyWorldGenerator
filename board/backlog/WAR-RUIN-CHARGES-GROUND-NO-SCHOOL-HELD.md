# WAR-RUIN-CHARGES-GROUND-NO-SCHOOL-HELD — a war ruin claims `weave` where the ley holds nothing

Filed 2026-09-21 from the closeout suite of the backlog sweep. **Attribution not established —
read the "Who caused it" section before assuming.**

## The failure

    Sim/tests/test_terrain_wars.py::test_a_war_ruin_only_charges_ground_a_school_already_held
    AssertionError: 'weave' != None

The invariant, at `test_terrain_wars.py:223-230`: for every ruin whose `cause` starts with `war_`,

    ruin['new_node_school'] == dominant_school({name: layers['ley_' + name][z][x] for name in SCHOOLS})

A war ruin may only charge ground with a school that ground already held. One does not: it claims
`weave` at a cell where `dominant_school` returns `None` — no school holds it at all.

## Why `weave` specifically

`weave` is the system's fallback school. `Sim/hero_generator/wells/magic.py:46` reads
`ruin.get('new_node_school') or 'weave'`. So a `weave` appearing where the ley says nothing is the
signature of a default being taken rather than a value being derived — which is exactly the class
of defect [CORRUPTION-LEGACY-BASIS](../done/CORRUPTION-LEGACY-BASIS.md) fixed on the corruption
side, where `legacy.basis` had to name its *source*.

## The write path

`Sim/icarus_sim/terrain_history.py:259` emits `new_node_school=legacy['school']`, where

    legacy = ruin_legacy(city, chosen[0], potencies,
                         nest_family=chosen[3].get('family'),
                         villain_school=chosen[3].get('school'))

`ruin_legacy` is at `Sim/icarus_sim/terrain_ruins.py:64` and takes **four** possible school
sources: the ley `potencies`, a `nest_family`, a `victor_culture`, a `god_school` and a
`villain_school`. The test asserts the ley wins for a war cause. Something else is winning.

## Who caused it — NOT established, and do not assume

Checked against HEAD rather than by adjacency:

- `Sim/icarus_sim/terrain_wars.py` — **unmodified**
- `Sim/tests/test_terrain_wars.py` — **unmodified**
- `Sim/icarus_sim/terrain_ruins.py` (holds `ruin_legacy`) — **unmodified**
- `Sim/icarus_sim/terrain_history.py:259` — the emitting line is **unchanged** in the diff

So no code on the direct path moved. That leaves the **inputs** to `ruin_legacy`, and the live
candidate is `villain_school=chosen[3].get('school')`: the villains block moved to VERSION 2 on
2026-09-21, gaining claim refresh, `refreshed_age` and `TIER_KEPT_PER_AGE` tier decay, and a
villain now survives and holds ground across ages where one previously could not. A villain
carrying a school into a war cause would take precedence over the ley.

**That is a hypothesis, not a finding.** The way to settle it is ablation, not reading: revert
`terrain_villains.py` alone, regenerate the same world, and re-run this one test. If it passes,
it is the villains change; if it fails identically, it predates the sweep. A concurrent session
reported this same failure earlier in the evening, which is weak evidence for pre-existing but
was measured while several lanes were in flight and does not separate the two.

Note the ley layer is itself in motion: `AGE_YEARS` moved 100 → 5000 on 2026-09-21, and it is a
composition exponent that drains the ley layer, so `dominant_school` returning `None` at more
cells than before is plausible and would produce exactly this symptom **without any villain
involvement**. That is the second hypothesis and it is at least as likely as the first.

## Why it was not fixed on the spot

Three of the four possible causes change generated worlds, and the fix is a precedence decision
between five school sources — not a patch. Taking it at the end of a long sweep, on a
determinism-sensitive path, with attribution unestablished, would have been the wrong trade.

## Acceptance

`test_a_war_ruin_only_charges_ground_a_school_already_held` passes unmodified, **and** the ablation
above is recorded so the next reader knows which of the two hypotheses was true. If the answer is
that the ley genuinely holds nothing at that cell now, then the *test* encodes the old world and
the card is about what a war ruin should charge when the ground holds nothing — which is a
question, not a bug.
