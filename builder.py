#!/usr/bin/env python3
"""Command line for the Builder tab: prepare WHDLoad archives, launch a game in Amiberry, build executables.
Run `python builder.py --help`. The code lives in tabs/builder/core.py."""
import sys

from tabs.builder.core import main

if __name__ == "__main__":
    sys.exit(main())
