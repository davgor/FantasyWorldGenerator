"""Build and test an extracted native source proof without a Python simulation."""
import argparse
import hashlib
import json
import os
from pathlib import Path
import platform
import shlex
import shutil
import subprocess
import sys

from package_native import SOURCE_FILES, manifest_metadata

ROOT=Path(__file__).resolve().parents[1]


def verify_sources(root):
    path=root/'manifest.json'
    if path.is_symlink():raise ValueError('manifest symlinks are not supported')
    with path.open('rb') as stream:raw=stream.read(65537)
    if len(raw)>65536:raise ValueError('source manifest exceeds byte limit')
    def pairs(items):
        result={}
        for key,value in items:
            if key in result:raise ValueError('duplicate source manifest key')
            result[key]=value
        return result
    manifest=json.loads(raw,object_pairs_hook=pairs)
    if type(manifest) is not dict:raise ValueError('source manifest must be an object')
    metadata={key:value for key,value in manifest.items() if key!='files'}
    if json.dumps(metadata,sort_keys=True)!=json.dumps(manifest_metadata(),sort_keys=True):
        raise ValueError('unsupported source manifest metadata')
    if type(manifest.get('files')) is not dict or set(manifest['files'])!=set(SOURCE_FILES):
        raise ValueError('unexpected source manifest file set')
    for relative,expected in manifest['files'].items():
        path=root/relative
        if any(parent.is_symlink() for parent in (path,*path.parents)):
            raise ValueError('source symlinks are not supported: '+relative)
        if hashlib.sha256(path.read_bytes()).hexdigest()!=expected:
            raise ValueError('source hash mismatch: '+relative)
    return hashlib.sha256(raw).hexdigest()


