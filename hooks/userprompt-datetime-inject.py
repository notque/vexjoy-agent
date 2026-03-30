#!/usr/bin/env python3
# hook-version: 1.0.0
"""UserPromptSubmit hook: inject current date/time into model context.

Prints the current date and time so the model has a timestamp reference
on every user prompt. This enables time-awareness within a session —
understanding elapsed time, giving reasonable estimates, and knowing
whether an operation is taking seconds or hours.
"""

import sys
from datetime import datetime, timezone

try:
    now = datetime.now(timezone.utc).astimezone()
    print(f"[datetime] {now.strftime('%Y-%m-%d %H:%M:%S %Z')}")
except Exception:
    pass

sys.exit(0)
