"""Create a deterministic, source-inclusive FantasyWorldGenerator plugin archive.

The archive is what a consumer project copies into Plugins/. It vendors the
engine-independent Core/ sources so UnrealBuildTool compiles world genesis into the
runtime module, and it carries the asset-ID registry table the importer resolves
identities through. Producing an archive is not an engine qualification: that still
needs a packaged Win64 generate-to-materialize digest.
"""
import argparse
import hashlib
import io
import json
from pathlib import Path
import shutil
import zipfile

ROOT=Path(__file__).resolve().parents[1]
PLUGIN_DIRECTORY='Unreal/FantasyWorldGenerator'
ARCHIVE_PREFIX='FantasyWorldGenerator/'
CORE_DIRECTORY='Core'
VENDORED_CORE=ARCHIVE_PREFIX+'Source/FantasyWorldGenerator/FantasyWorldGeneratorCore/'
REGISTRY_SOURCE='Contracts/catalogues/unreal-asset-registry-v1.json'
REGISTRY_TARGET=ARCHIVE_PREFIX+'Data/unreal-asset-registry-v1.json'
CATALOGUE_SOURCE='Contracts/catalogues/native-catalogues-v1.json'
CATALOGUE_TARGET=ARCHIVE_PREFIX+'Data/native-catalogues-v1.json'
# The settlement planners read these four at runtime, by path, exactly as the reference
# does. They MUST travel: the plugin has to be a folder a game copies and keeps, with
# nothing reaching back into this repository. Without them a packaged game silently
# produces no buildings, because the planners degrade rather than fail.
PLANNER_CATALOGUES=('civilizations.json','buildings.json','city_shapes.json','castles.json')
PLANNER_SOURCE_DIRECTORY='Sim/icarus_sim'
# Installed beside the plugin so a game can read, at runtime, exactly which generator
# build it is pinned to. The archive's own file name is a digest of everything, but a
# consumer never sees the archive -- it sees the folder.
IDENTITY_TARGET=ARCHIVE_PREFIX+'Data/plugin-manifest.json'
# Source-only plugin: refuse anything that could smuggle a binary, asset or build product.
ALLOWED_SUFFIXES=('.uplugin','.h','.hpp','.inl','.cpp','.cs','.md','.ini')


def manifest_metadata(registry,catalogues):
    return dict(schema='fantasy-world-generator.unreal-plugin-package',schema_version=2,
                plugin='FantasyWorldGenerator',plugin_version='0.3.0',module='FantasyWorldGenerator',module_type='Runtime',
                engine=dict(version='5.8',requested_patch='5.8.2',platforms=['Win64']),
                genesis='native-core',native_generate='available',core_vendored=True,recipe_version=3,
                coordinates=dict(version=1,unreal_x='east_m * 100',unreal_y='north_m * 100',
                                 unreal_z='up_m * 100',scale_unit_axes=False),
                asset_registry=dict(version=registry['version'],rows=len(registry['rows']),
                                    asset_list_sha256=registry['asset_list_sha256'],
                                    unbound=sum(1 for row in registry['rows'] if row['status']=='unbound')),
                catalogues=dict(version=catalogues['version'],profiles=len(catalogues['profiles']),
                                entities=len(catalogues['entities']),
                                registry_sha256=catalogues['registry']['sha256']),
                qualification='unqualified-source-only',unreal_qualified=False,unreal_cooked_runtime=False,
                python_runtime_required=False,license='LICENSE',
                # Hermetic: every catalogue the compiled rules read at runtime is staged
                # under Data/, so the installed folder is the whole generator and a game
                # keeps working when this repository is not on the machine.
                self_contained=True,
                limitations=['Generate, on-demand sampling, registry resolution, settlement, '
                             'road, habitat and building-geometry placement are all native',
                             'No Unreal Build Tool, editor load or cooked-runtime result is implied by this archive',
                             'Terrain presentation is a runtime procedural surface, not an editor Landscape actor',
                             'No Python runtime, sidecar or embedded interpreter',
                             'No public redistribution grant'])


# The counter kernel is not on the Unreal generate path, and its translation units
# define a helper named check(), which collides with the Unreal shared-PCH macro of the
# same name. Its header still travels: Error lives there.
CORE_SOURCES_NOT_VENDORED=('counter.cpp','wire.cpp')


def core_files(root=ROOT):
    """Core sources compiled into the module. Tests and drivers stay out of a shipped plugin."""
    directory=root/CORE_DIRECTORY
    payload={}
    for path in sorted(directory.rglob('*')):
        if path.is_dir() or 'tests' in path.relative_to(directory).parts:continue
        if path.name in CORE_SOURCES_NOT_VENDORED:continue
        if path.suffix not in ('.hpp','.cpp','.inl','.md'):
            raise ValueError('unexpected Core file for vendoring: '+path.name)
        if path.suffix=='.md':continue
        payload[VENDORED_CORE+path.relative_to(directory).as_posix()]=path.read_bytes()
    for required in ('world.cpp','genesis.cpp','registry.cpp','tectonics.cpp'):
        if VENDORED_CORE+required not in payload:
            raise ValueError('missing vendored Core source: '+required)
    return payload


