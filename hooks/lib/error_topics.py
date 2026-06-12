"""Extended error-topic classification for the error-learner hook.

The live learning DB shows topic=unknown dominating category=error rows
(~4100 unknown vs ~1300 classified). The dominant unknown shapes are CLI
usage errors, test failures, lint output, command-not-found, JSON parse
failures, git conflicts, and HTTP/network errors. This module maps those
shapes to concrete topics so new entries stop landing on "unknown".

Layering: ``classify_error`` (learning_db_v2's base taxonomy) keeps first
claim — an already-known shape is never reclassified. Only a base
"unknown" is retried against the extended patterns; "unknown" stays the
fallback. learning_db_v2.py itself is not edited (a pre-existing SQLi
false-positive there trips the commit security gate); this module only
imports its public classifier.

Patterns are conservative and word/phrase-anchored — a wrong topic is
worse than "unknown" (it attaches the wrong default fix action).
"""

import re

from learning_db_v2 import classify_error

# First match wins (dict order). Lower-cased message is searched.
EXTENDED_ERROR_TYPES = {
    "command_not_found": [
        r"command not found",
        r"not recognized as an internal",
    ],
    "json_parse": [
        r"jsondecodeerror",
        r"invalid json",
        r"failed to parse json",
        r"unexpected end of json",
        r"expecting value: line",
    ],
    "git_conflict": [
        r"merge conflict",
        r"conflict \(content\)",
        r"automatic merge failed",
        r"needs merge",
    ],
    "usage_error": [
        r"\busage: ",
        r"unrecognized arguments",
        r"the following arguments are required",
        r"invalid option",
        r"unknown option",
    ],
    "lint_error": [
        r"\bruff (check|format)",
        r"would reformat",
        r"fixable with the .--fix.",
    ],
    "test_failure": [
        r"assertionerror",
        r"=== failures ===",
        r"\b\d+ failed\b",
    ],
    "network": [
        r"http error \d{3}",
        r"\b404 not found\b",
        r"could not resolve host",
        r"connection reset",
        r"\bssl(error| certificate)",
    ],
}


def classify_error_topic(message: str) -> str:
    """Topic for an error message: base taxonomy first, then extended shapes.

    Returns "unknown" only when neither taxonomy matches.
    """
    if not message:
        return "unknown"
    base = classify_error(message)
    if base != "unknown":
        return base
    low = message.lower()
    for topic, patterns in EXTENDED_ERROR_TYPES.items():
        if any(re.search(p, low) for p in patterns):
            return topic
    return "unknown"
