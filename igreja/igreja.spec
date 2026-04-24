# -*- mode: python ; coding: utf-8 -*-

import sys
from pathlib import Path

import _tkinter
from PyInstaller.utils.hooks import collect_all, collect_submodules


def _unique_pairs(items):
    seen = set()
    result = []
    for source, destination in items:
        normalized = (str(Path(source)), destination.replace("\\", "/"))
        if normalized in seen:
            continue
        seen.add(normalized)
        result.append((normalized[0], normalized[1]))
    return result


def _find_first_existing(paths):
    for path in paths:
        if path.exists():
            return path
    raise FileNotFoundError(f"Nenhum caminho valido encontrado dentre: {paths}")


def _find_tcl_root():
    candidates = []
    for base in {
        Path(sys.base_prefix),
        Path(sys.exec_prefix),
        Path(sys.prefix),
        Path(_tkinter.__file__).resolve().parent.parent,
        Path(_tkinter.__file__).resolve().parents[2],
    }:
        candidates.append(base / "tcl")

    return _find_first_existing(candidates)


def _find_versioned_dir(root, pattern, required_files):
    matches = []
    for candidate in root.glob(pattern):
        if candidate.is_dir() and all((candidate / relative_path).exists() for relative_path in required_files):
            matches.append(candidate)

    if not matches:
        raise FileNotFoundError(f"Nao foi possivel localizar '{pattern}' em '{root}'.")

    return sorted(matches)[-1]


def _find_runtime_binary(name):
    candidates = []
    for base in {
        Path(_tkinter.__file__).resolve().parent,
        Path(sys.base_prefix) / "DLLs",
        Path(sys.exec_prefix) / "DLLs",
        Path(sys.prefix) / "DLLs",
    }:
        candidates.append(base / name)

    return _find_first_existing(candidates)


project_root = Path.cwd()
ffmpeg_root = project_root / "vendor" / "ffmpeg"
ffmpeg_binaries = []

if ffmpeg_root.exists():
    for file_path in ffmpeg_root.rglob("*"):
        if file_path.is_file():
            relative_parent = file_path.parent.relative_to(project_root)
            ffmpeg_binaries.append((str(file_path), str(relative_parent)))

tcl_root = _find_tcl_root()
tcl_library_dir = _find_versioned_dir(tcl_root, "tcl*", ("init.tcl",))
tcl_packages_dir = _find_versioned_dir(tcl_root, "tcl8", ("pkgIndex.tcl",))
tk_library_dir = _find_versioned_dir(tcl_root, "tk*", ("tk.tcl",))

tk_datas = _unique_pairs(
    [
        (str(tcl_library_dir), "_tcl_data"),
        (str(tcl_packages_dir), "_tcl_data/tcl8"),
        (str(tk_library_dir), "_tk_data"),
    ]
)

tk_binaries = _unique_pairs(
    [
        (str(_find_runtime_binary("_tkinter.pyd")), "."),
        (str(_find_runtime_binary("tcl86t.dll")), "."),
        (str(_find_runtime_binary("tk86t.dll")), "."),
    ]
)

tkdnd_datas, tkdnd_binaries, tkdnd_hiddenimports = collect_all("tkinterdnd2")
ttkbootstrap_datas, ttkbootstrap_binaries, ttkbootstrap_hiddenimports = collect_all("ttkbootstrap")
faster_whisper_datas, faster_whisper_binaries, faster_whisper_hiddenimports = collect_all("faster_whisper")
tkinter_hiddenimports = collect_submodules("tkinter")

a = Analysis(
    ['run.py'],
    pathex=[],
    binaries=_unique_pairs(ffmpeg_binaries + tk_binaries + tkdnd_binaries + ttkbootstrap_binaries + faster_whisper_binaries),
    datas=_unique_pairs(tkdnd_datas + ttkbootstrap_datas + faster_whisper_datas + tk_datas + [('config.json', '.')]),
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
    ] + tkinter_hiddenimports + tkdnd_hiddenimports + ttkbootstrap_hiddenimports + faster_whisper_hiddenimports,
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