def qualify(root,output):
    manifest_hash=verify_sources(root)
    compiler=shutil.which('clang++') or shutil.which('g++')
    if not compiler:raise ValueError('C++17 compiler required; native qualification cannot be skipped')
    flags=shlex.split(os.environ.get('FANTASY_WORLD_GENERATOR_CXXFLAGS',''))
    if sys.platform=='darwin':
        sdk=subprocess.check_output(['xcrun','--show-sdk-path'],text=True,timeout=60).strip()
        headers=Path(sdk)/'usr/include/c++/v1'
        if headers.is_dir():flags+=['-isystem',str(headers)]
    def build(name,sources):
        path=output/name
        compiled=subprocess.run([compiler,'-std=c++17','-Wall','-Wextra','-Werror','-pedantic',*flags,
                                 '-I',str(root/'Core'),*(str(root/'Core'/source) for source in sources),'-o',str(path)],
                                capture_output=True,text=True,timeout=60)
        if compiled.returncode:raise ValueError('native compilation failed ('+name+'): '+compiled.stderr)
        return path
    binary=build('native-counter',['counter.cpp','json.cpp','numeric.cpp','wire.cpp','tests/wire_driver.cpp'])
    genesis=build('native-genesis',['counter.cpp','json.cpp','numeric.cpp','wire.cpp','genesis.cpp','tests/genesis_driver.cpp'])
    checks=[]
    def run(op,value,expected_error=None,program=None):
        raw=json.dumps(value,ensure_ascii=True,separators=(',',':'),allow_nan=False).encode()
        result=subprocess.run([str(program or binary),op],input=raw,capture_output=True,timeout=10)
        if expected_error:
            if result.returncode!=2 or json.loads(result.stdout).get('code')!=expected_error:
                raise ValueError('native failure-code mismatch: '+op)
        elif result.returncode:
            raise ValueError('native execution failed: '+result.stdout.decode(errors='replace'))
        checks.append(op+(':'+expected_error if expected_error else ''))
        return result.stdout
    def equal(actual,expected):
        if actual!=expected:raise ValueError('native fixture output mismatch')
    def rejected(op,value,program):
        # The fixture declares no stable codes for these bodies, so only refusal is qualified.
        raw=json.dumps(value,ensure_ascii=True,separators=(',',':'),allow_nan=False).encode()
        result=subprocess.run([str(program),op],input=raw,capture_output=True,timeout=10)
        if result.returncode!=2 or json.loads(result.stdout).get('schema')!='fantasy-world-generator.failure':
            raise ValueError('native request validation accepted an invalid body: '+op)
        checks.append(op+':rejected')
    numeric=json.loads((root/'Fixtures/kernel-numeric-v1.json').read_text())
    for case in numeric['canonical']:
        equal(run('canonical',case['value']),case['ascii'].encode())
        equal(run('digest',case['value']).decode(),case['sha256'])
    for case in numeric['streams']:
        equal(run('stream',{key:case[key] for key in ('seed','stream','index')}).decode(),case['word'])
    f=json.loads((root/'Fixtures/counter-kernel-v1.json').read_text())
    first=json.loads(run('evaluate',dict(state=f['initial'],command=f['first_command'])))
    checkpoint=json.loads(run('commit',dict(state=f['initial'],candidate=first)))
    equal(checkpoint,f['checkpoint'])
    equal(json.loads(run('commit',dict(state=checkpoint,candidate=first))),checkpoint)
    resumed=json.loads(run('evaluate',dict(state=checkpoint,command=f['resume_command'])))
    equal(json.loads(run('commit',dict(state=checkpoint,candidate=resumed))),f['complete'])
    frame=json.loads((root/'Fixtures/unreal-frame-v1.json').read_text())
    for case in frame['valid']:
        equal(json.loads(run('unreal_cm',{key:case[key] for key in ('east_m','up_m','north_m')},program=genesis)),case['expected_cm'])
    equal(json.loads(run('validate_generate',dict(recipe_version=3,seed=42,overrides=dict(size=65)),program=genesis)),
          dict(ok=True,recipe_version=3,seed=42))
    for body in frame['invalid_generate']:
        rejected('validate_generate',body,genesis)
    cases=json.loads((root/'Fixtures/kernel-contract-v1.json').read_text())
    for case in cases['invalid']:
        if case['kind']=='event':run('event',case['value'],case['code'])
        else:run('evaluate',dict(state=f['initial'],command=case['value']),case['code'])
    # Detect source edits during compilation/execution before recording success.
    if verify_sources(root)!=manifest_hash:raise ValueError('source manifest changed during qualification')
    return dict(schema='fantasy-world-generator.native-qualification',schema_version=1,status='passed',
                manifest_sha256=manifest_hash,unreal_qualified=False,
                compiler=subprocess.check_output([compiler,'--version'],text=True,timeout=60).strip(),
                platform=platform.system(),architecture=platform.machine(),compiler_flags=['-std=c++17','-Wall','-Wextra','-Werror','-pedantic',*flags],
                checks=checks,binary_sha256=hashlib.sha256(binary.read_bytes()).hexdigest(),
                genesis_binary_sha256=hashlib.sha256(genesis.read_bytes()).hexdigest())


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output-dir',type=Path,default=ROOT/'build/qualification')
    args=parser.parse_args();output=args.output_dir.resolve();output.mkdir(parents=True,exist_ok=True)
    try:
        report=qualify(ROOT,output);status=0
    except (ValueError,OSError,RecursionError,subprocess.SubprocessError) as error:
        report=dict(schema='fantasy-world-generator.native-qualification',schema_version=1,status='failed',unreal_qualified=False,error=str(error))
        print(str(error),file=sys.stderr);status=1
    temporary=output/'qualification.json.tmp'
    temporary.write_text(json.dumps(report,sort_keys=True,indent=2)+'\n')
    temporary.replace(output/'qualification.json')
    if not status:print('Isolated native qualification passed ('+str(len(report['checks']))+' fixture checks); Unreal remains unqualified.')
    return status

if __name__=='__main__':raise SystemExit(main())
