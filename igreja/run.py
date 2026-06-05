import sys

from app.single_instance import acquire_single_instance_lock


if not acquire_single_instance_lock():
    sys.exit(0)

from app.main import main

if __name__ == "__main__":
    main()
