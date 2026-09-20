# CONTENT-BEAST-MOVEMENTS-STRANDED — a third of the travelling world never travels

Owner: none. State: open, unowned. Found by the Python-output red team
(`docs/reviews/233182e-python-output-red-team.md`, finding 5).

## Observed behavior

Seed 42, size 17, `generator_version` 16. `beast_movements` reports its own outcome:

```json
{"considered": 792, "skipped": 0, "share": 1.0, "routed": 532, "stranded": 260}
{"migratory": 297, "follower": 407, "irruptive": 85, "drifter": 3}
```

**260 of 792 groups — 33% — are stranded.** A stranded group carries an empty `legs`, confirmed
directly: 532 groups have legs, 260 have none. It exists at a point and never walks the seasonal
round the block was built to produce.

The block's `method` says *"Every placed site whose species declares a movement class other than
nester becomes a travelling group. Herds walk a seasonal round between high summer and winter
ground."* A third of them do not.

Downstream, `encounters` indexes all 792 anyway, so a third of the entries in the proximity index
describe a herd that is permanently where it started.

## Why it matters

The seasonal round is the point of the block — it is what makes `encounters.by_month` mean
anything, and `by_month` varies from 356 entries in month 5 to 769 in month 4, so a third of the
population sitting still is a third of that variation that is not real. A consumer reading
"what is near here in month 7" is reading a mixture of animals that move and animals that were
recorded as movers and do not.

The number is published, which is how this was found. Nothing acts on it and nothing explains it.

## Proposed mechanism

1. **Find out why.** The likely causes are all ordinary and all testable: no reachable summer or
   winter ground within the species' range on a world that is 80.5% ocean; a route that crosses
   water a land species cannot; a seasonal target that resolves to the same node it started on.
   The block already computes enough to say which.
2. **Record the reason per group**, the way `key_locations.diagnostics` records why an archetype
   did not place. A stranded group should carry the reason it is stranded.
3. **Then decide the behavior.** If a herd genuinely has nowhere to go, a group with no legs is
   the correct output and should say so rather than looking like a routing failure. If the round
   failed for a reason that can be fixed — a water crossing, a range that is too tight — fix it.
4. **Mark stranded groups in `encounters`**, or exclude them, so the monthly index is not a
   mixture of two different things. This overlaps `CONTENT-ENCOUNTERS-ARE-FISH` step 1 and the
   two should be done together.

## Dependencies and unresolved decisions

- Whether `stranded` is expected at all. `limits` is candid about what the block does not model —
  *"nothing breeds, starves, is eaten or merges with another group"* — but says nothing about
  groups that do not move, which suggests stranding was not an anticipated outcome.
- 786 of 792 groups come from `wildlife` and 6 from `beast_nests`. Whether the stranding rate
  differs between the two has not been measured and would localise the cause quickly.
- `beast-movements` has a schema and a version; adding a per-group reason is an interchange
  change.

## Acceptance and evidence

- Every stranded group carries a reason.
- The stranded share on a reference world is either below a stated threshold, or documented as
  expected with the reason it is expected.
- A behavioral test asserts the share does not regress.

## Adversarial review and limitations

One seed at one size. The 33% figure will move with land fraction and with world size, and on a
world that is 80.5% ocean a high stranding rate among land species is plausible and may be
correct. The defect this card asserts is that the document does not say which — not that 33% is
necessarily wrong.

**A stronger caveat, added after the fact.** The measured world has `resolved_octaves: 0` of 5 —
no surface relief at all — and routing walks that terrain. A seasonal round between high summer
and winter ground needs elevation to have somewhere to go, and on a world with none, a high
strand rate may be the correct output rather than a routing failure. **Re-measure at size 513
with all five octaves resolved before treating 33% as a defect.** That does not weaken the ask in
step 2 — a stranded group should carry its reason either way, and the reason is exactly what
would answer this.
