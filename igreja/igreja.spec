# -*- mode: python ; coding: utf-8 -*-

import sys
from pathlib import Path

from PyInstaller.utils.hooks import collect_data_files, collect_submodules

tkdnd_datas = collect_data_files("tkinterdnd2")
ttkbootstrap_datas = collect_data_files("ttkbootstrap")
faster_whisper_datas = collect_data_files("faster_whisper")
tkinter_hiddenimports = collect_submodules("tkinter")
project_root = Path.cwd()
python_root = Path(sys.base_prefix)
tcl_root = python_root / "tcl"
tcl_packages_dir = tcl_root / "tcl8"
tcl_library_dir = tcl_root / "tcl8.6"
tk_library_dir = tcl_root / "tk8.6"
python_dll_dir = python_root / "DLLs"
ffmpeg_root = project_root / "vendor" / "ffmpeg"
ffmpeg_binaries = []
tk_datas = []
tk_binaries = []

if ffmpeg_root.exists():
    for file_path in ffmpeg_root.rglob("*"):
        if file_path.is_file():
            relative_parent = file_path.parent.relative_to(project_root)
            ffmpeg_binaries.append((str(file_path), str(relative_parent)))

if tcl_library_dir.exists():
    tk_datas.append((str(tcl_library_dir), "_tcl_data"))

if tcl_packages_dir.exists():
    tk_datas.append((str(tcl_packages_dir), "_tcl_data/tcl8"))

if tk_library_dir.exists():
    tk_datas.append((str(tk_library_dir), "_tk_data"))

for dll_name in ("tcl86t.dll", "tk86t.dll", "_tkinter.pyd"):
    dll_path = python_dll_dir / dll_name
    if dll_path.exists():
        tk_binaries.append((str(dll_path), "."))

a = Analysis(
    ['run.py'],
    pathex=[],
    binaries=ffmpeg_binaries + tk_binaries,
    datas=tkdnd_datas + ttkbootstrap_datas + faster_whisper_datas + tk_datas + [('config.json', '.')],
    hiddenimports=[
        'tkinter',
        '_tkinter',
        'tkinterdnd2',
        'tkinterdnd2.TkinterDnD',
        'pypdf',
        'fitz',
        'pymupdf',
        'ttkbootstrap',
        'yt_dlp',
        'pytubefix',
        'docx',
        'whisper',
        'PIL',
        'rawpy',
    ] + tkinter_hiddenimports,
    hookspath=['app/pyinstaller_hooks'],
    hooksconfig={},
    runtime_hooks=['app/runtime_hooks/pyi_rth_tkinter.py'],
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
    upx=False,
    upx_exclude=['python312.dll', 'vcruntime140.dll', 'vcruntime140_1.dll'],
    runtime_tmpdir=None,
    console=False,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
)
