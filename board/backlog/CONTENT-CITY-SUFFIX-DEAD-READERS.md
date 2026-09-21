# CONTENT-CITY-SUFFIX-DEAD-READERS — a retired disambiguator that six places still read for

Owner: none. State: **part delivered 2026-09-21, two sites left and blocked** — see
[Delivered](#delivered) and [Not delivered](#not-delivered) at the foot. Sibling of
[CONTENT-AGE-SUFFIX-IN-NAMES](CONTENT-AGE-SUFFIX-IN-NAMES.md): same subject, opposite end.
That card is about the disambiguator that is live and should not be; this one is about the
disambiguator that is dead and is still being read for.

## Observed behavior

Settlement naming moved off `terrain_settlements._settlement_names`' round-robin over twelve
English nature words plus the literal string `' City'`, and onto `heritage.settlement_name`
(`board/done/HERITAGE.md`). The producer moved. Five readers did not.

**Two of those five are tests asserting directly opposite conventions about the same strings.**

- `Sim/tests/test_terrain_humans.py:45` asserted every settlement name **ends with** `' City'`.
- `Sim/tests/test_heritage_consumers.py:60` asserts no settlement name **contains** `' City'`.

`add_settlements` calls `named=_settlement_names(seed,selected,points,peoples)` and the
`sites=[]` loop immediately below builds `result['settlements']['sites']` from exactly that, so
these are one producer and one set of bytes. The second test calls `_settlement_names`
directly; the first reads the same strings two steps downstream. There is no reading on which
both are right. Only the stale one failed, so the contradiction was invisible — it read as one
broken test rather than as two claims that cannot both hold.

The other three readers strip the suffix and therefore fail silently (line numbers as found on
2026-09-21; three of these files were being written by other sessions the same night):

- `Sim/key_locations/core/naming.py:18` — `SUFFIX = ' City'`, plus a module docstring at :3-5
  describing the round-robin in the present tense.
- `Sim/hero_generator/history.py:72` — `name.replace(' City', '')`.
- `Sim/npc_roster/sites.py:157` — `.replace(' City', '')`, beside a live `(Age N)` split.

A sixth reader, missed by a grep for `' City'` because it writes the string as `'Fern City'`:
`Sim/tests/test_key_locations.py:909`, `assertEqual(naming.short_name('Fern City'), 'Fern')` —
the test that pins the third of those three.

## Which convention is live, and how that was established

By measuring what the generator emits, not by reading the readers.

- `Fixtures/sample-world-v1.json` (seed 42, size 33, generator 16, recipe 3) contains the
  substring `' City'` exactly **five** times, and all five are the same prose sentence boundary
  in `population_budget.method` — `"...remain excluded. City assets are selected from..."`.
  **Zero of its 35 settlement names and zero of its 38 ruin names carry the suffix.**
- `_settlement_names` over seeds 1, 42, 99, 1234 and 20260921, six peoples each, produces no
  name ending in `' City'`.

The absent-suffix convention is live. `test_terrain_humans.py:45` was the stale reader.
Corroborating: the assertion at `test_heritage_consumers.py:60` sits inside
`test_no_placeholder_english_survives`, whose next line is `assertNotIn('Alder', name)` —
`Alder` being one of the twelve retired nature words. That test is specifically the guard that
the old placeholder naming is gone.

## Why it matters

A silent strip is worse than a broken one. `short_name('Gulf City')` returning `'Gulf'` renames
a place that is really called that, and the next person to read any of these three sites sees
live disambiguation where there is none — which is how the contradictory pair survived in the
first place. Repairing only the failing assertion leaves that impression in three files.

## Proposed mechanism

1. Bring `test_terrain_humans.py:45` into line with the measurement, and assert something the
   live namer actually guarantees rather than only the absence of the retired suffix.
2. Delete the retired strip from each of the three consumers, leaving whatever each one does
   that is still live — the empty-to-`None` normalisation in `key_locations`, the `(Age N)`
   split in `npc_roster`.
3. Where a consumer's tests or pinned fixtures name their synthetic cities in the retired
   convention, rename the fixture cities rather than weakening the assertions: the derived
   strings then come out identical and the pinned fixture stays valid.
4. A test that pins the live convention over a spread of seeds, so a future reader cannot be
   written against the retired one without a failure.

## Dependencies and unresolved decisions

- Removing the strip in `hero_generator` and `npc_roster` is not a line change. Both are
  exercised only by synthetic worlds whose cities are named `Alder City`, `Bracken City`,
  `Umber City` and so on, and by two committed expected-output fixtures that carry those names
  (`Fixtures/hero-generator-v1.json`, 10 occurrences; `Fixtures/npc-roster-v1.json`, 2). The
  strip fires there, so removing it renames every derived string in both.
- `board/backlog/CONTENT-AGE-SUFFIX-IN-NAMES.md` removes the `(Age N)` disambiguator. When it
  lands, `npc_roster.sites._short_name` and `hero_generator.history.short_name` have nothing
  left to do at all and should go rather than become identities.

## Acceptance and evidence

- No test in the tree asserts that a settlement name carries `' City'`.
- No consumer shortens a name on the retired convention; a place called `Gulf City` reaches
  derived text intact.
- A multi-seed test pins the live convention.

## Delivered

2026-09-21. **The contradiction is closed and one of the three silent strips is gone.**

- `Sim/tests/test_terrain_humans.py:45` now asserts the live convention. It had been failing
  all night on `AssertionError: False is not true` — an `assertTrue(all(...))` that named
  neither the site nor the string. It is now a loop that asserts `kind == 'city'`, that the
  name does **not** end in `' City'`, and that `name_gloss` is non-empty, each reporting the
  offending name. `test_hinterland_invariants_and_stage_isolation` passes.
- `Sim/key_locations/core/naming.py` — `SUFFIX` deleted, `short_name` reduced to the
  empty-to-`None` normalisation that was the only live part of it, and the module docstring's
  present-tense description of the round-robin rewritten to the past. Its test in
  `Sim/tests/test_key_locations.py` now asserts `short_name('Gulf City') == 'Gulf City'`.
- `Sim/tests/test_heritage_consumers.py` gains `RetiredCitySuffixTests` (3 tests): the live
  convention over five seeds, the `key_locations` reader, and the jobs the helpers still have.
  Written before the change; it failed on
  `AssertionError: 'Gulf' != 'Gulf City'`.

196 tests green across `test_heritage_consumers`, `test_key_locations`, `test_npc_roster` and
`test_story_web`, plus `test_terrain_humans.HumanHinterlandTests`.

No conformance record was touched, because none claims any of these modules:
`tools/docs_check.py --list-uncovered` lists `Sim/key_locations/core/naming.py`,
`Sim/npc_roster/sites.py`, `Sim/icarus_sim/terrain_settlements.py` and every `hero_generator`
stem as unclaimed, and no record names any of these test modules as proof.

## Not delivered

**Two of the three silent strips are still in place**, at `Sim/hero_generator/history.py:72`
and `Sim/npc_roster/sites.py:157`. Both were removed, measured, and put back. Removing them is
correct and it is not a line change:

- `hero_generator`: breaks 3 tests in `Sim/tests/test_hero_countryside.py` and
  `Sim/tests/test_hero_generator.py`, and `Fixtures/hero-generator-v1.json` (a committed
  expected-output fixture carrying `Alder City`, `Bracken City`, `Cedar City`, `Dunlin City`,
  `Ember City`, `Glen City`) goes stale.
- `npc_roster`: breaks `test_the_pinned_world_yields_the_pinned_roster` and
  `test_a_castle_carries_no_civilization_so_it_inherits_its_core_city`
  (`'the fortress above Bracken City' != 'the fortress above Bracken'`), and
  `Fixtures/npc-roster-v1.json` goes stale.

The cheapest correct repair is mechanism step 3 — rename the synthetic fixture cities
(`'Bracken City (Age 1)'` → `'Bracken (Age 1)'`, `'Umber City'` → `'Umber'`, and the six in
`test_hero_generator.py`) so every derived string comes out byte-identical and the pinned
fixtures need only the same textual rename. For `npc_roster` that is four lines.

Both were left alone here because `Sim/tests/test_npc_roster.py` is fenced to another running
session, and because `Sim/hero_generator/wells/countryside.py`, `hooks.py`, `__init__.py` and
`Sim/tests/test_hero_countryside.py` were all being written by a third session while this was
measured (their mtimes moved between two runs, and three `test_hero_countryside` errors that
appear in the second run are theirs, not this change's). Each strip now carries a docstring
saying it is retired, why it is still there, and what removing it costs, so neither reads as
live disambiguation any more.

## Adversarial review and limitations

The measurement is one committed world plus five seeds of the naming function alone. It is
strong on the producer — `_settlement_names` is a pure function of `(seed, nodes, points,
peoples)` and there is no other path to a settlement name — and it says nothing about a
consumer that might synthesise the suffix itself. Grep says none does.

The synthetic-fixture names in `test_hero_generator.py`, `test_hero_countryside.py`,
`test_key_locations.py`, `test_npc_roster.py` and `test_story_web.py` are themselves written in
the retired convention. That is legal — a fixture may call a city anything — but it is why the
three strips still fire, and it is the reason this card is about five sites and its repair
touches twelve files.
