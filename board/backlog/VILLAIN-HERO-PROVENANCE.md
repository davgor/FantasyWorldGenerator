# VILLAIN-HERO-PROVENANCE — a villain never traces back to who it was

Owner: none. State: open, unowned. Raised by the user, routed through the coordinator, carded by
the bug-hunt session. Not started.

## The gap

`docs/super-villains.md` and `board/in-progress/SUPER-VILLAINS.md:13` state the requirement
outright: *"existing heroes can become them when their influence expands to devastating reach."*

Nothing implements it. `terrain_villains.advance()` mints `villain-{age}-{node}` from region tier
accumulation and nothing else. There is no hero linkage anywhere in the module — no field, no
lookup, no reference to `heroes`. A villain is a name the world puts on a concentrating region,
full stop.

So a requirement was written, agreed and never built, and the card that states it has been sitting
in `in-progress` with the step never started. This is the second time tonight a published claim
turned out to have no implementation behind it; the other was `terrain.biome_contract`, which was
implemented and then violated.

## The sequencing problem underneath it

The two passes run in the wrong order for the obvious implementation:

- `advance_villains` — `terrain_history.py:334`
- `_attach_heroes` — `terrain_history.py:557`

**Villains are seated more than two hundred lines before the cast exists.** So a villain cannot be
chosen *from* the heroes of its own age, because at seating time there are none. Any fix has to
answer that, and the three candidate answers are meaningfully different:

1. Seat from the **previous** age's cast, which the world still carries. Cheapest, and it fits the
   pacing model — a villain that was somebody is a villain who had time to become one.
2. Move the villain pass after `_attach_heroes`. Changes the order of two passes that several
   other things sit between, and would move every world.
3. Attribute **after the fact**: seat as today, then let the hero pass bind a villain to whoever
   best matches. Keeps generation order untouched.

## The user's framing, which narrows it usefully

**"The linkage is provenance, not motivation."** A villain should trace back to who it was, even
if nothing in its behaviour consults that. That rules out the expensive reading — no hero
attribute needs to feed reach, growth, tier or the fate lottery — and makes option 1 or 3 viable
where option 2 probably is not worth its cost.

It also means the linkage is a **record**, which puts it in the same family as
`VILLAIN-FALL-UNRECORDED.md`: what a villain leaves behind, and what it came from, are the two
ends of the same question. The `fallen` mark already carries `born_age`; a `risen_from` beside it
is the natural shape.

## Dependencies and unresolved decisions

- Open: which of the three sequencing answers. Not this card's to choose.
- Open: whether a villain must always have been someone. A region can concentrate with no
  plausible candidate nearby, and forcing a linkage would invent a person. A nullable provenance
  field is almost certainly right, matching how `fallen_mark` declines to record a villain that
  marked nothing.
- Sequence behind `VILLAINS-NO-SCHEMA.md`: this adds a field to a block with no contract.
- `terrain_history.py` is a seam; take it through the coordinator.

## Sources consulted

`Sim/icarus_sim/terrain_villains.py` (`advance`, uid minting), `Sim/icarus_sim/terrain_history.py:334,557`,
`board/in-progress/SUPER-VILLAINS.md:13`, `docs/super-villains.md`.

## Files and assets in scope

`Sim/icarus_sim/terrain_villains.py`, `Sim/icarus_sim/terrain_history.py`,
`Sim/tests/test_super_villains.py`, `docs/super-villains.md`, and whatever schema
`VILLAINS-NO-SCHEMA.md` produces.

## Acceptance and evidence

A seated villain in a world with a cast carries a resolvable reference to a person, or an explicit
null with a reason. The reference survives an age advance — which is the hard part, because hero
uids and the villain's own region anchor renumber on different schedules, and this is precisely the
class of id-across-age-boundaries breakage that has bitten this codebase before.

Needs a multi-age run at `villain_rise > 0` with heroes enabled.

## Adversarial review and limitations

The cheap version of this — stamp the nearest hero's uid on the villain — is worse than nothing. It
would read as a causal claim the generator cannot support, and a story layer would build on it.
Whatever lands should make clear whether it means "this person became this villain" or "this
villain rose where this person was", because those are different statements and only the first is
what the requirement asks for.

This card describes an unbuilt feature, not a defect in running code. Nothing is currently wrong;
something promised is currently absent.