def plugin_files(root=ROOT):
    directory=root/PLUGIN_DIRECTORY
    if not directory.is_dir():raise ValueError('missing plugin directory: '+PLUGIN_DIRECTORY)
    payload={}
    for path in sorted(directory.rglob('*')):
        relative=path.relative_to(directory).as_posix()
        if any(parent.is_symlink() for parent in (path,*path.parents)):
            raise ValueError('plugin symlinks are not supported: '+relative)
        if path.is_dir():continue
        if path.suffix not in ALLOWED_SUFFIXES:
            raise ValueError('unsupported plugin file; assets and build products are not packaged: '+relative)
        data=path.read_bytes()
        # Plugin code stays consumer-agnostic; a project content path belongs in the
        # registry table, which is data a consumer can re-point at its own assets.
        if b'/Game/' in data:raise ValueError('plugin source must not reference a project content path: '+relative)
        payload[ARCHIVE_PREFIX+relative]=data
    if ARCHIVE_PREFIX+'FantasyWorldGenerator.uplugin' not in payload:
        raise ValueError('missing FantasyWorldGenerator.uplugin')
    if ARCHIVE_PREFIX+'Source/FantasyWorldGenerator/FantasyWorldGenerator.Build.cs' not in payload:
        raise ValueError('missing FantasyWorldGenerator.Build.cs')
    payload.update(core_files(root))
    payload[REGISTRY_TARGET]=(root/REGISTRY_SOURCE).read_bytes()
    # Authoring traits and habitat rules travel as data; the rules that read them are
    # compiled Core sources, not a JSON world.
    payload[CATALOGUE_TARGET]=(root/CATALOGUE_SOURCE).read_bytes()
    for name in PLANNER_CATALOGUES:
        source=root/PLANNER_SOURCE_DIRECTORY/name
        if not source.is_file():
            raise ValueError('missing planner catalogue for staging: '+name)
        payload[ARCHIVE_PREFIX+'Data/'+name]=source.read_bytes()
    return payload


def bundle_bytes(root=ROOT):
    payload=plugin_files(root)
    registry=json.loads(payload[REGISTRY_TARGET])
    catalogues=json.loads(payload[CATALOGUE_TARGET])
    # The private notice travels inside the plugin folder that a consumer copies.
    payload[ARCHIVE_PREFIX+'LICENSE']=(root/'LICENSE').read_bytes()
    files={name:hashlib.sha256(data).hexdigest() for name,data in sorted(payload.items())}
    # One digest over every file's digest: the generator's identity, stable and
    # computable before the manifest that carries it exists. A game records this and
    # knows precisely which generator its worlds came from; two folders agreeing on it
    # produce identical worlds from identical seeds.
    identity=hashlib.sha256(
        ''.join(f'{name}:{digest}\n' for name,digest in sorted(files.items())).encode()).hexdigest()
    manifest=dict(manifest_metadata(registry,catalogues),generator_identity=identity,files=files)
    encoded=(json.dumps(manifest,sort_keys=True,indent=2)+'\n').encode()
    # Twice on purpose: at the archive root for inspection, and inside the plugin
    # folder because install() copies only that folder and a game must be able to read
    # its own generator version without the archive.
    payload['manifest.json']=encoded
    payload[IDENTITY_TARGET]=encoded
    output=io.BytesIO()
    with zipfile.ZipFile(output,'w',compression=zipfile.ZIP_STORED) as archive:
        for name,data in sorted(payload.items()):
            info=zipfile.ZipInfo(name,date_time=(1980,1,1,0,0,0))
            info.create_system=3;info.external_attr=0o100644<<16
            archive.writestr(info,data)
    return output.getvalue()


def install(project: Path, raw: bytes) -> Path:
    """Replace <project>/Plugins/FantasyWorldGenerator with this archive's contents."""
    if not (project/(project.name+'.uproject')).is_file() and not list(project.glob('*.uproject')):
        raise ValueError('not an Unreal project directory: '+str(project))
    destination=project/'Plugins'
    target=destination/'FantasyWorldGenerator'
    if target.exists():shutil.rmtree(target)
    destination.mkdir(parents=True,exist_ok=True)
    with zipfile.ZipFile(io.BytesIO(raw)) as archive:
        for name in archive.namelist():
            if not name.startswith(ARCHIVE_PREFIX):continue
            path=destination/name
            path.parent.mkdir(parents=True,exist_ok=True)
            path.write_bytes(archive.read(name))
    return target


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output-dir',type=Path,default=ROOT/'Artifacts/unreal')
    parser.add_argument('--install',type=Path,default=None,
                        help='also copy the plugin into this Unreal project (writes outside this repository)')
    args=parser.parse_args()
    raw=bundle_bytes();digest=hashlib.sha256(raw).hexdigest()
    args.output_dir.mkdir(parents=True,exist_ok=True)
    path=args.output_dir/('fantasy-world-generator-plugin-'+digest+'.zip')
    # A content-addressed file must never silently replace different bytes.
    try:
        with path.open('xb') as stream:stream.write(raw)
    except FileExistsError:
        if path.read_bytes()!=raw:raise ValueError('content-addressed output collision')
    print(path)
    if args.install is not None:
        print(install(args.install.resolve(),raw))
    return 0

if __name__=='__main__':raise SystemExit(main())
