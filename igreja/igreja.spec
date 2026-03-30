# -*- mode: python ; coding: utf-8 -*-

from pathlib import Path

from PyInstaller.utils.hooks import collect_data_files

tkdnd_datas = collect_data_files("tkinterdnd2")
project_root = Path.cwd()
ffmpeg_root = project_root / "vendor" / "ffmpeg"
ffmpeg_binaries = []

if ffmpeg_root.exists():
    for file_path in ffmpeg_root.rglob("*"):
        if file_path.is_file():
            relative_parent = file_path.parent.relative_to(project_root)
            ffmpeg_binaries.append((str(file_path), str(relative_parent)))

a = Analysis(
    ['run.py'],
    pathex=[],
    binaries=ffmpeg_binaries,
    datas=tkdnd_datas,
    hiddenimports=['tkinterdnd2', 'tkinterdnd2.TkinterDnD', 'pypdf', 'fitz', 'pymupdf'],
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
    name='Igreja',
    icon='app/assets/app_icon.ico',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    upx_exclude=[],
    runtime_tmpdir=None,
    console=False,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
)
