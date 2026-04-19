import os
import re
import sys
from pathlib import Path


def main() -> int:
    ref_name = (os.environ.get("GITHUB_REF_NAME") or "").strip()
    if not ref_name:
        print("GITHUB_REF_NAME nao definido; nada para validar.")
        return 0

    match = re.fullmatch(r"v?(.+)", ref_name)
    if not match:
        print(f"Tag invalida: {ref_name}")
        return 1

    expected_version = match.group(1)

    namespace: dict[str, str] = {}
    version_file = Path(__file__).resolve().parents[1] / "app" / "version.py"
    exec(version_file.read_text(encoding="utf-8"), namespace)
    current_version = str(namespace.get("APP_VERSION", "")).strip()

    if current_version != expected_version:
        print(
            "APP_VERSION divergente da tag.\n"
            f"Tag: {expected_version}\n"
            f"APP_VERSION: {current_version}"
        )
        return 1

    print(f"APP_VERSION confere com a tag: {current_version}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
