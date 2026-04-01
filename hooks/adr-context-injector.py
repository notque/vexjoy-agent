#!/usr/bin/env python3
# hook-version: 2.0.0
"""UserPromptSubmit: ADR context injector — DISABLED pending redesign."""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent / "lib"))

from hook_utils import empty_output


def main():
    empty_output("UserPromptSubmit").print_and_exit()


if __name__ == "__main__":
    try:
        main()
    except Exception:
        pass
    finally:
        sys.exit(0)
