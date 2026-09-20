# SDET-STATUS-VOCABULARY — one field name, seven namespaces, and no way to ask who is alive

Owner: none. State: **defect pinned by failing tests; no fix attempted.**
Evidence: `tests/test_status_vocabulary.py` — 7 tests, 3 pass, 4 fail, 0.041 s, no world
generated.

Executable half of `PRODUCT-CONSUMER-VOCABULARY`. The enumeration below was produced by
walking every `*.schema.json` for a property literally named `status`, not by reading them.

## The surface

Thirteen declaration sites, twelve with an enum, five distinct vocabularies, plus one
unconstrained and one absent:

| tokens | where |
|---|---|
| `ok` · `failed` | block level in hero-generator, npc-roster, story-web, key-locations, key-location-plans |
| `living` · `legend` | `heroes.people[]`, `heroes.dreads[]` |
| `alive` · `dead` | `npcs.people[]` |
| `complete` · `empty` | `key_location_plans.plans[]` |
| `complete` · `partial` · `unbuildable` | city, hamlet and castle plan items |
| *(any string)* | `asset_list.assets[]` — declared `type: string`, no enum |
| `living` · `fallen` | `villains.people[]` — **declared in no schema at all** |

`route_status` (`routed` · `stranded`, in beast-movements and nomads) and `plan_status` are
**not** counted: they are different field names, and a collision analysis of the name
`status` may not borrow them.

## Two defects, separately

### 1. No consumer can ask who is alive

The live token is `living` for heroes, **`alive`** for npcs and `living` for villains. So
`status == 'living'` is right twice and silently wrong once. The end token is `legend`,
`dead`, `fallen` — three words for one event, two carrying a judgement the third does not, so
a consumer cannot even map them without first deciding what a legend is.

The only translation between two published contracts anywhere in the repository is a
hand-written expression inside a private record builder at `Sim/npc_roster/__init__.py:190`:

```python
'status': 'alive' if person.get('status') == 'living' else 'dead',
```

**That expression is the mapping.** It is published nowhere, so every downstream consumer
either rediscovers it or gets it wrong.

### 2. `complete` already means two different things

`key_location_plans.plans[]` uses it for *this plan has contents*; the city, hamlet and castle
plan items use it for *this item was fully placed*. A consumer comparing plan blocks on
`status == 'complete'` is asking two questions and will never be told which one it got.

### The villain leg is the worst of the three, and compounds another card

`villains.people[].status` is emitted with **no published definition**, so a consumer cannot
discover that `fallen` is a value it must handle. And per
`SDET-VILLAIN-FALL-UNREACHABLE.md`, no world that can be built ever contains one: the field
can only ever hold `living`. So a consumer writing `if status == 'fallen'` is writing dead
code that looks defensive — **and it cannot find that out**, because there is no schema to
tell it the value exists and no world that will ever show it one. That intersection with
`VILLAINS-NO-SCHEMA.md` is worse than either card alone.

`living` *is* declared — by `hero-generator.schema.json`, for a different block. A consumer
that found it there learned the wrong complement: a hero who is not `living` is a `legend`, a
villain who is not `living` is `fallen`.

## Proposed mechanism

**Not proposed**, and deliberately so: this is a schema change across at least two published
contracts, which `VILLAIN-FALL-UNRECORDED.md` already flagged as *"a recommendation to route,
not something either card should do on its way past"*. The cheapest honest step is to publish
the mapping that `npc_roster:190` currently keeps private, whatever else is decided.

## Dependencies and unresolved decisions

- `hero-generator.schema.json` and `npc-roster.schema.json` are published contracts; changing
  either enum is a consumer-visible interchange change needing a version move.
- `legend` and `fallen` are not synonyms for `dead` — they carry meaning a roster's `dead`
  does not. Collapsing them would lose information; keeping them needs a published mapping.
  Nobody has chosen.
- Blocked on nothing, but sequence behind `VILLAINS-NO-SCHEMA.md`: the villain leg cannot be
  fixed before the block has a contract to fix it in.

## Sources consulted

- `Contracts/schemas/hero-generator.schema.json` — block and person enums.
- `Contracts/schemas/npc-roster.schema.json` — block and person enums.
- `Contracts/schemas/key-location-plans.schema.json` — the `complete`/`empty` plan enum.
- `Contracts/schemas/world-output.schema.json` — the three plan-item enums.
- `Sim/npc_roster/__init__.py:190` — the only cross-contract translation there is.
- `board/backlog/PRODUCT-CONSUMER-VOCABULARY.md` — the prose argument.

## Files and assets in scope

`Contracts/schemas/hero-generator.schema.json`, `Contracts/schemas/npc-roster.schema.json`,
`Contracts/schemas/key-location-plans.schema.json`, `Contracts/schemas/world-output.schema.json`,
`Contracts/schemas/asset-list.schema.json`, `Sim/npc_roster/__init__.py`, `docs/npc-roster.md`,
`docs/hero-generator.md`.

## Acceptance and evidence

`tests/test_status_vocabulary.py` passes unmodified:

1. one token means alive across every block with people;
2. one token means no longer alive across the same;
3. no token appears in two `status` vocabularies;
4. every `status` a block emits is constrained by a contract — no free strings, nothing
   emitted that no schema declares.

Three tests must keep passing. Two are controls — the surface is 13 sites and 12 enums, and
the hand-written token maps match what the schemas declare. The third,
`test_a_block_outcome_cannot_be_read_as_a_person`, is a guard rather than a defect: `ok`/
`failed` and `living`/`legend` are disjoint today, so value-matching between those two depths
is safe, and the test exists so that stops being true audibly.

## Documentation impact

Whatever mapping is settled is published, or this recurs. `docs/npc-roster.md` is the natural
home since that package owns the only translation that exists.

## Adversarial review and limitations

- **Global disjointness is not claimed, and an earlier draft of this card claimed it.**
  `complete` disproves it. The surviving guard is scoped to person-versus-block, which is the
  axis the evidence supports. Both peer sessions caught the overclaim independently.
- **Not a defect, checked and dropped:** `npc_roster` reads a missing `status` as `dead` while
  `terrain_villains.is_standing` reads it as `living`. `status` is a *required* property of a
  person in both schemas, so no valid world omits it, and the villain default is deliberate
  backward compatibility for records written before a fall could be recorded. Each is
  defensible alone and the two never both fire. Recorded here so it is not re-found and filed.
- The villain tokens are derived by running the model rather than reading a literal, using
  `hold=99.` as a labelled instrument to make it emit its second token. That band is
  unreachable in any legal configuration; it is not a configuration and must not be read as one.
- `fallen` also appears in `key-locations.schema.json` as prose about a fallen *city*. It is
  unrelated and is not the villain vocabulary.

## Handoff

The lead came from the product red-team session. Its original form — block-level `ok|failed`
confusable with person-level `living|legend` — is **not currently true**: the two sets are
disjoint, so no adapter can read a failed block as a living person today. That is now a
passing guard, and the finding moved to the cross-block liveness predicate, which is real and
already bites. The coordinator supplied the `complete` overlap, with one correction: its table
counted `routed|stranded` as a sixth `status` vocabulary, and that is `route_status`.
