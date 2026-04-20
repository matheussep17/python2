import sys
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from app.licensing import device_fingerprint, machine_name


def main():
    print(f"Computador: {machine_name()}")
    print(f"Fingerprint: {device_fingerprint()}")


if __name__ == "__main__":
    main()
