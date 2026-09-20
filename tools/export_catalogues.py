"""Resolve the authoring registries into the catalogue the native core reads.

Authoring, linking and validation stay in Python: this writes the settled result. The
native generator reads traits and rules from here rather than re-implementing the
registry loader, the same way the Unreal asset registry ships as a table. That is data
for the rules, not a generated world; a world is still produced from a seed in process.

Regenerate with this tool and commit the output; `--check` fails when it is stale.
"""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "Sim"))

from icarus_sim.civilization_registry import (  # noqa: E402
    default_profile_id, entity_rules, registry_identity, section)
from icarus_sim.terrain_profiles import civilization_ids, get_profile, profiles  # noqa: E402
from icarus_sim.terrain_nests import profiles as nest_profiles, roles as nest_roles  # noqa: E402
from icarus_sim.terrain_settlements import (  # noqa: E402
    _city_building_packs, _load_city_layout_profiles)
from heritage import resolve as heritage_resolve  # noqa: E402

SCHEMA = "fantasy-world-generator.native-catalogues"
VERSION = 1
DESTINATION = ROOT / "Contracts" / "catalogues" / "native-catalogues-v1.json"
# Entity rule blocks the native placement rules consume. The authoring registry holds
# more; exporting only what is read keeps the shipped table reviewable.
ENTITY_BLOCKS = ("settlement", "economy")


def _plain(value):
    """Sets are authoring conveniences; the shipped table is ordered JSON."""
    if isinstance(value, set):
        return sorted(value)
    if isinstance(value, dict):
        return {key: _plain(item) for key, item in value.items()}
    if isinstance(value, list):
        return [_plain(item) for item in value]
    return value


def city_layout_profiles() -> dict:
    """The normalized layout profiles, in the order the authoring registry lists them."""
    catalogue = _load_city_layout_profiles()
    return {"schema_version": catalogue["schema_version"],
            "fallback_profile_id": catalogue["fallback_profile_id"],
            "profiles": [_plain(profile) for profile in catalogue["profiles"].values()]}


def city_building_packs() -> dict:
    """The normalized packs, in pack order: the weighted draw depends on that order."""
    catalogue = _city_building_packs()
    return {"schema_version": catalogue["schema_version"],
            "fallback_pack_id": catalogue["fallback_pack_id"],
            "packs": [_plain(pack) for pack in catalogue["packs"]]}


def build_catalogues() -> dict:
    identity = registry_identity()
    defaults = section("defaults")
    body = {
        "schema": SCHEMA,
        "version": VERSION,
        "registry": {"schema_version": identity["schema_version"], "revision": identity["revision"],
                     "sha256": identity["sha256"]},
        "defaults": {"profile_id": default_profile_id(),
                     "aggregate_profile_id": defaults["aggregate_profile_id"],
                     "resource_score_factor_label": defaults["resource_score_factor_label"]},
        "civilization_ids": list(civilization_ids()),
        "profiles": {key: get_profile(key) for key in sorted(profiles())},
        "entities": {key: dict({block: entity_rules(key)[block] for block in ENTITY_BLOCKS},
                               parent_race_id=entity_rules(key)["parent_race_id"])
                     for key in sorted(civilization_ids())},
        # Parent races keep registry order: founding rotates initiative through them.
        "parent_races": [{"id": key, **value} for key, value in section("parent_races").items()],
        # Resolved heritage: key traits, the culture derived from them and the language
        # genome derived from that, one entry per civilization. The derivation itself never
        # ships - the native side reads settled values exactly as it reads settled profiles.
        # This is also the bridge the heritage package cannot build for itself: it is a leaf
        # that never imports the registry, so something that imports both has to pair each
        # civilization with its parent race, and this is the one place that already does.
        "heritage": {key: heritage_resolve(key, entity_rules(key)["parent_race_id"])
                     for key in sorted(civilization_ids())},
        "founding_rules": section("founding_rules"),
        "city_classification": {"medium_suitability_min": section("city_classification")["medium_suitability_min"]},
        # Validated by the reference loader on the way out: duplicate ids, unknown
        # media and non-positive weights are authoring errors, not native ones.
        "nest_profiles": [_plain(profile) for profile in nest_profiles()],
        # Feeding roles carry the biome table every animal of that role uses; a
        # species table overrides it, exactly as civilization biome preferences do.
        "nest_roles": _plain(nest_roles()),
        "city_layout_profiles": city_layout_profiles(),
        "city_building_packs": city_building_packs(),
    }
    body["content_sha256"] = hashlib.sha256(
        json.dumps(body, sort_keys=True, separators=(",", ":"), allow_nan=False).encode("utf-8")).hexdigest()
    return body


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--check", action="store_true", help="fail when the committed catalogue is stale")
    arguments = parser.parse_args()
    body = build_catalogues()
    text = json.dumps(body, indent=1, sort_keys=True) + "\n"
    if arguments.check:
        current = DESTINATION.read_text(encoding="utf-8") if DESTINATION.is_file() else ""
        if current != text:
            print("Native catalogues are stale; run tools/export_catalogues.py", file=sys.stderr)
            return 1
        print(f"Native catalogues current: {len(body['profiles'])} profiles, "
              f"{len(body['entities'])} entities, "
              f"{len(body['city_building_packs']['packs'])} building packs, "
              f"{len(body['nest_profiles'])} nest profiles")
        return 0
    DESTINATION.parent.mkdir(parents=True, exist_ok=True)
    DESTINATION.write_text(text, encoding="utf-8")
    print(f"Wrote {DESTINATION.relative_to(ROOT)}: {len(body['profiles'])} profiles, "
          f"{len(body['entities'])} entities, "
          f"{len(body['city_building_packs']['packs'])} building packs, "
          f"{len(body['nest_profiles'])} nest profiles")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
