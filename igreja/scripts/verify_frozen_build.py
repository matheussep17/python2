from __future__ import annotations

import argparse
import tempfile
from pathlib import Path

from PyInstaller.archive.readers import CArchiveReader
from PyInstaller.loader.pyimod01_archive import ZlibArchiveReader


REQUIRED_ARCHIVE_PREFIXES = (
    "_tcl_data\\",
    "_tk_data\\",
    "vendor\\ffmpeg\\bin\\",
)

REQUIRED_ARCHIVE_ITEMS = (
    "_tcl_data\\init.tcl",
    "_tk_data\\tk.tcl",
    "tcl86t.dll",
    "tk86t.dll",
    "_tkinter.pyd",
    "vendor\\ffmpeg\\bin\\ffmpeg.exe",
    "vendor\\ffmpeg\\bin\\ffprobe.exe",
)

REQUIRED_PYZ_MODULES = (
    "ttkbootstrap",
    "ttkbootstrap.style",
    "ttkbootstrap.themes",
    "ttkbootstrap.themes.standard",
    "ttkbootstrap.localization",
    "tkinterdnd2",
    "tkinterdnd2.TkinterDnD",
)


def _normalize(name: str) -> str:
    return name.replace("/", "\\")


def _load_pyz_toc(executable_path: Path) -> set[str]:
    carchive = CArchiveReader(str(executable_path))
    pyz_bytes = carchive.extract("PYZ.pyz")

    with tempfile.NamedTemporaryFile(suffix=".pyz", delete=False) as temp_file:
        temp_file.write(pyz_bytes)
        temp_path = Path(temp_file.name)

    try:
        pyz = ZlibArchiveReader(str(temp_path))
        return set(pyz.toc)
    finally:
        temp_path.unlink(missing_ok=True)


def verify_build(executable_path: Path) -> None:
    archive = CArchiveReader(str(executable_path))
    toc = {_normalize(name) for name in archive.toc}
    pyz_toc = _load_pyz_toc(executable_path)

    missing_archive_items = [name for name in REQUIRED_ARCHIVE_ITEMS if name not in toc]
    missing_archive_prefixes = [prefix for prefix in REQUIRED_ARCHIVE_PREFIXES if not any(name.startswith(prefix) for name in toc)]
    missing_pyz_modules = [name for name in REQUIRED_PYZ_MODULES if name not in pyz_toc]

    problems = []
    if missing_archive_items:
        problems.append("Itens ausentes no executavel: " + ", ".join(missing_archive_items))
    if missing_archive_prefixes:
        problems.append("Pastas obrigatorias ausentes no executavel: " + ", ".join(missing_archive_prefixes))
    if missing_pyz_modules:
        problems.append("Modulos Python ausentes no PYZ: " + ", ".join(missing_pyz_modules))

    if problems:
        raise RuntimeError("\n".join(problems))


def main() -> None:
    parser = argparse.ArgumentParser(description="Valida se os requireds criticos entraram na build do PyInstaller.")
    parser.add_argument("executable", type=Path, help="Caminho para o executavel gerado pelo PyInstaller.")
    args = parser.parse_args()

    verify_build(args.executable.resolve())
    print(f"Build validada com sucesso: {args.executable}")


if __name__ == "__main__":
    main()
