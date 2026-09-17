"""Locate a C++17 compiler for headless native tests (clang, g++, or MSVC)."""
from __future__ import annotations

import os
from pathlib import Path
import shutil
import subprocess
import sys


def visual_studio_cl() -> str | None:
    vswhere = Path(os.environ.get('ProgramFiles(x86)', r'C:\Program Files (x86)')) / 'Microsoft Visual Studio/Installer/vswhere.exe'
    if not vswhere.is_file():
        return None
    found = subprocess.check_output(
        [str(vswhere), '-latest', '-products', '*',
         '-requires', 'Microsoft.VisualStudio.Component.VC.Tools.x86.x64',
         '-find', r'**\Hostx64\x64\cl.exe'],
        text=True, timeout=15).strip().splitlines()
    return found[0] if found else None


def compiler_command() -> list[str] | None:
    unix = shutil.which('clang++') or shutil.which('g++')
    if unix:
        extra = os.environ.get('FANTASY_WORLD_GENERATOR_CXXFLAGS', '')
        import shlex
        flags = shlex.split(extra)
        if sys.platform == 'darwin':
            try:
                sdk = subprocess.check_output(['xcrun', '--show-sdk-path'], text=True, timeout=10).strip()
                headers = Path(sdk) / 'usr/include/c++/v1'
                if headers.is_dir():
                    flags += ['-isystem', str(headers)]
            except (OSError, subprocess.CalledProcessError):
                pass
        return [unix, '-std=c++17', '-Wall', '-Wextra', '-Werror', '-pedantic', *flags]
    if os.name != 'nt':
        return None
    cl = visual_studio_cl()
    if not cl:
        return None
    return [cl, '/nologo', '/std:c++17', '/EHsc', '/W3', '/WX']


def compile_native(sources: list[Path], include: Path, output: Path) -> None:
    command = compiler_command()
    if command is None:
        raise FileNotFoundError('no C++17 compiler')
    args = list(command)
    if Path(command[0]).name.lower() == 'cl.exe':
        args += [f'/I{include}', f'/Fe{output}', '/Fo' + str(output.parent) + '\\']
        args += [str(path) for path in sources]
        env = msvc_env(command[0])
    else:
        args += ['-I', str(include), *[str(path) for path in sources], '-o', str(output)]
        env = None
    built = subprocess.run(args, capture_output=True, text=True, timeout=90, env=env)
    if built.returncode:
        raise AssertionError(built.stdout + built.stderr)


def msvc_env(cl_path: str) -> dict[str, str]:
    vcvars = Path(cl_path).resolve().parents[3] / 'Auxiliary' / 'Build' / 'vcvars64.bat'
    # typical: .../VC/Auxiliary/Build/vcvars64.bat from Hostx64/x64/cl.exe
    # parents: 0 x64, 1 Hostx64, 2 bin, 3 MSVC version, 4 Tools, 5 VC
    vc_root = Path(cl_path).resolve()
    for parent in vc_root.parents:
        candidate = parent / 'Auxiliary' / 'Build' / 'vcvars64.bat'
        if candidate.is_file():
            vcvars = candidate
            break
    else:
        raise FileNotFoundError('vcvars64.bat not found from ' + cl_path)
    dumped = subprocess.check_output(f'"{vcvars}" && set', shell=True, text=True, timeout=60)
    env = dict(os.environ)
    for line in dumped.splitlines():
        if '=' in line:
            key, _, value = line.partition('=')
            env[key] = value
    return env
