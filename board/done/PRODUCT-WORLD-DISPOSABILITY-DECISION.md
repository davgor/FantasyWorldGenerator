# PRODUCT-WORLD-DISPOSABILITY-DECISION — eighteen statements destroy every existing world; ruled 2026-09-20

Owner: none. State: **closed by a user ruling, 2026-09-20.** Found by the product red team
auditing `233182e`.

> **Closing evidence.** The user ruled that generated worlds are disposable. The record this
> card asked for is
> [023 World compatibility policy](../../docs/decisions/023-world-compatibility-policy.md),
> which carries all five elements requested under Proposed mechanism: the policy in one
> present-tense sentence; the milestone at which it changes, named as phase 2 of the product
> roadmap — the AI TTRPG text UI — and explicitly not ML-13; what a consumer may rely on today,
> which is deterministic replay from an exported `Config` under the same generator and nothing
> across generators; the additive `key_locations` block named as the one compatible-change
> pattern to copy, with the byte-identical replay run that proved it; and where the
> regeneration statements live. A pointer to 023 was added to `Contracts/README.md` beside the
> world-envelope paragraph, and the record is indexed in `docs/README.md`.
>
> **One correction to this card, carried into 023.** The enumeration below is an undercount.
> The real figure is **eighteen statements across fifteen lines**, not eleven: this card
> omitted five algorithm-revision statements in `docs/terrain-world-layers.md` of exactly the
> same kind as the ones it lists, and counted the registry-identity line as one where it
> carries two. The card’s argument survives the correction and is strengthened by it. 023
> carries the corrected count and the counting rule; it deliberately carries no line table,
> because both documents move.
>
> **The line numbers quoted below are frozen and two of them have already moved.** The pointer
> paragraph added to `Contracts/README.md` under this ruling shifts its second regeneration
> statement from line 22 to line 24, and a pointer added to `docs/terrain-world-layers.md`
> shifts every line this card cites in that file. Re-derive them with `grep -ni regenerat`
> rather than trusting the enumeration below.

> **2026-09-20: the grid ruling made this card load-bearing.** The ceiling moves to 1025, which
> admits a fifth terrain octave. The octave admission filter at
> `Sim/icarus_sim/terrain_tectonics.py:178` admits an octave only while its `wavelength` exceeds
> twice the grid step, so a size-17 world admits none and a size-513 world admits all five —
> recomputed from the recipe-3 defaults and confirmed against thirteen worlds under `Artifacts/`.
> **Admitting a fifth octave changes generated terrain, so every saved world becomes stale.** That
> is the twelfth instance of the pattern this card documents, and the first one whose blast radius
> is every world anyone has kept.
>
> The ruling authorises the widen. **It does not authorise regenerating or deleting anyone's data**,
> and the coordinator has told the performance session so explicitly. The gap between "this change
> invalidates saved worlds" and "therefore we may discard them" is exactly the gap this card exists
> to close, and nothing has closed it. If the policy is written before the widen lands, the widen
> is a routine change with a stated consequence; if it is not, the consequence lands silently for
> the twelfth time.

## Requested behavior

One decision record stating the world-compatibility policy out loud, and one place a consumer can
read it. Either:

- **"Worlds are disposable until X"** — named milestone, stated reason, and an explicit
  acknowledgement that every generator change may invalidate every saved world until then; or
- **an owner for world migration**, with the first slice scoped.

Not both, and not neither. Neither is where the repository is now.

## The defect

Grepping the two canonical contract documents for regeneration requirements returns **eleven**
distinct statements:

- `Contracts/README.md:12` — "earlier worlds must be regenerated rather than advanced";
  "Algorithm-8/9/10/11 worlds and retired generic human profile IDs require regeneration";
  "Recipes 1/2 and old age/save contracts are rejected and must be regenerated"
- `Contracts/README.md:22` — "Old worlds require regeneration."
- `docs/terrain-world-layers.md:24` — "Recipes 1 and 2 are retired and rejected: existing worlds
  must be regenerated. Seed compatibility with those recipes is intentionally broken by the
  clean-start biome migration."
- `docs/terrain-world-layers.md:142,148,190,214,216,218,234` — seven more, each attached to a
  different schema or registry revision, each a consequence of other work

Searching `board/` for an owner of world migration, save compatibility, or forward/backward
compatibility returns **nothing**. Not an open ticket, not a deferred one, not a decision record
saying "deliberately not yet." `board/done/MIGRATION-CULTURES.md` is in-world population movement,
not save migration.

