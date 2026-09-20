"""Packaged heritage documents: race key traits, the derivation rules, the root lexicon, overrides.

Traits are data so a people can be added or retuned without touching code. Each file carries
its own ``revision``; the combined revisions travel with every resolved people so a consumer
can tell a heritage edit from a world change.

This package is a leaf. It never imports ``icarus_sim``, the same contract ``story_web``
states for itself, which is why ``resolve`` is handed a parent race rather than looking one
up. The cost of that independence is two enums restated here - the civilization ids and the
magic schools - and the price is paid in ``tests/test_heritage_registry_binding.py``, which
asserts both against the registry in each direction so neither can drift unnoticed.
"""
from importlib.resources import files
import json
import re

POLICY_FILES = ('traits', 'derivation', 'lexicon', 'overrides', 'appearance')

# The eight schools generation can actually raise. The four Outside schools in
# terrain_leyline_history.HIDDEN_SCHOOLS are deliberately absent: nobody has a cultural
# stance toward a school they have never heard of, and no world can produce one.
KNOWN_SCHOOLS = ('weave', 'umbral', 'infernal', 'radiant', 'fire', 'water', 'earth', 'air')
HIDDEN_SCHOOLS = ('blood', 'void', 'rot', 'eldritch')

CRAFTS = ('seafaring', 'husbandry_and_tillage', 'metal_and_forge', 'stone_and_vault',
          'wood_and_weave', 'glass_and_mechanism', 'herb_and_dye', 'ice_and_preserve',
          'clay_and_kiln')
CRAFT_COUNT = 2

AXES = {
    # Soma - articulatory; these drive the phoneme inventory.
    'body_scale': ('small', 'compact', 'mid', 'tall', 'towering'),
    'vocal_tract': ('narrow', 'even', 'broad', 'resonant_chest'),
    'breath_capacity': ('short', 'steady', 'deep', 'sustained'),
    'hearing_band': ('low_weighted', 'flat', 'high_weighted', 'wide'),
    'lifespan_tempo': ('brief', 'human', 'long', 'ancient'),
    'dentition': ('blunt', 'even', 'prominent_canine', 'tusked'),
    # Register - habitat acoustics; these drive prosody and script.
    'speech_environment': ('open_plain', 'surf', 'forest', 'stone_hall', 'wind_scoured',
                           'humid_canopy', 'market_din', 'terraced_valley'),
    'carrying_register': ('quiet', 'conversational', 'carrying', 'calling'),
    'writing_surface': ('none', 'knot_and_cord', 'incised_stone', 'carved_wood',
                        'inked_hide', 'pressed_fibre_paper'),
    # Social - these drive culture.
    'kinship': ('nuclear_household', 'extended_clan', 'lineage_house', 'age_cohort',
                'crew_and_berth', 'guild_family'),
    'authority': ('elder_council', 'hereditary_lord', 'guild_assembly',
                  'acclaimed_war_leader', 'temple_seat', 'consensus_moot'),
    'mobility': ('rooted', 'seasonal_transhumance', 'voyaging', 'caravan',
                 'frontier_expanding'),
    'memory_mode': ('oral_formulaic', 'sung_lineage', 'written_archive', 'carved_record',
                    'ledger_and_seal'),
    'craft_focus': CRAFTS,
    'outsiders': ('hostile', 'wary', 'transactional', 'hospitable', 'assimilating'),
    'magic_stance': ('untrained', 'ritual_communal', 'scholarly_licensed',
                     'inherited_bloodline', 'taboo_avoidant', 'bargained_with'),
    'magic_school': KNOWN_SCHOOLS,
}
LIST_AXES = frozenset({'craft_focus'})

# Height envelopes for the five `body_scale` values, in metres, as a (floor, ceiling) pair
# the authored band has to lie inside. These are physical constraints rather than authoring
# taste, so they live here beside `phonemes.GATES` instead of in the table they police: a
# subrace cannot be handed a stature its own key trait contradicts. The `compact` and
# `small` ceilings are what make "no dwarf stands over 4 ft 5 in" - 1.3462 m - a property
# of the loader rather than a promise in a comment.
BODY_SCALE_HEIGHT_M = {
    'small': (0.92, 1.26),
    'compact': (1.10, 1.34),
    'mid': (1.38, 2.05),
    'tall': (1.55, 2.20),
    'towering': (2.00, 3.20),
}

