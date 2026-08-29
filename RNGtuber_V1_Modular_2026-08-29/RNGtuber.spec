# -*- mode: python ; coding: utf-8 -*-
from pathlib import Path
from PyInstaller.utils.hooks import collect_submodules

root = Path(SPECPATH).resolve()

datas = [
    (str(root / "assets" / "characters" / "zhou_wanqing" / "runtime"), "assets/characters/zhou_wanqing/runtime"),
    (str(root / "assets" / "characters" / "zhou_wanqing" / "character.json"), "assets/characters/zhou_wanqing"),
    (str(root / "assets" / "characters" / "zhou_wanqing" / "ASSET_QA.json"), "assets/characters/zhou_wanqing"),
]

# PyInstaller's static analysis can miss newly split package modules when an
# older onedir artifact is reused/patched.  Force the entire local rngtuber
# package into the build so modules such as rngtuber.renderer can never be
# omitted from the Windows release.
rngtuber_hiddenimports = collect_submodules("rngtuber")

hiddenimports = sorted(set([
    "sounddevice",
    "pygame",
    *rngtuber_hiddenimports,
]))

a = Analysis(
    [str(root / "run.py")],
    pathex=[str(root)],
    binaries=[],
    datas=datas,
    hiddenimports=hiddenimports,
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=["pygame.tests", "pygame.examples", "pygame.docs"],
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
