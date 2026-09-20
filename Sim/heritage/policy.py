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

POLICY_FILES = ('traits', 'derivation', 'lexicon', 'overrides')

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
