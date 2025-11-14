# -*- mode: python ; coding: utf-8 -*-
import platform
import toml
import pathlib
import sys

architecture = platform.machine()

version = toml.load(pathlib.Path(sys.argv[0]).parents[1].joinpath("pyproject.toml"))
version = version["project"]["version"]
version = version.replace(".", "_")


a = Analysis(
    ['../src/simvue_cli/cli/__init__.py'],
    pathex=[],
    binaries=[],
    datas=[],
    hiddenimports=[],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[],
    noarchive=False,
    optimize=0,
)
pyz = PYZ(a.pure)

exe = EXE(
    pyz,
    a.scripts,
    a.binaries,
    a.datas,
    [],
    name=f'simvue_{version}_{architecture}',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    upx_exclude=[],
    runtime_tmpdir=None,
    console=True,
    onefile=True,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    icon="icon.ico"
)