# The same argument for `lifespan_tempo`: an ancient people that dies at ninety is an
# authoring slip, not a design decision, and the tempo axis is what a name, a culture and
# an elder sprite are all already keyed on.
LIFESPAN_TEMPO_YEARS = {
    'brief': (55, 120), 'human': (70, 160), 'long': (180, 520), 'ancient': (500, 1600),
}

# Appearance: what a people looks like. Authored per race and extended per subrace, never
# derived - skin range, ear form and dress are new information, not a restatement of the
# seventeen axes. Blocks are ordered from what a modeller needs first to what a concept
# artist needs last.
APPEARANCE_BLOCKS = {
    'frame': ('height_m', 'mass_kg', 'build', 'sexual_dimorphism'),
    'proportion': ('heads_tall', 'shoulder_width_ratio', 'leg_length_ratio',
                   'hand_length_ratio'),
    'coloration': ('skin', 'hair', 'eye'),
    'features': ('face_shape', 'ear', 'eye_shape', 'nose', 'brow', 'jaw', 'lips', 'teeth',
                 'skin_texture', 'markings'),
    'grooming': ('scalp_texture', 'facial_hair', 'body_hair', 'common_styles'),
    'life_stages': ('child', 'adolescent', 'adult', 'elder', 'max_years'),
    'attire': ('layering', 'materials', 'dye_character', 'signature_item', 'footwear'),
    'art_direction': ('silhouette', 'reads_as', 'avoid'),
}
BAND_KEYS = ('min', 'mean', 'max', 'sd')
# The two blocks an artist works from directly pair a machine handle with open English
# describing it. They are one value, not two: a `features` entry is a form token and the
# sentence that explains it, and a `coloration` entry is a palette and the sentence that
# says how it is distributed. Keeping the pair in one place is the point - a parallel prose
# block beside a token block is two registries of the same fact, and they drift.
FEATURE_KEYS = ('form', 'note')
PALETTE_KEYS = ('note', 'swatches')
# Long enough that a token cannot pass as a description. `note` exists because
# `broad_high_bridge` tells a concept artist nothing about a dwarf's nose.
PROSE_MIN = 20
SEXES = ('male', 'female')
LIFE_STAGES = ('child', 'adolescent', 'adult', 'elder')
STAGE_KEYS = ('onset_years', 'height_fraction', 'read')
# Two closed vocabularies, because a wrong value in either produces the wrong art silently
# rather than a missing field. Every other descriptive key stays open: appearance vocabulary
# is art direction and grows with the world, so it is held to a bare snake_case token -
# usable as a prompt fragment, enumerable later - and to nothing further. Closing them all
# would mean a code edit for every new nose.
FACIAL_HAIR = ('none', 'sparse', 'male_only', 'male_full', 'male_full_female_sparse',
               'full_universal')
SEXUAL_DIMORPHISM = ('minimal', 'low', 'moderate', 'pronounced')
PALETTE_MIN = 3
# Population frequencies are authored to two decimals; the tolerance is for float addition,
# not for a palette that nearly sums to one.
WEIGHT_TOLERANCE = 1e-6
TOKEN = re.compile(r'^[a-z][a-z0-9_]*$')
HEX_COLOUR = re.compile(r'^#[0-9a-f]{6}$')

CULTURE_BLOCKS = {
    'household': ('unit', 'inheritance', 'naming_pattern', 'marriage_move'),
    'governance': ('seat', 'succession', 'law_form', 'assembly'),
    'livelihood': ('primary', 'secondary', 'exchange', 'calendar'),
    'memory': ('record', 'teaching', 'oath_form', 'taboo'),
    'contact': ('stranger_rite', 'trade_stance', 'war_stance'),
    'faith': ('school', 'practice', 'site', 'festival'),
}
GENOME_DERIVED_BLOCKS = ('phonotactics', 'prosody', 'morphology', 'orthography', 'rates')
RATE_KEYS = ('third_syllable', 'cluster', 'loanword')


def _pairs(items):
    result = {}
    for key, value in items:
        if key in result:
            raise ValueError(f'duplicate policy key {key!r}')
        result[key] = value
    return result


def _reject(token):
    raise ValueError(f'non-finite policy number {token}')


def load(name):
    if name not in POLICY_FILES:
        raise ValueError(f'unknown policy {name!r}')
    text = files('heritage.policies').joinpath(name + '.json').read_text(encoding='utf-8')
    document = json.loads(text, object_pairs_hook=_pairs, parse_constant=_reject)
    if type(document.get('revision')) is not int or document['revision'] < 1:
        raise ValueError(f'policy {name} needs a positive integer revision')
    return document


