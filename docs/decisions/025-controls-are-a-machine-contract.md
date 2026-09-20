# 025 — The control surface is a machine contract, not a UI hint

On 2026-09-20 the owner confirmed the shipped shape: a local LLM is packaged inside the
game alongside this code, and it is the only caller of the generator. The player acts in
the game; the orchestrator interprets that action and translates it into calls. No control
here is ever touched by a person.

That changes what a control's metadata is for. A description read by a developer can be
terse, because the developer can read the code beside it. A description read by a small
model choosing a control and a value has to carry the effect on the world, and the model
cannot ask a follow-up question.

## Decision

- **`terrain_world.registry(3)` is the single source of truth for the control surface**, and
  it is published as generated data at `Contracts/catalogues/world-controls-v1.json` by
  `tools/export_controls.py`, in the mirror-channel style decision 020 established for
  authoring catalogues. A packaged mirror ships inside the Python package; the same file is
  staged into `Plugin/Data/` so a cooked game reads it with no Python present.
- **Every published control carries a description and a unit.** `CONTROL_PROSE` in
  `terrain_world.py` is total over the registry and `registry()` raises when it is not, so a
  control added without a description fails at import rather than reaching a consumer as its
  own field name with the underscores changed.
- **A description states what the control does to the world**, in terms an intent can be
  mapped onto. The house exemplars are the `river_threshold_km2` message at
  `terrain_world.py` and the `orogeny` comment carried from `Core/config.hpp`: both name the
  effect, the interaction and the failure mode.
- **Three statuses, because a caller cannot see two of them.** `open` behaves as declared.
  `pinned` has `min == max` and refuses every value — seven controls, including all four
  hidden-school occurrences and the disabled sky islands. `inert` accepts every value and is
  read by nothing on this recipe — one control, `stubbornness`. A pinned control announces
  itself on the first attempt; an inert one never does, which is why it has to be declared.
- **Precedence is published in both directions.** Nine controls are derived from the
  authored world shape unless individually overridden, and this happens on the default path
  too because an absent `circumference_km` falls back to the `world_size` preset. Each
  derived control names what it derives from; each shape input names what it overrides. Both
  lists are extracted from the code with `ast` rather than transcribed.
- **No control is renamed and no bound is changed by this decision.** Shipped names are in
  published schemas and pinned tests. The cost of the collision is confusion; the cost of the
  rename is every consumer and every fixture.

## Reason

The surface was exposed at three widths that disagreed — 209 controls in the reference, 21
rows in the native bounds table with four of them wrong, and five reachable from the
packaged plugin. Underneath that, 54 of 209 controls described themselves with their own
field name and 43 shipped no unit at all, and 29 of those were named nowhere in `docs/` or
`Contracts/`. A tool schema generated from that state publishes placeholders to the model
that has to use it.

Making the registry generated data rather than a Python dict read at runtime is what lets
the native core and the plugin stop keeping hand-written copies, which is where the four
divergences came from.

## Consequences

- `tools/export_controls.py --check` runs inside `validate_repo.py --stage checks`, so a
  registry edit that does not regenerate the catalogue fails the gate.
- `tests/test_control_catalogue.py` checks the projection in both directions, that every
  pinned control is marked and says why, and that precedence resolves from either end.
- `describe_controls()` filters by group, name and query and hides pinned controls by
  default, because the whole catalogue is 33,454 bytes and a small model would otherwise pay
  roughly nine thousand tokens for a table it needs once.
- World document bytes change, because `registry()` is published inside every world at
  `recipe.parameters`. No terrain, layer or settlement value moves. Decision 023 already
  makes generated worlds disposable.
- `stubbornness` is now declared inert rather than quietly doing nothing. Making it live is
  a separate change and needs a ticket.