**Every one of the eleven is individually defensible.** A pre-release generator that breaks seed
compatibility to fix a biome migration is making the right trade, and `docs/terrain-world-layers.md:24`
says so in as many words. The defect is the aggregate: a policy with eleven instances and zero
statements is indistinguishable from an oversight, and it is currently discoverable only by
grepping for the phrase.

## Why it matters

The roadmap's phase 2 is an AI TTRPG text UI and phase 3 is a 3D top-down game. Both imply a player,
a campaign, and a world someone has spent hours inside. On current policy any change that moves any
of a dozen version integers destroys every existing world, and the destruction is announced in a
sentence inside a paragraph about fortress counts.

There is a live example of the cost already, and it is not hypothetical: `Contracts/README.md:12`
notes that `key_locations` "is additive and carries its own schema, so a consumer that does not read
it is unaffected and a world generated without it replays identically." That is a carefully designed
compatible change, written by someone who clearly held the whole policy in their head at the time.
It is the only sentence of the eleven that describes compatibility rather than its absence, and
nothing marks it as the good case.

## Proposed mechanism

`docs/decisions/023-world-compatibility-policy.md`, stating:

1. **The current policy**, in one sentence, in the present tense.
2. **The milestone at which it changes** — the natural candidate is the first release with a
   real player-facing consumer, which is phase 2, not ML-13.
3. **What a consumer may rely on today** — that a world replays deterministically from its exported
   `Config` under the same generator, and nothing across generators.
4. **The one compatible-change pattern the repository has already discovered**: a block that is
   additive, carries its own schema and leaves replay identical does not force regeneration. That
   is `key_locations` and it should be named as the pattern to copy.
5. **Where the eleven statements live**, so a future reader finds them without the grep.

`Contracts/README.md` and `docs/terrain-world-layers.md` each gain one pointer to it. The eleven
statements stay where they are — they are true and they are local to their subject.

## Dependencies and unresolved decisions

- **This needs the user, not an agent.** It is a product-scope decision about what the generator
  promises, and the honest options differ by months of work. An agent writing it unilaterally would
  be inventing a commitment.
- Interacts with `PRODUCT-BLOCK-REGISTRY`: a registry that records which blocks are additive is
  where pattern (4) would be enforced rather than described.
- Interacts with the time-advancement work now landing, which introduces a deliberate
  output-changing claim decay — a twelfth instance arriving while this card sits open.

## Sources consulted

`Contracts/README.md:12,22`; `docs/terrain-world-layers.md:24,142,148,190,214,216,218,234`;
`board/` full text search for migration/compatibility ownership (no ticket);
`board/done/MIGRATION-CULTURES.md` (unrelated); `PLAN.md` §"Acceptance, maintenance and first
action"; roadmap phases per the product owner.

## Files and assets in scope

New `docs/decisions/023-world-compatibility-policy.md`; one pointer line each in
`Contracts/README.md` and `docs/terrain-world-layers.md`; `docs/README.md` decision index.

## Acceptance and evidence

A reader who has never seen this repository can answer "if I generate a world today, what survives
tomorrow's commit?" from one document. `tools/docs_check.py` link and numbering checks pass — note
the decision numbering check at `tools/docs_check.py:268` and that 023 is the next free number after
the renumbered 022.

## Documentation impact

Entirely documentation. No behavior changes and none should; a card that quietly acquires a
migration implementation has failed.

## Adversarial review and limitations

**The strongest objection is that this card asks for a paragraph and dresses it as a finding.** It
does. The defence is the grep: eleven statements, zero owners, and a twelfth arriving this week. A
paragraph that has not been written in eleven opportunities is not being deferred, it is being
missed.

**The second objection is that the answer is obvious** — of course a pre-release generator breaks
compatibility, everybody on the fleet knows it. That is exactly the failure mode. It is known by
people and recorded by nobody, and the sessions that know it are ephemeral. The coordinator's own
fleet conventions C1 and C2 have the same problem and the same fix.

**Where this card could be wrong:** if a decision record already states this and I missed it. I
searched `docs/decisions/` for compatibility language and found 015 (retiring legacy biome and save
compatibility) and 002 (export artifact is not a runtime package), both of which touch the area and
neither of which states a policy. 003–013 were allocated in the source repository and did not come
across with the extraction, so **it is possible this decision was made and lost in the gap.** If
anyone knows that to be true, that fact belongs in the new record rather than being rediscovered.

## Handoff

Found by grepping the canonical contract documents for regeneration requirements, then searching
`board/` for an owner and finding none. Full reasoning in
`docs/reviews/233182e-product-red-team.md`, Finding 2 — note that document's own placement warning.
