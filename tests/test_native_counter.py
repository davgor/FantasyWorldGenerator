"""Compile shared JSON fixtures into a typed native harness; no engine required."""
import json
import os
from pathlib import Path
import shutil
import shlex
import subprocess
import tempfile
import sys
import unittest

ROOT=Path(__file__).resolve().parents[1]


def event(value):
    return 'Event{' + ','.join(json.dumps(value[key]) for key in
        ('schema','schema_version','world_id','event_id','actor_id','target_id','time_ms','delta')) + '}'


def events(values):
    return '{'+','.join(event(v) for v in values)+'}'


def snapshot(value):
    assignments=''.join('s.'+key+'='+json.dumps(value[key])+';' for key in
        ('schema','schema_version','rules_version','numeric_version','world_id','authority_epoch','revision','time_ms','counter'))
    assignments+='s.receipts={'+','.join('Receipt{'+event(r['event'])+','+str(r['counter_after'])+'}' for r in value['receipts'])+'};'
    if value['pending'] is not None:
        assignments+='s.pending=Pending{'+str(value['pending']['target_time_ms'])+','+events(value['pending']['events'])+'};'
    return '[&]{Snapshot s;'+assignments+'return s;}()'


def command(value):
    return 'Command{'+','.join(json.dumps(value[k]) for k in ('schema','schema_version','world_id','authority_epoch','expected_revision','target_time_ms','budget'))+','+events(value['events'])+'}'


class NativeCounterTests(unittest.TestCase):
    def test_shared_fixtures_and_native_failure_cases(self):
        compiler=shutil.which('clang++') or shutil.which('g++')
        if compiler is None:
            self.skipTest('headless native proof requires a C++17 compiler; Python reference remains standalone')
        flags=shlex.split(os.environ.get('FANTASY_WORLD_GENERATOR_CXXFLAGS',''))
        if sys.platform == 'darwin':
            sdk=subprocess.check_output(['xcrun','--show-sdk-path'],text=True).strip()
            headers=Path(sdk)/'usr/include/c++/v1'
            if headers.is_dir():
                flags += ['-isystem',str(headers)]
        fixture=json.loads((ROOT/'Fixtures/counter-kernel-v1.json').read_text())
        declarations='\n'.join('auto '+name+'='+snapshot(fixture[key])+';' for name,key in
                              [('initial','initial'),('checkpoint','checkpoint'),('complete','complete')])
        declarations+='\nauto first_command='+command(fixture['first_command'])+';'
        declarations+='\nauto resume_command='+command(fixture['resume_command'])+';'
        harness=(ROOT/'Core/tests/counter_cases.inc').read_text()
        source='#include "counter.hpp"\n#include <algorithm>\n#include <iostream>\n#include <stdexcept>\nusing namespace fantasy_world_generator;\n'+harness.replace('/* SHARED_FIXTURES */',declarations)
        with tempfile.TemporaryDirectory(prefix='fantasy-world-generator-native-') as directory:
            cpp=Path(directory)/'test.cpp'; binary=Path(directory)/'counter_test'
            cpp.write_text(source)
            built=subprocess.run([compiler,'-std=c++17','-Wall','-Wextra','-Werror','-pedantic',*flags,
                                  '-I',str(ROOT/'Core'),str(ROOT/'Core/counter.cpp'),str(cpp),'-o',str(binary)],capture_output=True,text=True,timeout=60)
            self.assertEqual(built.returncode,0,built.stdout+built.stderr)
            result=subprocess.run([str(binary)],capture_output=True,text=True,timeout=15)
            self.assertEqual(result.returncode,0,result.stdout+result.stderr)
        self.assertEqual([json.loads(line) for line in result.stdout.splitlines()],
                         [fixture['checkpoint'],fixture['complete']])
        from fantasy_world_generator.kernel_numeric import canonical_bytes
        self.assertEqual(result.stdout.encode(),canonical_bytes(fixture['checkpoint'])+b'\n'+canonical_bytes(fixture['complete'])+b'\n')
