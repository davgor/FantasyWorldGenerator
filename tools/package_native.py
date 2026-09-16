"""Create a deterministic, private native source proof bundle; never publish it."""
import argparse
import hashlib
import io
import json
from pathlib import Path
import zipfile

ROOT=Path(__file__).resolve().parents[1]
SOURCE_FILES=(
    'LICENSE','Core/README.md','Core/counter.hpp','Core/counter.cpp','Core/json.hpp','Core/json.cpp',
    'Core/numeric.hpp','Core/numeric.cpp','Core/wire.hpp','Core/wire.cpp','Core/tests/wire_driver.cpp',
    'Contracts/kernel-v1.md','Contracts/schemas/counter-kernel.schema.json',
    'Fixtures/kernel-numeric-v1.json','Fixtures/kernel-contract-v1.json','Fixtures/counter-kernel-v1.json',
    'tools/package_native.py','tools/qualify_native.py',
)


def manifest_metadata():
    return dict(schema='mathlab.native-source-package',schema_version=1,
                  qualification='unqualified-source-only',license='LICENSE',
                  contracts=dict(counter_rule=1,counter_state=1,counter_command=1,counter_candidate=1,kernel_numeric=1),
                  requires=dict(cpp_standard=17,cpp_exceptions=True,binary64_double=True),
                  limitations=['No Unreal adapter or engine/cooked qualification','No durable storage or external effect delivery',
                               'No general native world generator','No public redistribution grant'])


def bundle_bytes(root=ROOT):
    payload={}
    for relative in SOURCE_FILES:
        path=root/relative
        if any(parent.is_symlink() for parent in (path,*path.parents)):
            raise ValueError('source symlinks are not supported: '+relative)
        payload[relative]=path.read_bytes()
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
    parser.add_argument('--output-dir',type=Path,default=ROOT/'Artifacts/native')
    args=parser.parse_args()
    raw=bundle_bytes();digest=hashlib.sha256(raw).hexdigest()
    args.output_dir.mkdir(parents=True,exist_ok=True)
    path=args.output_dir/('mathlab-native-source-'+digest+'.zip')
    # A content-addressed file must never silently replace different bytes.
    try:
        with path.open('xb') as stream:stream.write(raw)
    except FileExistsError:
        if path.read_bytes()!=raw:raise ValueError('content-addressed output collision')
    print(path)
    return 0

if __name__=='__main__':raise SystemExit(main())
