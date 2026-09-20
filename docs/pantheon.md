# Pantheon: religion schema 1 and the visitation API

Gods may exist. Which ones do is decided by the world, how they are arranged by the world plus the seed, and who worships them by the peoples. In generation the gods are back-burner characters: records with no terrain, food, threat or influence effect. They act only when the orchestrator, the game or AI host driving the JSON API, summons one, and a god walking the mortal plane is highly disruptive.

Reference: `Sim/icarus_sim/pantheon.json` (catalogue, ships as data per decision 020), `terrain_religion.py` (resolution), `terrain_visitation.py` (summons). Both modules are Python only, like the age API; the native core does not port them.

## Catalogue

Twenty-five gods in four families, eleven cosmologies, an affinity table per civilization. Every god record carries an independent existence rule, one or two aspects, domains, allies and rivals, school affinities, the nest families it purges when it walks, and the sentence its smiting leaves in a ruin.

- **School gods** (8): one per leyline, manifest when that network has at least one key point. Aspect is *Sovereign* below the midpoint of mean intensity × (1 + instability) and *Wild* above it; undead nests push Umbral and infernal nests push Infernal toward Wild.
- **Ancestor gods** (3): The First Hearth (human), The Elder Star (elf), The Deep Forge (dwarf), manifest when that parent race founded a city in the world's history, ruins included. Each carries a per-civilization epithet.
- **Feature gods** (7): The Drowned Mother (ocean covers half the globe, or a maritime, large-island or tidekin city), The Sky Court (a sky settlement), The Great Wyrm (a dragon nest), The Unnamed Outside (an aberrant nest), The Keeper of Fallen Cities (a ruin), The Wanderer (a diaspora), and **The Turning Moon** (always; *Pale Warden* when the almanac year leans Still, *Turning Face* when it leans Restless).
- **Civic gods** (7): always manifest, magic or not. Six fold into a school god as a saint when that school manifests and the cosmology allows folding (not under The Mosaic or The Ancestor Halls); they stay listed either way so consumers can always find them. The Red Field never folds.

Existence rules are small data expressions (`always`, `school`, `race`, `races`, `civilization_city`, `ocean_share`, `sky`, `dragon`, `nest_family`, `ruins`, `diaspora`, `magic_enabled`, `magic_disabled`, `primordial_count`, `gods`, `any`, `all`) read from what the generator already exports. A god that qualified earlier and no longer does is `sleeping` and keeps its last aspect.

## Cosmology

Eligible templates are those whose prerequisites hold; each has a fit weight (base plus a per-fact term such as the number of primordial networks, dragon nests, ruins or founding races; The Turning Moon weighs `lunar_influence × 8`; The Mosaic keeps a small constant so it is the fallback). One is drawn with `child_seed(seed, 'pantheon-v1')`. The export lists the eligible set with its weights.

## Faiths

Each civilization with a live city takes its ancestor god as patron, then draws up to three more from the manifest set with `child_seed(seed, 'faith-v1-' + civilization)`, weighted by the affinity table (+2 strong, +1 mild, −2 aversion), +1.5 for the cosmology's high gods, +0.5 for civic gods, plus the mean potency of each god's schools under its cities. Cities within reach of a dragon, infernal, undead or aberrant nest add a `fear` entry for the matching god. A founding with reason `religious_schism` becomes a sect: patron and first manifest rival swapped, a new epithet. Feasts come from the lunar almanac: surge days of worshipped school gods, full moons for the moon god, and hollow nights kept as dread, or as vigils by Wild Umbral and Infernal cults. A civilization converted by a visitation keeps that god as patron for as long as the god exists.

## Export

`religion`: `version`, `catalogue {schema_version, revision, sha256}`, `facts` (the resolved inputs), `cosmology {id, name, high, arrangement, eligible}`, `gods[]` (`status` absent, manifest, sleeping or walking; `aspect`, `aspect_name`, `evidence`, `saint_of`, `avatar` while walking), `faiths{civilization}` (`patron`, `gods`, `names`, `fear`, `sects`, `feasts`, `conversion`, `weights`), `sites[]` (a Loom-Mother cult at each self-destruction ruin with `born_under_surge` when that age's Weave tide was ≥ 1.3, a Red Field shrine at each war ruin, theophany and pilgrimage sites from visitations), `visitations[]`, `method`, `limits`.

Religion is resolved after beast nests (stage 13), at the end of every age transition, after every age-API step, and after every visitation. It reads only final-stage inputs, so it is never stage-dependent.

## Visitation API

```
POST /world/summon
{"api_version": 1, "world": <recipe-3 world, phase >= 13>, "god_id": "god_fire",
 "target": {"city_uid": "..."} | {"node": 123}, "wrath": 0..1, "variation": uint32, "day": int}
{"api_version": 1, "world": <world with a walking god>, "god_id": "god_fire", "depart": true}
```

`terrain_visitation.visitation_request(body)` is stateless: same input, same output; the caller's object is unchanged; persist the returned world to call again. The world must pass the age boundary and carry `astrology`, `lunar_almanac` and `religion` version 1 with the current catalogue identity. Only a manifest or sleeping god can be summoned; an absent god does not exist in this world; a walking god cannot be summoned twice; the target must be land; at most eight visitations per world.

A summons, in order (`religion.visitations[].order`):

1. **Avatar cluster.** The arrival day is `founding.end_year × 360` unless the request names a `day`. In each of the god's schools (school gods their own; feature and civic gods their affinities; the moon the four schools of the hemisphere leaning that day) a key point of intensity 4 at the target plus four ring points of intensity 3 at half a settlement spacing on seeded bearings. Local potency saturates, so `dominant_magic` flips and biomes mutate across the cluster.
2. **Opposed suppression.** Within reach (three settlement spacings) every node and line of the opposed schools (radiant⇄infernal, weave⇄umbral, fire⇄water) is scaled by `1 − 0.5 × wrath`; the record restores them exactly at departure.
3. **Divine fate lottery.** Every city within reach rolls the age lottery (ley pressure and nest threats as usual) with one more cause, `divine_<god_id>`, of weight `0.6 × wrath × (1 − d/reach) × aspect × faith`: Wild doubles, Sovereign halves; a city that worships the god counts a quarter, one whose patron is a rival counts double. Ruins carry the god's smiting sentence, a legacy key point of intensity 4 in the god's school, and `visitation`. Wars are not rolled. Surviving worshippers within reach gain `favor` and a lower `regional_threat` in the refreshed assessment.
4. **Rebuild.** The age transition's tail: fields, biomes, civilization, nests, threat assessment, almanac. Nests of the god's purge families within reach are then removed until the next age recomputes them.
5. **Conversion.** Every surviving civilization with a city within reach takes the god as patron. A theophany site marks the target. The god's status becomes `walking` with its avatar.

Departure (`depart: true`, and automatically at the next age transition): the cluster collapses to one footprint key point of intensity 3.5 at the target, opposed intensities are restored, the theophany becomes a pilgrimage site, the god returns to `manifest`, and `departed_age` is set. The footprint, the ruins, the mutated biomes and the conversions are the lasting impact.

Every distance is a ratio of `settlement_spacing`, never a metre constant or a raster cell, so world scale and raster size cannot turn a local visitation into a regional one.

## Limits

Gods are narrative provenance until summoned; a visitation is a bounded stateless operation with no runtime clock, actor or combat model; the avatar is a ley cluster, not a creature. Names and epithets are authored English. No asset identities and no temple dedications are added. The Unreal plugin receives the religion and visitation JSON but does not yet act on it.