def load_all():
    policies = {name: load(name) for name in POLICY_FILES}
    lint_traits(policies['traits'])
    lint_derivation(policies['derivation'])
    lint_lexicon(policies['lexicon'], policies['traits'])
    lint_overrides(policies['overrides'], policies['traits'])
    lint_appearance(policies['appearance'], policies['traits'])
    return policies


def revisions(policies):
    return {name: policies[name]['revision'] for name in POLICY_FILES}


def _check_axis(axis, value, label):
    if axis not in AXES:
        raise ValueError(f'{label} names an unknown axis {axis!r}')
    if axis in LIST_AXES:
        if (not isinstance(value, list) or len(value) != CRAFT_COUNT
                or len(set(value)) != CRAFT_COUNT):
            raise ValueError(f'{label} needs exactly {CRAFT_COUNT} distinct crafts')
        for item in value:
            if item not in AXES[axis]:
                raise ValueError(f'{label} axis {axis!r} is not one of {sorted(AXES[axis])}')
        return
    if isinstance(value, bool) or type(value) in (int, float):
        raise ValueError(f'heritage traits carry no numbers; {label} axis {axis!r} '
                         'must be an enum value')
    if value not in AXES[axis]:
        if axis == 'magic_school' and value in HIDDEN_SCHOOLS:
            raise ValueError(f'{label} claims the hidden school {value!r}; '
                             'generation can never raise one')
        raise ValueError(f'{label} axis {axis!r} is not one of {sorted(AXES[axis])}')


def lint_traits(document):
    """Every people is complete, so a half-authored race fails here rather than in the lab."""
    for race, base in document['races'].items():
        if set(base) != set(AXES):
            missing = sorted(set(AXES) - set(base)) or sorted(set(base) - set(AXES))
            raise ValueError(f'race {race!r} must name exactly the {len(AXES)} heritage '
                             f'axes; check {missing}')
        for axis, value in base.items():
            _check_axis(axis, value, f'race {race!r}')
    for cid, delta in document['peoples'].items():
        for axis, value in delta.items():
            _check_axis(axis, value, f'people {cid!r}')
    return document


def lint_derivation(document):
    """Every enum value maps, so adding an axis value cannot silently produce an empty culture."""
    culture = document['culture']
    if set(culture) != set(CULTURE_BLOCKS):
        raise ValueError(f'derivation must produce exactly the culture blocks '
                         f'{sorted(CULTURE_BLOCKS)}')
    for block, keys in CULTURE_BLOCKS.items():
        if set(culture[block]) != set(keys):
            raise ValueError(f'derivation culture block {block!r} must produce exactly '
                             f'{sorted(keys)}')
    for section, blocks in (('culture', culture), ('genome', document['genome'])):
        for block, rules in blocks.items():
            for key, rule in rules.items():
                _lint_rule(section, block, key, rule)
    for key in RATE_KEYS:
        rule = document['genome']['rates'][key]
        for value in rule['map'].values():
            if isinstance(value, bool) or type(value) not in (int, float) or not 0 <= value <= 1:
                raise ValueError(f'derivation rate {key!r} must be a number in 0..1')
    return document


def _lint_rule(section, block, key, rule):
    path = f'{section}.{block}.{key}'
    if not isinstance(rule, dict) or len(rule) not in (1, 2):
        raise ValueError(f'derivation rule at {path} must be copy, from/map or craft')
    if 'copy' in rule:
        if rule['copy'] not in AXES:
            raise ValueError(f'derivation rule at {path} copies unknown axis {rule["copy"]!r}')
        return
    if 'craft' in rule:
        if rule['craft'] not in range(CRAFT_COUNT):
            raise ValueError(f'derivation rule at {path} indexes craft_focus out of range')
        return
    axis = rule.get('from')
    if axis not in AXES or axis in LIST_AXES:
        raise ValueError(f'derivation rule at {path} reads unknown axis {axis!r}')
    table = rule.get('map')
    if not isinstance(table, dict):
        raise ValueError(f'derivation rule at {path} needs a map')
    for value in AXES[axis]:
        if value not in table:
            raise ValueError(f'derivation has no rule for {axis!r}/{value!r}; '
                             'every enum value must map')
    extra = sorted(set(table) - set(AXES[axis]))
    if extra:
        raise ValueError(f'derivation rule at {path} maps values outside {axis!r}: {extra}')
    for mapped in table.values():
        if isinstance(mapped, (dict, list)):
            raise ValueError(f'derivation nests {path} more than two levels deep')
        if section == 'culture' and (isinstance(mapped, bool) or type(mapped) in (int, float)):
            raise ValueError(f'heritage culture carries no numbers; {path} must be an enum value')


