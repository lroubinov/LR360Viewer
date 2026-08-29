# -*- mode: python ; coding: utf-8 -*-
from PyInstaller.utils.hooks import collect_all

wv_datas, wv_bins, wv_hidden = collect_all('webview')

datas = [
    ('LR360Viewer.lrplugin/viewer/viewer.html', '.'),
    ('assets/LR360Viewer.ico', '.'),
]
datas += wv_datas

hiddenimports = [
    'webview',
    'webview.platforms.edgechromium',
    'PIL',
    'PIL.Image',
    'clr',
] + wv_hidden

a = Analysis(
    ['LR360Viewer.lrplugin/viewer/server.py'],
    pathex=[],
    binaries=wv_bins,
    datas=datas,
    hiddenimports=hiddenimports,
    hookspath=[],
    hooksconfig={},
    runtime_hooks=['rthook_lr360_icon.py'],
    excludes=[],
    noarchive=False,
)

pyz = PYZ(a.pure)

exe = EXE(
    pyz,
    a.scripts,
    a.binaries,
    a.datas,
    [],
    name='LR360Viewer',
    icon='assets/LR360Viewer.ico',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    console=False,
    disable_windowed_traceback=False,
    argv_emulation=False,
)
