# -*- mode: python ; coding: utf-8 -*-
from pathlib import Path

from PyInstaller.utils.hooks import collect_all

root = Path(SPECPATH).resolve()
sounddevice_data, sounddevice_binaries, sounddevice_hidden = collect_all("sounddevice")
pygame_data, pygame_binaries, pygame_hidden = collect_all("pygame")

datas = [
    (str(root / "assets" / "characters" / "zhou_wanqing" / "runtime"), "assets/characters/zhou_wanqing/runtime"),
    (str(root / "assets" / "characters" / "zhou_wanqing" / "character.json"), "assets/characters/zhou_wanqing"),
    (str(root / "assets" / "characters" / "zhou_wanqing" / "ASSET_QA.json"), "assets/characters/zhou_wanqing"),
] + sounddevice_data + pygame_data

a = Analysis(
    [str(root / "run.py")],
    pathex=[str(root)],
    binaries=sounddevice_binaries + pygame_binaries,
    datas=datas,
    hiddenimports=sounddevice_hidden + pygame_hidden,
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[],
    noarchive=False,
    optimize=1,
)
pyz = PYZ(a.pure)

exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name="RNGtuber",
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=False,
    console=False,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
)

coll = COLLECT(
    exe,
    a.binaries,
    a.datas,
    strip=False,
    upx=False,
    upx_exclude=[],
    name="RNGtuber",
)
