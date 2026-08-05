# -*- mode: python ; coding: utf-8 -*-
from PyInstaller.utils.hooks import collect_all

datas = [('litmetica3d/mc_assets/26.2.zip', 'litmetica3d/mc_assets')]
binaries = []
hiddenimports = ['litmetica3d.conversion', 'litmetica3d.emission', 'litmetica3d.gui_qt', 'litmetica3d.gui_app', 'litmetica3d.gui_styles']
for package in ('manifold3d', 'PIL'):
    collected = collect_all(package)
    datas += collected[0]
    binaries += collected[1]
    hiddenimports += collected[2]

a = Analysis(
    ['run_gui.py'], pathex=[], binaries=binaries, datas=datas,
    hiddenimports=hiddenimports, hookspath=[], hooksconfig={},
    runtime_hooks=[], excludes=['tkinter'], noarchive=False, optimize=0,
)
pyz = PYZ(a.pure)
exe = EXE(
    pyz, a.scripts, [],
    exclude_binaries=True,
    name='litmetica3d-v0.5.0', debug=False,
    bootloader_ignore_signals=False, strip=False, upx=True,
    console=False,
    disable_windowed_traceback=False,
)
coll = COLLECT(
    exe, a.binaries, a.datas,
    strip=False, upx=True, upx_exclude=[],
    name='litmetica3d-v0.5.0',
)