def lint_lexicon(document, traits):
    """A root spelled with a phoneme its family cannot make is an authoring error, not a quirk."""
    from . import phonemes
    shared = set(document['shared_slots'])
    seen_branches = set()
    for family, entry in document['families'].items():
        race = entry['parent_race']
        if race not in traits['races']:
            raise ValueError(f'lexicon family {family!r} names unknown race {race!r}')
        missing = sorted(shared - set(entry['roots']))
        if missing:
            raise ValueError(f'lexicon family {family!r} is missing shared slots {missing}')
        allowed = set(''.join(phonemes.inventory(traits['races'][race])[0])) | set(
            ''.join(phonemes.inventory(traits['races'][race])[1]))
        for slot, root in entry['roots'].items():
            if not root or not root.isascii() or root != root.strip():
                raise ValueError(f'lexicon family {family!r} root {slot!r} is not a bare token')
            stray = sorted(set(root) - allowed)
            if stray:
                raise ValueError(f'lexicon family {family!r} root {slot!r}={root!r} uses '
                                 f'letters its soma cannot make: {stray}')
        for branch, spec in entry['branches'].items():
            if branch in seen_branches:
                raise ValueError(f'lexicon branch {branch!r} is declared twice')
            seen_branches.add(branch)
            for change in spec['sound_changes']:
                if not isinstance(change, list) or len(change) != 2 or not change[0]:
                    raise ValueError(f'lexicon branch {branch!r} has a malformed sound change')
    for role, slots in document['slot_roles'].items():
        if not slots:
            raise ValueError(f'lexicon slot role {role!r} is empty')
    return document


def lint_overrides(document, traits):
    for cid in document.get('culture', {}):
        if cid not in traits['peoples']:
            raise ValueError(f'override names {cid!r}, which is not a people in traits')
    for cid, patch in document.get('culture', {}).items():
        for block, keys in patch.items():
            if block not in CULTURE_BLOCKS:
                raise ValueError(f'override for {cid!r} touches unknown culture block {block!r}')
            for key, value in keys.items():
                if key not in CULTURE_BLOCKS[block]:
                    raise ValueError(f'override for {cid!r} touches unknown culture key '
                                     f'{block}.{key}')
                if isinstance(value, (dict, list)):
                    raise ValueError(f'override for {cid!r} nests {block}.{key} '
                                     'more than two levels deep')
                if isinstance(value, bool) or type(value) in (int, float):
                    raise ValueError(f'heritage culture carries no numbers; {cid} '
                                     f'{block}.{key} must be an enum value')
    for cid in document.get('genome', {}):
        if cid not in traits['peoples']:
            raise ValueError(f'override names {cid!r}, which is not a people in traits')
    return document


def _finite(value, label):
    if isinstance(value, bool) or type(value) not in (int, float):
        raise ValueError(f'{label} must be a number')
    if value != value or value in (float('inf'), float('-inf')):
        raise ValueError(f'{label} must be a finite number')
    return float(value)


def _bounded(value, label, low, high):
    number = _finite(value, label)
    if not low <= number <= high:
        raise ValueError(f'{label} is {number:g}, outside {low:g}..{high:g}')
    return number


def _token(value, label):
    if not isinstance(value, str) or not TOKEN.match(value):
        raise ValueError(f'{label} must be a bare lowercase token, not {value!r}')


def _token_list(value, label):
    if not isinstance(value, list) or not value:
        raise ValueError(f'{label} must be a non-empty list of tokens')
    if len(set(value)) != len(value):
        raise ValueError(f'{label} names the same entry twice')
    for item in value:
        _token(item, label)


def _band(value, label):
    """min/mean/max/sd, so a caller can draw one NPC from the population it describes."""
    if not isinstance(value, dict) or set(value) != set(BAND_KEYS):
        raise ValueError(f'{label} must name exactly {list(BAND_KEYS)}')
    low = _finite(value['min'], f'{label}.min')
    mean = _finite(value['mean'], f'{label}.mean')
    high = _finite(value['max'], f'{label}.max')
    if not 0 < low <= mean <= high:
        raise ValueError(f'{label} needs 0 < min <= mean <= max; '
                         f'got {low:g}/{mean:g}/{high:g}')
    if _finite(value['sd'], f'{label}.sd') <= 0:
        raise ValueError(f'{label}.sd must be positive; a per-NPC draw needs a spread')


