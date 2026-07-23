"""Enable ``python -m arena``."""

from __future__ import annotations

import sys

from arena.cli import main

if __name__ == "__main__":
    sys.exit(main())
