#!/usr/bin/env python3
"""Run the DAH aggregate debt-snapshot CLI workflow from the workspace root."""

from __future__ import annotations

import sys
from pathlib import Path


def main() -> int:
    workspace = Path.cwd()
    if not (workspace / "main.py").is_file():
        print("Run this script from the workspace root that contains main.py.")
        return 2
    sys.path.insert(0, str(workspace))
    from main import DahCli

    return DahCli().run(["debt-snapshot", *sys.argv[1:]])


if __name__ == "__main__":
    raise SystemExit(main())
