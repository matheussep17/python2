import os
import sys
from pathlib import Path


def _set_tk_environment():
    meipass = getattr(sys, "_MEIPASS", None)
    if not meipass:
        return

    base_dir = Path(meipass)
    tcl_library = base_dir / "_tcl_data"
    tk_library = base_dir / "_tk_data"
    tcl_package_path = base_dir / "_tcl_data" / "tcl8"

    if tcl_library.exists():
        os.environ["TCL_LIBRARY"] = str(tcl_library)

    if tk_library.exists():
        os.environ["TK_LIBRARY"] = str(tk_library)

    if tcl_package_path.exists():
        os.environ["TCLLIBPATH"] = str(tcl_package_path)


_set_tk_environment()
