#!/usr/bin/env python3
"""Detect available image generation backend.

Checks environment for API keys and outputs the backend name.
Output: "gemini" if GEMINI_API_KEY or GOOGLE_API_KEY is set, else "ask"
"""

import os
import sys


def detect() -> str:
    """Return the backend name based on available environment variables."""
    if os.environ.get("GEMINI_API_KEY") or os.environ.get("GOOGLE_API_KEY"):
        return "gemini"
    return "ask"


if __name__ == "__main__":
    result = detect()
    print(result)
    sys.exit(0)
