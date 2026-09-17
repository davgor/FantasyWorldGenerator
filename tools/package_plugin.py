"""Create a deterministic FantasyWorldGenerator plugin archive; it is not an engine-qualified release."""
import argparse
import hashlib
import io
import json
from pathlib import Path
import zipfile

ROOT=Path(__file__).resolve().parents[1]
PLUGIN_DIRECTORY='Unreal/FantasyWorldGenerator'
ARCHIVE_PREFIX='FantasyWorldGenerator/'
# Source-only plugin: refuse anything that could smuggle a binary, asset or generated build product.
ALLOWED_SUFFIXES=('.uplugin','.h','.hpp','.inl','.cpp','.cs','.md','.ini')


def manifest_metadata():
    return dict(schema='fantasy-world-generator.unreal-plugin-package',schema_version=1,
                plugin='FantasyWorldGenerator',plugin_version='0.1.0',module='FantasyWorldGenerator',module_type='Runtime',
                engine=dict(version='5.8',requested_patch='5.8.2',platforms=['Win64']),
                genesis='native-core',native_generate='incomplete',core_vendored=False,recipe_version=3,
                coordinates=dict(version=1,unreal_x='east_m * 100',unreal_y='north_m * 100',
                                 unreal_z='up_m * 100',scale_unit_axes=False),
                qualification='unqualified-source-only',unreal_qualified=False,unreal_cooked_runtime=False,
                python_runtime_required=False,license='LICENSE',
                limitations=['No native world generate, on-demand sampling or asset-registry materialize',
                             'No Unreal Build Tool, editor load or cooked-runtime verification',
                             'Frame and generate-request rules mirror Core until Core/genesis is compiled in',
                             'No Python runtime, sidecar or embedded interpreter',
                             'No public redistribution grant'])


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
        # The plugin must stay consumer-agnostic; a project content path belongs in UnrealWorldGen.
        if b'/Game/' in data:raise ValueError('plugin source must not reference a project content path: '+relative)
        payload[ARCHIVE_PREFIX+relative]=data
    if ARCHIVE_PREFIX+'FantasyWorldGenerator.uplugin' not in payload:
        raise ValueError('missing FantasyWorldGenerator.uplugin')
    if ARCHIVE_PREFIX+'Source/FantasyWorldGenerator/FantasyWorldGenerator.Build.cs' not in payload:
        raise ValueError('missing FantasyWorldGenerator.Build.cs')
    return payload


def bundle_bytes(root=ROOT):
    payload=plugin_files(root)
    # The private notice travels inside the plugin folder that a consumer copies.
    payload[ARCHIVE_PREFIX+'LICENSE']=(root/'LICENSE').read_bytes()
    manifest=dict(manifest_metadata(),files={name:hashlib.sha256(data).hexdigest() for name,data in sorted(payload.items())})
    payload['manifest.json']=(json.dumps(manifest,sort_keys=True,indent=2)+'\n').encode()
    output=io.BytesIO()
    with zipfile.ZipFile(output,'w',compression=zipfile.ZIP_STORED) as archive:
        for name,data in sorted(payload.items()):
            info=zipfile.ZipInfo(name,date_time=(1980,1,1,0,0,0))
            info.create_system=3;info.external_attr=0o100644<<16
            archive.writestr(info,data)
    return output.getvalue()


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output-dir',type=Path,default=ROOT/'Artifacts/unreal')
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
    return 0

if __name__=='__main__':raise SystemExit(main())