def _prose(value, label):
    if not isinstance(value, str) or len(value.strip()) < PROSE_MIN:
        raise ValueError(f'{label} must be open English a concept artist can act on, '
                         f'not {value!r}')


def _palette(value, label):
    """Weights are population frequencies. The engine's per-NPC weighting sits on top."""
    if not isinstance(value, list) or len(value) < PALETTE_MIN:
        raise ValueError(f'{label} needs at least {PALETTE_MIN} swatches')
    names, total = [], 0.0
    for index, swatch in enumerate(value):
        where = f'{label}[{index}]'
        if not isinstance(swatch, dict) or set(swatch) != {'name', 'hex', 'weight'}:
            raise ValueError(f'{where} must name exactly name, hex and weight')
        _token(swatch['name'], f'{where}.name')
        if not isinstance(swatch['hex'], str) or not HEX_COLOUR.match(swatch['hex']):
            raise ValueError(f'{where}.hex must be lowercase #rrggbb, '
                             f'not {swatch["hex"]!r}')
        if _finite(swatch['weight'], f'{where}.weight') <= 0:
            raise ValueError(f'{where}.weight must be positive; drop the swatch instead')
        names.append(swatch['name'])
        total += swatch['weight']
    if len(set(names)) != len(names):
        raise ValueError(f'{label} names the same swatch twice')
    if abs(total - 1.0) > WEIGHT_TOLERANCE:
        raise ValueError(f'{label} weights are population frequencies and must sum to 1; '
                         f'they sum to {total:g}')


def _check_appearance_key(block, key, value, label):
    where = f'{label} {block}.{key}'
    if block == 'frame':
        if key in ('height_m', 'mass_kg'):
            if not isinstance(value, dict) or set(value) != set(SEXES):
                raise ValueError(f'{where} must name exactly {list(SEXES)}')
            for sex in SEXES:
                _band(value[sex], f'{where}.{sex}')
        elif key == 'sexual_dimorphism':
            if value not in SEXUAL_DIMORPHISM:
                raise ValueError(f'{where} is not one of {sorted(SEXUAL_DIMORPHISM)}')
        else:
            _token(value, where)
    elif block == 'proportion':
        # Head-units and body ratios: what a rig and a sprite sheet are actually built on.
        if key == 'heads_tall':
            _bounded(value, where, 3.0, 9.0)
        else:
            _bounded(value, where, 0.05, 0.95)
    elif block == 'coloration':
        if not isinstance(value, dict) or set(value) != set(PALETTE_KEYS):
            raise ValueError(f'{where} must name exactly {list(PALETTE_KEYS)}')
        _prose(value['note'], f'{where}.note')
        _palette(value['swatches'], f'{where}.swatches')
    elif block == 'grooming':
        if key == 'common_styles':
            _token_list(value, where)
        elif key == 'facial_hair':
            if value not in FACIAL_HAIR:
                raise ValueError(f'{where} is not one of {sorted(FACIAL_HAIR)}')
        else:
            _token(value, where)
    elif block == 'life_stages':
        if key == 'max_years':
            _bounded(value, where, 1, 5000)
        else:
            if not isinstance(value, dict) or set(value) != set(STAGE_KEYS):
                raise ValueError(f'{where} must name exactly {list(STAGE_KEYS)}')
            _bounded(value['onset_years'], f'{where}.onset_years', 0, 5000)
            _bounded(value['height_fraction'], f'{where}.height_fraction', 0.2, 1.0)
            if not isinstance(value['read'], str) or not value['read'].strip():
                raise ValueError(f'{where}.read must say what visibly changes here')
    elif block == 'attire':
        if key == 'materials':
            _token_list(value, where)
        else:
            _token(value, where)
    elif block == 'features':
        if not isinstance(value, dict) or set(value) != set(FEATURE_KEYS):
            raise ValueError(f'{where} must name exactly {list(FEATURE_KEYS)}')
        _token(value['form'], f'{where}.form')
        _prose(value['note'], f'{where}.note')
    elif key == 'avoid':
        _token_list(value, where)
    else:
        # `art_direction.silhouette` and `.reads_as`, the layer's two standalone prose keys.
        _prose(value, where)


