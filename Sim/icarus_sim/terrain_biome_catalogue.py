"""Natural surfaces and explicit natural-core / magic-school states."""
from .terrain_leyline_history import SCHOOLS

NATURAL_BIOMES = {0:'ocean', 1:'tundra', 2:'desert', 3:'grassland', 4:'forest', 5:'exposed_rock',
                  6:'snow', 7:'rainforest', 8:'lake', 13:'marsh', 15:'boreal_forest',
                  16:'cold_tundra', 17:'land_ice'}
VARIANT_NAMES = {
    'weave': ['Prismatic seas','Dream tundra','Glass mirages','Possibility meadows','Living storywoods','Floating stonefields','Chromatic snow','Everchanging canopy','Starlight lakes','Spellmist marsh','Aurora woods','Shifting frostlands','Singing glaciers'],
    'umbral': ['Silent seas','Grave tundra','Haunted tombs','Ashen meadows','Mourning woods','Ossuary crags','Funeral snow','Withering canopy','Stillwater tombs','Haunted marsh','Ghost pines','Deathfrost plains','Sepulchral ice'],
    'infernal': ['Brimstone seas','Blighted tundra','Hellglass wastes','Cinder blight','Thornhell woods','Demon spires','Sootsnow fields','Devouring jungle','Bloodglass lakes','Corruption mire','Charred blackwoods','Torment barrens','Infernal glaciers'],
    'radiant': ['Dawn seas','Blessed tundra','Golden sanctuaries','Healing meadows','Sanctuary woods','Hallowed heights','Luminous snow','Mercy gardens','Lustral lakes','Purifying marsh','Dawnlit pines','Peaceful frostlands','Cathedral ice'],
    'fire': ['Steam seas','Ember tundra','Furnace dunes','Flamegrass plains','Phoenix woods','Molten crags','Smoldering snow','Emberbloom jungle','Boiling lakes','Cinder mire','Firecone woods','Ashfrost plains','Steamcut glaciers'],
    'water': ['Crystal currents','Rime tundra','Frostglass dunes','Dew meadows','Rainveil woods','Springstone cliffs','Sapphire snow','Deluge jungle','Winterglass lakes','Tidal gardens','Mistbound pines','Bluefrost tundra','Everflow glaciers'],
    'earth': ['Rootreef seas','Mossbound tundra','Blooming dunes','Titan meadows','Ancient rootwoods','Living monoliths','Mosswarm snow','Colossal jungle','Rootcradle lakes','Deep-root marsh','Ironbark taiga','Lichenstone plains','Rootsplit glaciers'],
    'air': ['Storm seas','Gale tundra','Whistling dunes','Thundergrass plains','Skyreach woods','Windcarved spires','Dancing snow','Stormcrown jungle','Suspended mist lakes','Cloudveil marsh','Singing pines','Force-swept tundra','Howling glaciers'],
}


def biome_catalogue():
    return [dict(id=f'{core}.{school}', core=core, core_biome_id=bid, magic_school=school,
                 group=SCHOOLS[school][0], descriptors=SCHOOLS[school][1],
                 name=VARIANT_NAMES[school][i], color=SCHOOLS[school][2],
                 asset_id=f'terrain.mutation.{core}.{school}')
            for i,(bid,core) in enumerate(NATURAL_BIOMES.items()) for school in SCHOOLS]


NATURAL_COLORS = {
    0: [42,102,147], 1: [156,164,126], 2: [218,184,120], 3: [139,176,99],
    4: [65,135,80], 5: [145,143,139], 6: [230,240,241], 7: [22,83,58],
    8: [68,160,185], 13: [105,135,101], 15: [56,104,95],
    16: [152,164,136], 17: [223,240,245],
}


def natural_catalogue():
    return [dict(id=bid, core=core,
                 name='Persistent land ice' if bid == 17 else core.replace('_', ' ').capitalize(),
                 color=list(NATURAL_COLORS[bid]), asset_id=f'terrain.biome.{bid:03d}')
            for bid, core in NATURAL_BIOMES.items()]


def cell_variant(result, x, z):
    index = result['layers'].get('biome_variant')
    value = index[z][x] if index is not None else -1
    return result['terrain']['magical_biomes'][value]['id'] if value >= 0 else None
