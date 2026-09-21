# NOMAD-SUBDIVIDE-DROPS-THE-LAST-CUT — a caravan leg can be half again a day's march

**DONE 2026-09-21. Owner ruling: the cut is wrong — no segment may exceed one day's march.**
The existing assertion stands unchanged and is green. See "What was delivered" at the foot.

Filed 2026-09-21 from work on [NOMAD-FISSION](../done/NOMAD-FISSION.md). **Pre-existing and
proven so**, not introduced by that card.

## Requested behavior

No leg of a nomad round should exceed one day's march. `Sim/tests/test_terrain_nomads.py::test_no_caravan_leg_exceeds_a_day_march` asserts exactly that and it fails.

    AssertionError: 40980.256554012645 not less than or equal to 36750.0
                    : ('nomad-2-723', ...)

A leg of **1.115 day-marches** survives on seed 42 size 33. The bound is 36,750 m; the leg is
40,980 m.

## The defect

`_subdivide` in `Sim/icarus_sim/terrain_nomad_routes.py` cuts a leg into day-marches and its tail
condition is `remaining > day_march * .5`. A remainder of half a day-march or less is **not** cut,
so it is absorbed into the previous segment — which means a segment can reach **1.5 day-marches**
before the rule forces another cut. The assertion allows 1.0. Every value in `(1.0, 1.5]` is a
leg the code considers finished and the test considers too long.

## It is pre-existing — established, not assumed

The agent that found it proved this rather than inferring it from a clean-looking diff:

1. Ran the module on the pristine tree **before touching anything**: 33 tests, 1 failure, same
   band, same length, 1223 s.
2. Ran the original `terrain_nomad_routes.py` from `git show HEAD:` against the same world and got
   **the identical over-long leg**.

That matters because four sessions were writing this tree concurrently, and a failure appearing in
a working lane is assumed to belong to it by default.

## Why it was deliberately not fixed in place

It is a one-line change in a file that agent owned, and it was still left alone, for a reason worth
keeping: **fixing it moves caravan station counts**, and
[NOMAD-CARAVAN-ECONOMY](../retired/NOMAD-CARAVAN-ECONOMY.md) is measuring against those counts. Landing both
in one pass would confound that card's measurement with this one's. Sequence this **after** the
caravan work, or accept that the caravan baseline must be re-taken.

## Unresolved — RULED 2026-09-21: the cut is wrong

Whether the bound or the cut is wrong. Two readings, and this card did not choose:

- **The cut is wrong.** Change the tail to `remaining > 0` (or fold the remainder forward rather
  than back) so no segment exceeds one day-march, and the existing assertion stands unchanged.
  Cost: more, shorter legs; station counts move; `round_length_m` is unaffected but the leg count
  is not.
- **The bound is wrong.** A herder day is not a constant, and absorbing a short tail into the
  previous day may be the truer model — a band does not stop half an hour short of water to make
  the arithmetic tidy. Then the assertion should read `1.5 * day_march` and say why.

The second reading is not obviously wrong, which is why this needs a ruling rather than a patch.
Whoever takes it should state which of the two they are asserting, because the test currently
encodes the first while the code implements the second, and **only one of them is a defect**.

## Dependencies

Sequence after [NOMAD-CARAVAN-ECONOMY](../retired/NOMAD-CARAVAN-ECONOMY.md). Size 17 raises no wanderers on
seed 42, so any test must use size 33 or larger.

**Not sequenced after it in the end, and it no longer exists:** NOMAD-CARAVAN-ECONOMY was
retired to `board/retired/` by another lane tonight. The owner ruled on this card first, so any caravan
baseline must be re-taken against the counts below rather than the other way round. That is
the cost the card named and it was accepted knowingly.

## What was delivered, 2026-09-21

**Both candidate mechanisms were checked, and only one of them fires.** The card offered the
tail condition; the ruling also asked whether `len(leg['nodes']) < 3` — a leg with no
intermediate node, emitted uncut whatever its length — was the real cause. It is not, and
this was measured rather than reasoned: the failing leg `nomad-2-723-camp-3 -> camp-4`
carries **12 nodes and 11 steps**, the widest of them 5906.3 m, so it has ten interior
nodes any of which could have held a station. The short circuit never sees it.

The tail condition is the whole defect. The 11 cumulative distances are 3125.0, 7975.4,
13199.0, 16324.0, 22230.3, 25355.3, 28480.3, 31605.3, 34730.3, 37855.3, 40980.3. The run
first reaches the 35000 m march at the tenth node, 37855.3 m, where 3125.0 m remain — not
more than `day_march * .5`, so no cut fires. Nothing after it can fire either, and the leg
is emitted whole at **1.171 `DAY_MARCH_M`**, 1.115 times the test's 5%-slack bound.

### The cut now closes at the last node inside the day, not the first node past it

`remaining > 0` was the obvious repair and it is not enough: cutting on the crossing
overshoots by up to one graph step, 6250 m at size 33, which is 17.9% of the march and
still past the assertion's 1.05. The condition is therefore `run > 0. and run + step >
day_march`, closing the segment at `a` and starting the next at `a`. Every segment is then
at most one day's march by construction.

The same leg now reads 34730.256554 m over 10 nodes and 6250.0 m over 3, with one station
camp between them, and no routed leg on seed 42 size 33 exceeds the bound.

`run > 0.` is the residual the ruling asked about: a **single graph step** wider than a
day's march has no interior node and is walked whole. That is the same limit the
`len(nodes) < 3` short circuit states for a two-node leg, and it is a property of the route
graph rather than of this cut — the step is 12500 m at size 17 and 6250 m at size 33
against a 35000 m march, so it does not arise at any raster the generator ships.

One branch died with the change: `elif out_legs: out_legs[-1]['to'] = leg['to']` repaired a
one-node tail, which the old cut could produce by cutting at `b`. The new cut never lands
on the last node, so it was unreachable and is removed rather than left to be trusted.

### Cost, as predicted

Station counts move. On seed 42 size 33 the one routed caravan gains one station camp and
one leg (5 legs to 6). **`Fixtures/sample-world-v1.json` is stale**: the `nomads` block is
written at stage 16 of generation, so the committed sample's camps and legs no longer
reproduce. The orchestrator rebuilds it once at the end of the sweep.

`ROUTES_VERSION` moves **2 to 3**. No field and no enum changed and a v2 document still
validates, so the bump is about the guarantee: a consumer that sized a day's travel off
the longest leg, or counted a route's stations, reads different numbers now. The marker
and the sentence beside it moved in `docs/nomads.md` and `docs/conformance/nomads.md`.

Test: `Sim/tests/test_terrain_nomads.py::NomadRouteTests::test_no_caravan_leg_exceeds_a_day_march`,
**unchanged**, as the ruling required. Before: `AssertionError: 40980.256554012645 not less
than or equal to 36750.0 : ('nomad-2-723', 40980.256554012645)`. After: green.