def check_resolved_appearance(appearance, traits, label):
    """Cross-layer agreement, judged on a complete body rather than on a sparse delta.

    Called once per race base at load, and once per people after `derive.merge_appearance`,
    because a delta cannot be judged until it has been merged onto what it inherits. One
    implementation and two call sites: the alternative is a second merge in this module,
    which is exactly the drift a sparse layer invites.
    """
    scale = traits['body_scale']
    floor, ceiling = BODY_SCALE_HEIGHT_M[scale]
    for sex in SEXES:
        band = appearance['frame']['height_m'][sex]
        if band['min'] < floor or band['max'] > ceiling:
            raise ValueError(
                f'{label} is body_scale {scale!r}, whose height envelope is '
                f'{floor:g}..{ceiling:g} m; its {sex} band is '
                f'{band["min"]:g}..{band["max"]:g} m')
    stages = appearance['life_stages']
    onsets = [stages[stage]['onset_years'] for stage in LIFE_STAGES]
    if onsets[0] != 0:
        raise ValueError(f'{label} life_stages.child must begin at year 0')
    for index in range(len(LIFE_STAGES) - 1):
        if onsets[index] >= onsets[index + 1]:
            raise ValueError(
                f'{label} life_stages.{LIFE_STAGES[index]} begins at {onsets[index]:g} '
                f'and {LIFE_STAGES[index + 1]} at {onsets[index + 1]:g}; '
                'stages run in order')
    growth = [stages[stage]['height_fraction'] for stage in LIFE_STAGES[:3]]
    if not growth[0] < growth[1] < growth[2]:
        raise ValueError(f'{label} does not grow from child to adult: {growth}')
    if stages['adult']['height_fraction'] != 1:
        raise ValueError(f'{label} life_stages.adult.height_fraction is the reference '
                         'stature every band is stated at, and must be exactly 1')
    maximum = stages['max_years']
    if maximum <= onsets[-1]:
        raise ValueError(f'{label} life_stages.max_years {maximum:g} is not past its '
                         f'elder onset {onsets[-1]:g}')
    low, high = LIFESPAN_TEMPO_YEARS[traits['lifespan_tempo']]
    if not low <= maximum <= high:
        raise ValueError(f'{label} has lifespan_tempo {traits["lifespan_tempo"]!r}, whose '
                         f'span is {low:g}..{high:g} years; max_years is {maximum:g}')


def lint_appearance(document, traits):
    """A complete body per race, a sparse extension per subrace.

    This is the one heritage layer that carries numbers, and it may because a body has
    measurements and nothing else in the repository states them. `civilizations.json`
    measures habitat and never anatomy, so a number here cannot become a second copy of one
    the placement code reads - which is the whole reason the trait and culture layers are
    barred from carrying any.

    Structure is checked here. Agreement with the key traits is checked on the resolved
    body by `check_resolved_appearance`: a race base is complete and can be judged now, a
    subrace delta cannot.
    """
    for field in ('races', 'peoples'):
        mine, theirs = set(document[field]), set(traits[field])
        if mine != theirs:
            raise ValueError(f'appearance must name exactly the {field} traits names; '
                             f'check {sorted(mine ^ theirs)}')
    for race, base in document['races'].items():
        label = f'race {race!r}'
        if set(base) != set(APPEARANCE_BLOCKS):
            raise ValueError(f'{label} must name exactly the appearance blocks '
                             f'{sorted(APPEARANCE_BLOCKS)}')
        for block, keys in APPEARANCE_BLOCKS.items():
            if set(base[block]) != set(keys):
                raise ValueError(f'{label} block {block!r} must name exactly '
                                 f'{sorted(keys)}')
            for key, value in base[block].items():
                _check_appearance_key(block, key, value, label)
        check_resolved_appearance(base, traits['races'][race], label)
    for cid, delta in document['peoples'].items():
        label = f'people {cid!r}'
        for block, keys in delta.items():
            if block not in APPEARANCE_BLOCKS:
                raise ValueError(f'{label} extends unknown appearance block {block!r}')
            if not isinstance(keys, dict):
                raise ValueError(f'{label} block {block!r} must map keys to extensions')
            for key, value in keys.items():
                if key not in APPEARANCE_BLOCKS[block]:
                    raise ValueError(f'{label} extends unknown key {block}.{key}')
                _check_appearance_key(block, key, value, label)
    return document
