#!/usr/bin/env python3
"""Multi-stage Jev pipeline for code review.

Three Jev stages cascade, each stage's output shaping the next:
  1. CLASSIFY: diff type, scope, risk, language (1 Jev call).
  2. DOMAIN CHECKS: type-specific quality checks + universal code-smell
     checks, questions selected by Stage 1's classification (1 Jev call).
  3. VERIFY: adversarial false-positive filter on flagged findings from
     Stage 2 (1 Jev call, skipped when nothing is flagged).

Total: 2-3 Jev calls for a complete review.

Input: unified diff via --diff-file, --pr (gh pr diff), or stdin.
Output: structured JSON findings to stdout.

Usage:
    git diff HEAD~1 | python3 scripts/jev-cascade-review.py --json-compact
    python3 scripts/jev-cascade-review.py --diff-file pr.diff --threshold 0.6 --verbose
    python3 scripts/jev-cascade-review.py --pr 42 --summary

Exit codes:
    0 -- always (output is JSON to stdout; errors go to stderr)
"""

from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
from pathlib import Path

_SCRIPTS_DIR = Path(__file__).resolve().parent
if str(_SCRIPTS_DIR) not in sys.path:
    sys.path.insert(0, str(_SCRIPTS_DIR))
import jev_router_common

DEFAULT_THRESHOLD = 0.6
DEFAULT_TIMEOUT = 8.0

LARGE_DIFF_CHAR_THRESHOLD = 8000
LARGE_DIFF_FILE_THRESHOLD = 20
DIFF_TYPE_CRITERIA: dict[str, dict[str, str | list[str]]] = {
    "feature_addition": {
        "what": "New functionality",
        "signals": ["new files", "new exports", "new routes"],
    },
    "bug_fix": {
        "what": "Fixing incorrect behavior",
        "signals": ["test changes", "edge case handling"],
    },
    "refactor": {
        "what": "Restructuring without behavior change",
        "signals": ["renames", "extractions", "no test changes"],
    },
    "config_change": {
        "what": "Build, deploy, or environment config",
        "signals": ["yaml/json/toml changes", "env vars"],
    },
    "test_update": {
        "what": "Test additions or modifications",
    },
    "docs_update": {
        "what": "Documentation changes",
    },
}

SCOPE_CRITERIA = [
    "Trivial (1-5 lines)",
    "Small (6-50 lines)",
    "Medium (51-200 lines)",
    "Large (200+ lines)",
]

RISK_CRITERIA = [
    "Low risk -- safe, isolated change",
    "Medium risk -- touches shared code",
    "High risk -- changes core logic, APIs, or data",
    "Critical risk -- security, auth, or data integrity",
]

LANGUAGE_CRITERIA: dict[str, str] = {
    "python": "Python (.py)",
    "typescript": "TypeScript (.ts, .tsx)",
    "javascript": "JavaScript (.js, .jsx)",
    "go": "Go (.go)",
    "rust": "Rust (.rs)",
    "java": "Java (.java)",
    "kotlin": "Kotlin (.kt)",
    "swift": "Swift (.swift)",
    "shell": "Shell/Bash (.sh)",
    "sql": "SQL (.sql)",
    "css": "CSS/SCSS (.css, .scss)",
    "html": "HTML (.html)",
    "yaml": "YAML (.yaml, .yml)",
    "json": "JSON (.json)",
    "toml": "TOML (.toml)",
    "markdown": "Markdown (.md)",
    "other": "Other or mixed languages",
}
FEATURE_CHECKS: dict[str, dict] = {
    "has_tests": {
        "type": "noul",
        "instructions": "True when this feature addition includes test code (test files, test functions, assertions).",
        "criteria": {
            "true": {
                "what": "Tests accompany the feature",
                "examples": ["test_ functions", "assert statements", "new test files"],
            },
            "false": {
                "what": "No tests for the new functionality",
                "examples": ["only production code added", "no test files touched"],
            },
        },
    },
    "has_error_handling": {
        "type": "noul",
        "instructions": "True when this feature handles failure cases: try/except, error returns, validation, fallback paths.",
        "criteria": {
            "true": {
                "what": "Failure paths are handled",
                "examples": ["try/except blocks", "input validation", "fallback defaults"],
            },
            "false": {
                "what": "Happy path only, no error handling",
                "examples": ["no try/except", "no validation", "assumes valid input"],
            },
        },
    },
    "is_backward_compatible": {
        "type": "noul",
        "instructions": (
            "True when this change preserves existing public API signatures, argument types, "
            "return types, and behavior. False when it changes or removes an existing public "
            "function/method signature, renames a public export, or changes the shape of a return value."
        ),
        "criteria": {
            "true": {
                "what": "Existing APIs preserved",
                "examples": ["new function added, existing unchanged", "optional parameter added with default"],
            },
            "false": {
                "what": "Breaking change to existing API",
                "examples": ["function renamed", "required parameter added", "return type changed"],
            },
        },
    },
    "follows_patterns": {
        "type": "noul",
        "instructions": (
            "True when the new code follows the conventions visible in the surrounding diff context: "
            "naming, error handling, import style, file organization."
        ),
        "criteria": {
            "true": {
                "what": "Consistent with surrounding code style",
                "examples": ["same naming convention", "similar error handling pattern"],
            },
            "false": {
                "what": "Deviates from established patterns",
                "examples": ["different naming style", "different error handling approach"],
            },
        },
    },
}

BUG_FIX_CHECKS: dict[str, dict] = {
    "has_regression_test": {
        "type": "noul",
        "instructions": "True when there is a test that specifically covers the bug being fixed -- a test that would have caught this bug before the fix.",
        "criteria": {
            "true": {
                "what": "Regression test present",
                "examples": ["test for the exact edge case", "test that reproduces the bug"],
            },
            "false": {
                "what": "No regression test",
                "examples": ["fix only, no test added", "existing tests not updated"],
            },
        },
    },
    "root_cause_addressed": {
        "type": "noul",
        "instructions": (
            "True when the fix addresses the root cause of the bug. "
            "False when it only patches the symptom (e.g., adding a null check without fixing why null appears)."
        ),
        "criteria": {
            "true": {
                "what": "Root cause fixed",
                "examples": ["underlying logic corrected", "data flow fixed at source"],
            },
            "false": {
                "what": "Symptom patched, root cause remains",
                "examples": ["null check added but null source not fixed", "retry hides the real failure"],
            },
        },
    },
    "side_effects": {
        "type": "noul",
        "instructions": "True when this fix could introduce new bugs: changes shared state, alters control flow used elsewhere, or modifies a hot path.",
        "criteria": {
            "true": {
                "what": "Fix risks side effects",
                "examples": ["shared mutable state changed", "control flow altered in a shared function"],
            },
            "false": {
                "what": "Fix is isolated",
                "examples": ["change scoped to one function", "no shared state touched"],
            },
        },
    },
}

REFACTOR_CHECKS: dict[str, dict] = {
    "behavior_preserved": {
        "type": "noul",
        "instructions": "True when observable behavior is unchanged: same inputs produce same outputs, same side effects, same error cases.",
        "criteria": {
            "true": {
                "what": "Behavior unchanged",
                "examples": ["pure rename", "extract method with same logic", "move file with updated imports"],
            },
            "false": {
                "what": "Behavior may have changed",
                "examples": ["logic rewritten", "error handling changed", "default values altered"],
            },
        },
    },
    "improves_readability": {
        "type": "noul",
        "instructions": "True when the refactored code is more readable: shorter functions, clearer names, less nesting, better structure.",
        "criteria": {
            "true": {
                "what": "More readable after refactoring",
                "examples": ["long function split into focused helpers", "deeply nested code flattened"],
            },
            "false": {
                "what": "Readability unchanged or worse",
                "examples": ["same complexity, different arrangement", "more indirection added"],
            },
        },
    },
    "reduces_complexity": {
        "type": "noul",
        "instructions": "True when cyclomatic complexity is reduced: fewer branches, fewer nested conditions, simpler control flow.",
        "criteria": {
            "true": {
                "what": "Complexity reduced",
                "examples": ["nested ifs replaced with early returns", "switch replaced with lookup table"],
            },
            "false": {
                "what": "Complexity unchanged or increased",
                "examples": ["same branching, different shape", "new branches added"],
            },
        },
    },
}

CONFIG_CHECKS: dict[str, dict] = {
    "has_secrets": {
        "type": "noul",
        "instructions": "True when this config change adds, exposes, or hardcodes secrets, credentials, API keys, tokens, or passwords.",
        "criteria": {
            "true": {
                "what": "Secrets exposed in config",
                "examples": ["API key in YAML", "password in env file committed", "token hardcoded"],
            },
            "false": {
                "what": "No secrets in config",
                "examples": ["environment variable reference", "secret manager path", "placeholder value"],
            },
        },
    },
    "env_specific": {
        "type": "noul",
        "instructions": "True when this config change is environment-specific (only applies to dev, staging, or production) rather than universal.",
        "criteria": {
            "true": {
                "what": "Environment-specific config",
                "examples": ["production-only setting", "dev database URL", "staging feature flag"],
            },
            "false": {
                "what": "Universal config change",
                "examples": ["applies to all environments", "build tool setting", "linter rule"],
            },
        },
    },
}

# Universal checks applied regardless of diff type.
UNIVERSAL_CHECKS: dict[str, dict] = {
    "has_slop": {
        "type": "noul",
        "instructions": "True when the diff contains AI-generated boilerplate with no clear purpose: cookie-cutter code, trivial wrappers, or obviously generated filler.",
        "criteria": {
            "true": {
                "what": "AI-generated boilerplate",
                "examples": [
                    "trivial getter/setter with no logic",
                    "copy-pasted function with only name changed",
                    "boilerplate comments restating code",
                ],
            },
            "false": {
                "what": "Purposeful code",
                "examples": [
                    "function with meaningful logic",
                    "wrapper adding retries or validation",
                    "well-structured new module",
                ],
            },
        },
    },
    "has_pointless_comments": {
        "type": "noul",
        "instructions": "True when added comments restate what the code obviously does, add no information, or are generic boilerplate.",
        "criteria": {
            "true": {
                "what": "Comments that restate code",
                "examples": ["// increment counter", "# return the result", "// set the variable"],
            },
            "false": {
                "what": "Comments explaining WHY or documenting non-obvious behavior",
                "examples": [
                    "// Retry with backoff -- API rate-limits at 100 req/s",
                    "# Must lock before read: concurrent writers possible",
                ],
            },
        },
    },
}

NAMING_QUALITY_CRITERIA = [
    "Poor -- vague names",
    "Acceptable",
    "Good -- domain-specific",
    "Excellent",
]

# Index of the level whose text contains "poor"; naming at or below it is flagged.
_NAMING_POOR_LEVEL = next(i for i, label in enumerate(NAMING_QUALITY_CRITERIA) if "poor" in label.lower())

# Map diff_type -> domain-specific check definitions.
DOMAIN_CHECK_MAP: dict[str, dict[str, dict]] = {
    "feature_addition": FEATURE_CHECKS,
    "bug_fix": BUG_FIX_CHECKS,
    "refactor": REFACTOR_CHECKS,
    "config_change": CONFIG_CHECKS,
}


def _build_stage1_payload(diff_text: str) -> dict:
    """Build Stage 1 Jev payload: classify the diff by type, scope, risk, language.

    v2: 4 original Choices/Scores + 8 structural Nouls that detect specific
    risk patterns the broad risk Score misses.
    """
    questions: dict[str, dict] = {
        "diff_type": {
            "type": "choice",
            "instructions": (
                "Classify this diff into the single best-matching category based on the nature of the changes. "
                "Look at what was added, removed, and modified to determine the primary purpose."
            ),
            "criteria": DIFF_TYPE_CRITERIA,
        },
        "scope": {
            "type": "score",
            "instructions": "Rate the size/scope of this diff based on the number of meaningful lines changed.",
            "criteria": SCOPE_CRITERIA,
        },
        "risk": {
            "type": "score",
            "instructions": (
                "Rate the risk level of this diff based on what it touches: isolated utilities are low risk, "
                "shared code is medium, core logic/APIs/data are high, security/auth/data integrity are critical."
            ),
            "criteria": RISK_CRITERIA,
        },
        "language": {
            "type": "choice",
            "instructions": "Pick the primary programming language of this diff based on the file extensions and syntax.",
            "criteria": LANGUAGE_CRITERIA,
        },
        # v2 structural Nouls: detect specific patterns the broad risk Score misses.
        "has_logic_error_risk": {
            "type": "noul",
            "instructions": (
                "True when this diff modifies conditional logic, loop bounds, comparison operators, "
                "or arithmetic in ways that could silently produce wrong results."
            ),
            "criteria": {
                "true": {
                    "what": "Logic changes that could produce wrong results silently",
                    "examples": [
                        "Changed > to >= in a boundary check",
                        "Modified loop termination condition",
                        "Altered boolean expression in a filter",
                    ],
                    "not_for": "Adding new logic from scratch (that is a feature, not a logic change risk).",
                },
                "false": {
                    "what": "No changes to conditional or arithmetic logic",
                    "examples": [
                        "Renamed variables without changing logic",
                        "Added a new function with its own logic",
                        "Changed string literals or messages",
                    ],
                },
            },
        },
        "has_concurrency_risk": {
            "type": "noul",
            "instructions": (
                "True when this diff touches shared mutable state, locking, async/await patterns, "
                "goroutine/thread creation, or concurrent data structures."
            ),
            "criteria": {
                "true": {
                    "what": "Changes to concurrent or shared-state code",
                    "examples": [
                        "Modified a mutex/lock acquisition pattern",
                        "Changed async function that shares state with other coroutines",
                        "Altered a channel or queue operation",
                    ],
                    "not_for": "Pure functions or isolated synchronous code with no shared state.",
                },
                "false": {
                    "what": "No concurrent or shared-state patterns",
                    "examples": [
                        "Modified a pure function",
                        "Changed a local variable",
                        "Added a new standalone utility",
                    ],
                },
            },
        },
        "has_security_surface": {
            "type": "noul",
            "instructions": (
                "True when this diff touches authentication, authorization, input validation, "
                "cryptographic operations, or user-facing permission checks."
            ),
            "criteria": {
                "true": {
                    "what": "Changes to security-relevant code paths",
                    "examples": [
                        "Modified password hashing or token generation",
                        "Changed permission check logic",
                        "Altered input sanitization or validation",
                        "Modified CORS, CSP, or security headers",
                    ],
                    "not_for": "Adding new non-security features that happen to be in a file that also has auth code.",
                },
                "false": {
                    "what": "No security-relevant code touched",
                    "examples": [
                        "Changed UI styling",
                        "Modified test fixtures",
                        "Updated documentation",
                    ],
                },
            },
        },
        "has_data_integrity_risk": {
            "type": "noul",
            "instructions": (
                "True when this diff modifies database queries, schema definitions, data migrations, "
                "serialization/deserialization, or data validation that protects stored data."
            ),
            "criteria": {
                "true": {
                    "what": "Changes that could corrupt or lose data",
                    "examples": [
                        "Modified a SQL query that writes data",
                        "Changed a migration script",
                        "Altered serialization format for persisted objects",
                    ],
                    "not_for": "Read-only database queries or data display code.",
                },
                "false": {
                    "what": "No data persistence changes",
                    "examples": [
                        "Modified a read-only endpoint",
                        "Changed how data is displayed, not stored",
                        "Updated in-memory-only calculations",
                    ],
                },
            },
        },
        "has_api_contract_change": {
            "type": "noul",
            "instructions": (
                "True when this diff changes a public API surface: HTTP endpoints, function signatures "
                "exported to other modules, CLI argument parsing, or wire protocol formats."
            ),
            "criteria": {
                "true": {
                    "what": "Public interface changed",
                    "examples": [
                        "Added required parameter to a public function",
                        "Changed HTTP response shape",
                        "Renamed an exported function or class",
                        "Modified CLI argument parsing",
                    ],
                    "not_for": "Internal-only functions, private methods, or test helpers.",
                },
                "false": {
                    "what": "Only internal implementation changed",
                    "examples": [
                        "Refactored a private helper",
                        "Changed internal variable names",
                        "Modified how a result is computed without changing its shape",
                    ],
                },
            },
        },
        "has_error_path_change": {
            "type": "noul",
            "instructions": (
                "True when this diff modifies error handling, exception paths, fallback behavior, "
                "or retry logic in ways that change what happens on failure."
            ),
            "criteria": {
                "true": {
                    "what": "Error handling behavior changed",
                    "examples": [
                        "Changed which exception types are caught",
                        "Modified retry count or backoff strategy",
                        "Altered fallback behavior on service unavailability",
                    ],
                    "not_for": "Adding new error handling to code that had none (that is an improvement, not a risk).",
                },
                "false": {
                    "what": "Error handling unchanged or newly added",
                    "examples": [
                        "Added try/except to unprotected code",
                        "No changes to catch blocks or error returns",
                        "Only happy-path code modified",
                    ],
                },
            },
        },
        "has_performance_implication": {
            "type": "noul",
            "instructions": (
                "True when this diff changes algorithm complexity, adds/removes caching, modifies "
                "batch sizes, changes query patterns, or alters loop bounds in performance-sensitive code."
            ),
            "criteria": {
                "true": {
                    "what": "Changes with performance implications",
                    "examples": [
                        "Replaced O(n) lookup with O(n²) nested loop",
                        "Removed caching from a hot path",
                        "Changed batch size from 100 to 10000",
                        "Added an N+1 query pattern",
                    ],
                    "not_for": "Performance-neutral changes like renaming or reformatting.",
                },
                "false": {
                    "what": "No performance-sensitive changes",
                    "examples": [
                        "Renamed a function",
                        "Changed a log message",
                        "Modified test assertions",
                    ],
                },
            },
        },
        "has_backwards_incompatibility": {
            "type": "noul",
            "instructions": (
                "True when this diff removes, renames, or changes the type of something that existing "
                "consumers depend on: exported functions, config keys, environment variables, database columns."
            ),
            "criteria": {
                "true": {
                    "what": "Existing consumers would break",
                    "examples": [
                        "Removed a function that other modules import",
                        "Renamed a config key without a migration",
                        "Changed a return type from string to dict",
                    ],
                    "not_for": "Additive changes (new function, new optional parameter with default, new config key).",
                },
                "false": {
                    "what": "Purely additive or internal changes",
                    "examples": [
                        "Added a new function",
                        "Added optional parameter with a default",
                        "Changed only internal implementation",
                    ],
                },
            },
        },
    }
    return {"state": diff_text, "model": jev_router_common.JEV_MODEL, "questions": questions}


_V2_STAGE1_NOULS = [
    "has_logic_error_risk",
    "has_concurrency_risk",
    "has_security_surface",
    "has_data_integrity_risk",
    "has_api_contract_change",
    "has_error_path_change",
    "has_performance_implication",
    "has_backwards_incompatibility",
]


def _parse_stage1(data: dict) -> dict:
    """Parse Stage 1 answers into a classification dict.

    v2: includes 8 structural Nouls alongside the original 4 Choices/Scores.
    """
    answers = data["answers"]

    diff_type_answer = answers.get("diff_type", {})
    diff_type = diff_type_answer.get("choice", "feature_addition")
    if diff_type not in DIFF_TYPE_CRITERIA:
        diff_type = "feature_addition"

    scope_answer = answers.get("scope", {})
    scope = scope_answer.get("choice", scope_answer.get("score", "Small (6-50 lines)"))

    # Live Jev Score: ``score`` is a weighted mean of 0..len(RISK_CRITERIA)-1.
    # Keep the mean (risk_score), the bucket (risk_level), and the label (risk)
    # so downstream string consumers keep working.
    risk_answer = answers.get("risk", {})
    risk_score = risk_answer.get("score")
    risk_level = jev_router_common.score_level(risk_answer, len(RISK_CRITERIA))
    if risk_level is None:
        # Legacy label string or missing answer: match by equality, else lowest risk.
        legacy = risk_answer.get("choice", risk_score)
        risk_level = RISK_CRITERIA.index(legacy) if legacy in RISK_CRITERIA else 0
        risk_score = None if isinstance(risk_score, (str, bool)) else risk_score
    risk = RISK_CRITERIA[risk_level]

    language_answer = answers.get("language", {})
    language = language_answer.get("choice", "other")
    if language not in LANGUAGE_CRITERIA:
        language = "other"

    # v2: parse structural Noul signals.
    risk_signals: dict[str, float] = {}
    for key in _V2_STAGE1_NOULS:
        answer = answers.get(key, {})
        risk_signals[key] = round(float(answer.get("noul", 0.0)), 3)

    return {
        "type": diff_type,
        "scope": scope,
        "risk": risk,
        "risk_score": risk_score,
        "risk_level": risk_level,
        "language": language,
        "risk_signals": risk_signals,
    }


def _build_stage2_payload(diff_text: str, classification: dict) -> dict:
    """Build Stage 2 Jev payload: domain checks selected by Stage 1 classification.

    Questions include:
    - Domain-specific Nouls chosen by diff_type (e.g., has_tests for features).
    - Universal Nouls (has_slop, has_pointless_comments) for all types.
    - naming_quality Score for all types.

    Instructions include Stage 1 classification as context.
    """
    diff_type = classification["type"]
    context_prefix = (
        f"This diff was classified as: type={diff_type}, scope={classification['scope']}, "
        f"risk={classification['risk']}, language={classification['language']}. "
    )

    questions: dict[str, dict] = {}

    domain_checks = DOMAIN_CHECK_MAP.get(diff_type, {})
    for key, definition in domain_checks.items():
        scoped = dict(definition)
        scoped["instructions"] = context_prefix + definition["instructions"]
        questions[key] = scoped

    # Universal checks (always asked).
    for key, definition in UNIVERSAL_CHECKS.items():
        scoped = dict(definition)
        scoped["instructions"] = context_prefix + definition["instructions"]
        questions[key] = scoped

    # Naming quality score (always asked).
    questions["naming_quality"] = {
        "type": "score",
        "instructions": context_prefix + "Rate the quality of variable, function, and class names in this diff.",
        "criteria": NAMING_QUALITY_CRITERIA,
    }

    return {"state": diff_text, "model": jev_router_common.JEV_MODEL, "questions": questions}


def _parse_stage2(data: dict, classification: dict, threshold: float) -> list[dict]:
    """Parse Stage 2 answers into a list of finding dicts.

    Each finding: {check, score, flagged, description}.
    """
    answers = data["answers"]
    diff_type = classification["type"]
    findings: list[dict] = []

    domain_checks = DOMAIN_CHECK_MAP.get(diff_type, {})
    check_descriptions = _check_descriptions()

    for key in domain_checks:
        answer = answers.get(key, {})
        score = float(answer.get("noul", 0.0))
        # For checks where True means "good" (has_tests, has_error_handling,
        # is_backward_compatible, follows_patterns, has_regression_test,
        # root_cause_addressed, behavior_preserved, improves_readability,
        # reduces_complexity), flagging means the score is LOW (absence of
        # the good property). For checks where True means "bad" (side_effects,
        # has_secrets, env_specific), flagging means the score is HIGH.
        is_positive_check = key not in {"side_effects", "has_secrets", "env_specific"}
        if is_positive_check:
            flagged = score < (1.0 - threshold)
        else:
            flagged = score >= threshold
        findings.append(
            {
                "check": key,
                "score": round(score, 3),
                "flagged": flagged,
                "description": check_descriptions.get(key, key),
            }
        )

    # Universal Noul results (True = bad -> flag on high score).
    for key in UNIVERSAL_CHECKS:
        answer = answers.get(key, {})
        score = float(answer.get("noul", 0.0))
        flagged = score >= threshold
        findings.append(
            {
                "check": key,
                "score": round(score, 3),
                "flagged": flagged,
                "description": check_descriptions.get(key, key),
            }
        )

    naming_answer = answers.get("naming_quality", {})
    naming_level = _naming_level(naming_answer)
    naming_label = NAMING_QUALITY_CRITERIA[naming_level] if naming_level is not None else "Acceptable"
    # NAMING_QUALITY_CRITERIA runs Poor -> Excellent, so flag at or below the "poor" level.
    naming_flagged = naming_level is not None and naming_level <= _NAMING_POOR_LEVEL
    findings.append(
        {
            "check": "naming_quality",
            "score": naming_answer.get("score", naming_label),
            "level": naming_level,
            "label": naming_label,
            "flagged": naming_flagged,
            "description": "Variable and function naming quality",
        }
    )

    return findings


def _naming_level(naming_answer: dict) -> int | None:
    """Bucket the naming_quality Score answer; accept a legacy label string."""
    level = jev_router_common.score_level(naming_answer, len(NAMING_QUALITY_CRITERIA))
    if level is not None:
        return level
    legacy = naming_answer.get("choice", naming_answer.get("score"))
    if isinstance(legacy, str):
        for idx, label in enumerate(NAMING_QUALITY_CRITERIA):
            if label == legacy or label.lower().startswith(legacy.lower()):
                return idx
    return None


def _check_descriptions() -> dict[str, str]:
    """Human-readable descriptions for each check key."""
    return {
        # Feature checks
        "has_tests": "No tests for new feature",
        "has_error_handling": "No error handling for failure cases",
        "is_backward_compatible": "Breaking change to existing API",
        "follows_patterns": "Does not follow codebase patterns",
        # Bug fix checks
        "has_regression_test": "No regression test for the bug fix",
        "root_cause_addressed": "Fix addresses symptom, not root cause",
        "side_effects": "Fix may introduce side effects",
        # Refactor checks
        "behavior_preserved": "Refactor may have changed behavior",
        "improves_readability": "Refactor does not improve readability",
        "reduces_complexity": "Refactor does not reduce complexity",
        # Config checks
        "has_secrets": "Config change exposes secrets",
        "env_specific": "Config is environment-specific",
        # Universal checks
        "has_slop": "AI-generated boilerplate detected",
        "has_pointless_comments": "Pointless comments that restate code",
        # Naming
        "naming_quality": "Variable and function naming quality",
    }


_VERIFICATION_SEVERITY_CRITERIA = [
    "Cosmetic -- style only, no functional impact",
    "Minor -- low-impact improvement, not a bug",
    "Moderate -- real issue but unlikely to cause outage",
    "Major -- could cause incorrect behavior in production",
    "Critical -- data loss, security vulnerability, or service outage risk",
]


def _build_stage3_payload(diff_text: str, flagged_findings: list[dict]) -> dict:
    """Build Stage 3 Jev payload: adversarial verification of flagged findings.

    v2: for each flagged finding, ask 4 questions:
    - finding_N_real (Noul): is it genuine or a false positive?
    - finding_N_has_repro (Noul): can you describe a concrete input/state that triggers it?
    - finding_N_fix_straightforward (Noul): is the fix obvious and low-effort?
    - finding_N_severity (Score): how bad is this if it ships?
    """
    findings_context = json.dumps(flagged_findings, indent=2)
    state = f"[DIFF]\n{diff_text}\n\n[FINDINGS FROM PREVIOUS ANALYSIS]\n{findings_context}"

    questions: dict[str, dict] = {}
    for i, finding in enumerate(flagged_findings):
        check = finding["check"]
        desc = finding["description"]
        score = finding["score"]
        finding_label = f"Finding: {check} -- {desc} (score: {score})"

        questions[f"finding_{i}_real"] = {
            "type": "noul",
            "instructions": (
                f"Given this diff and this finding, is it a genuine issue or a false positive? "
                f"{finding_label}. "
                f"True only when the finding reflects a real problem in this specific code. "
                f"False when the finding is a false positive, overly strict, or does not apply here."
            ),
            "criteria": {
                "true": {
                    "what": "Finding describes a real problem in this diff",
                    "examples": [
                        "The diff adds a public function with no error handling, and has_error_handling flagged it",
                        "The diff changes auth logic, and has_security_surface flagged it correctly",
                    ],
                    "not_for": (
                        "Findings triggered by pattern matching that do not apply to this specific context. "
                        "Example: has_tests flags a config-only change where no tests are expected."
                    ),
                },
                "false": {
                    "what": "Finding is a false positive or does not apply",
                    "examples": [
                        "has_tests flagged a documentation-only PR",
                        "side_effects flagged a change to a pure function",
                    ],
                },
            },
        }

        questions[f"finding_{i}_has_repro"] = {
            "type": "noul",
            "instructions": (
                f"Can you describe a concrete input, state, or sequence that would trigger this issue? "
                f"{finding_label}. "
                f"True when there is a reproducible scenario. False when the issue is theoretical or vague."
            ),
            "criteria": {
                "true": {
                    "what": "A concrete reproduction path exists",
                    "examples": [
                        "Calling the function with None as the first argument would raise TypeError",
                        "A concurrent request during the write window would see stale data",
                    ],
                },
                "false": {
                    "what": "No concrete reproduction scenario",
                    "examples": [
                        "General concern about error handling without a specific trigger",
                        "Style preference with no behavioral consequence",
                    ],
                },
            },
        }

        questions[f"finding_{i}_fix_straightforward"] = {
            "type": "noul",
            "instructions": (
                f"Is the fix for this finding obvious, low-risk, and low-effort? "
                f"{finding_label}. "
                f"True when a one-line or small-scope fix resolves it. "
                f"False when fixing it requires significant redesign or has knock-on effects."
            ),
            "criteria": {
                "true": {
                    "what": "Fix is obvious and small",
                    "examples": [
                        "Add a None check on one line",
                        "Add a missing test case",
                        "Rename a variable for clarity",
                    ],
                },
                "false": {
                    "what": "Fix requires significant change",
                    "examples": [
                        "Redesign the concurrency model",
                        "Refactor the data flow to avoid the race condition",
                        "Add a migration and backfill",
                    ],
                },
            },
        }

        questions[f"finding_{i}_severity"] = {
            "type": "score",
            "instructions": (f"Rate the severity of this finding if it ships to production. {finding_label}."),
            "criteria": _VERIFICATION_SEVERITY_CRITERIA,
        }

    return {"state": state, "model": jev_router_common.JEV_MODEL, "questions": questions}


def _parse_stage3(data: dict, flagged_findings: list[dict]) -> list[dict]:
    """Parse Stage 3 answers into verified finding dicts.

    v2: each finding gets 4 signals: is_real, has_repro, fix_straightforward, severity.
    """
    answers = data["answers"]
    verified: list[dict] = []

    for i, finding in enumerate(flagged_findings):
        real_answer = answers.get(f"finding_{i}_real", {})
        confidence = float(real_answer.get("noul", 0.0))
        is_real = confidence >= 0.5

        repro_answer = answers.get(f"finding_{i}_has_repro", {})
        has_repro = float(repro_answer.get("noul", 0.0)) >= 0.5

        fix_answer = answers.get(f"finding_{i}_fix_straightforward", {})
        fix_straightforward = float(fix_answer.get("noul", 0.0)) >= 0.5

        severity_answer = answers.get(f"finding_{i}_severity", {})
        severity = severity_answer.get("choice") or severity_answer.get(
            "score", "Minor -- low-impact improvement, not a bug"
        )

        result: dict = {
            "check": finding["check"],
            "verified": is_real,
            "confidence": round(confidence, 3),
            "has_repro": has_repro,
            "fix_straightforward": fix_straightforward,
            "severity": severity,
        }
        if not is_real:
            result["reason"] = "false_positive"
        verified.append(result)

    return verified


def _split_diff_by_file(diff_text: str) -> list[tuple[str, str]]:
    """Split a unified diff into per-file chunks.

    Returns a list of (filename, file_diff_text) tuples. Each file_diff_text
    is a self-contained unified diff fragment starting with "diff --git".
    """
    chunks: list[tuple[str, str]] = []
    current_lines: list[str] = []
    current_file: str | None = None

    for line in diff_text.splitlines(keepends=True):
        if line.startswith("diff --git "):
            if current_file is not None and current_lines:
                chunks.append((current_file, "".join(current_lines)))
            current_lines = [line]
            parts = line.rstrip().split(" b/", 1)
            current_file = parts[1] if len(parts) == 2 else "unknown"
        else:
            current_lines.append(line)

    if current_file is not None and current_lines:
        chunks.append((current_file, "".join(current_lines)))

    return chunks


def _count_diff_files(diff_text: str) -> int:
    """Count files in a unified diff without full parsing."""
    return diff_text.count("\ndiff --git ") + (1 if diff_text.startswith("diff --git ") else 0)


def _diff_exceeds_threshold(diff_text: str) -> bool:
    """True when the diff is large enough to warrant per-file splitting."""
    if len(diff_text) > LARGE_DIFF_CHAR_THRESHOLD:
        return True
    return _count_diff_files(diff_text) > LARGE_DIFF_FILE_THRESHOLD


def _aggregate_cascade_results(per_file_results: list[dict]) -> dict:
    """Merge per-file cascade_review results into one aggregate result.

    Takes the broadest classification (highest risk), merges findings and
    verified_findings, sums latency and jev_calls.
    """
    if not per_file_results:
        return {
            "classification": None,
            "findings": [],
            "verified_findings": [],
            "stages": 0,
            "jev_calls": 0,
            "latency_ms": {"stage1": 0, "stage2": 0, "stage3": 0, "total": 0},
        }

    best_classification: dict | None = None
    best_risk_rank = -1
    all_findings: list[dict] = []
    all_verified: list[dict] = []
    errors: list[str] = []
    total_jev_calls = 0
    total_latency: dict[str, float] = {"stage1": 0, "stage2": 0, "stage3": 0}
    max_stages = 0

    for result in per_file_results:
        if result.get("error"):
            # A failed file still spent Jev calls; count them and surface the error.
            total_jev_calls += result.get("jev_calls", 0)
            errors.append(str(result["error"]))
            continue

        classification = result.get("classification")
        if classification:
            rank = _classification_risk_level(classification)
            if rank > best_risk_rank:
                best_risk_rank = rank
                best_classification = classification

        all_findings.extend(result.get("findings", []))
        all_verified.extend(result.get("verified_findings", []))
        total_jev_calls += result.get("jev_calls", 0)

        lat = result.get("latency_ms", {})
        total_latency["stage1"] += lat.get("stage1", 0)
        total_latency["stage2"] += lat.get("stage2", 0)
        total_latency["stage3"] += lat.get("stage3", 0)

        max_stages = max(max_stages, result.get("stages", 0))

    total_latency["total"] = round(sum(v for k, v in total_latency.items() if k != "total"), 1)
    for k in ("stage1", "stage2", "stage3"):
        total_latency[k] = round(total_latency[k], 1)

    aggregate: dict = {
        "classification": best_classification,
        "findings": all_findings,
        "verified_findings": all_verified,
        "stages": max_stages,
        "jev_calls": total_jev_calls,
        "latency_ms": total_latency,
    }
    if errors:
        aggregate["errors"] = errors
    return aggregate


def _classification_risk_level(classification: dict) -> int:
    """Risk rank for one classification: ``risk_level`` first, label fallback, -1 unknown."""
    level = classification.get("risk_level")
    if isinstance(level, int) and not isinstance(level, bool):
        return level
    risk_str = classification.get("risk", "")
    return RISK_CRITERIA.index(risk_str) if risk_str in RISK_CRITERIA else -1


def _cascade_review_single(
    diff_text: str,
    *,
    threshold: float = DEFAULT_THRESHOLD,
    timeout: float = DEFAULT_TIMEOUT,
) -> dict:
    """Run the three-stage cascade on a single diff chunk (no splitting).

    Internal workhorse called by cascade_review(). Same return format.
    """
    api_key = os.environ.get("TYPESAFE_API_KEY", "").strip()
    latency: dict[str, float] = {"stage1": 0, "stage2": 0, "stage3": 0}
    jev_calls = 0

    try:
        stage1_payload = _build_stage1_payload(diff_text)
        data1, latency1 = jev_router_common.call_jev(
            stage1_payload, api_key, timeout, script_name="jev-cascade-review.py"
        )
        latency["stage1"] = round(latency1, 1)
        jev_calls += 1
        classification = _parse_stage1(data1)
    except Exception as exc:
        print(f"[cascade-review] stage 1 failed: {type(exc).__name__}: {exc}", file=sys.stderr)
        return {
            "error": f"stage 1 failed: {type(exc).__name__}: {str(exc)[:200]}",
            "classification": None,
            "findings": [],
            "verified_findings": [],
            "stages": 0,
            "jev_calls": jev_calls,
            "latency_ms": {**latency, "total": sum(latency.values())},
        }

    try:
        stage2_payload = _build_stage2_payload(diff_text, classification)
        data2, latency2 = jev_router_common.call_jev(
            stage2_payload, api_key, timeout, script_name="jev-cascade-review.py"
        )
        latency["stage2"] = round(latency2, 1)
        jev_calls += 1
        findings = _parse_stage2(data2, classification, threshold)
    except Exception as exc:
        print(f"[cascade-review] stage 2 failed: {type(exc).__name__}: {exc}", file=sys.stderr)
        return {
            "error": f"stage 2 failed: {type(exc).__name__}: {str(exc)[:200]}",
            "classification": classification,
            "findings": [],
            "verified_findings": [],
            "stages": 1,
            "jev_calls": jev_calls,
            "latency_ms": {**latency, "total": sum(latency.values())},
        }

    flagged = [f for f in findings if f.get("flagged")]
    verified_findings: list[dict] = []
    stages = 2

    if flagged:
        try:
            stage3_payload = _build_stage3_payload(diff_text, flagged)
            data3, latency3 = jev_router_common.call_jev(
                stage3_payload, api_key, timeout, script_name="jev-cascade-review.py"
            )
            latency["stage3"] = round(latency3, 1)
            jev_calls += 1
            verified_findings = _parse_stage3(data3, flagged)
            stages = 3
        except Exception as exc:
            print(f"[cascade-review] stage 3 failed: {type(exc).__name__}: {exc}", file=sys.stderr)
            # Stage 3 failure is non-fatal: findings stand unverified.
            verified_findings = [
                {
                    "check": f["check"],
                    "verified": False,
                    "confidence": 0.0,
                    "has_repro": False,
                    "fix_straightforward": True,
                    "severity": "Minor -- low-impact improvement, not a bug",
                    "reason": "verification_failed",
                }
                for f in flagged
            ]
            stages = 3

    latency["total"] = round(sum(latency.values()), 1)

    return {
        "classification": classification,
        "findings": findings,
        "verified_findings": verified_findings,
        "stages": stages,
        "jev_calls": jev_calls,
        "latency_ms": latency,
    }


def cascade_review(
    diff_text: str,
    *,
    threshold: float = DEFAULT_THRESHOLD,
    timeout: float = DEFAULT_TIMEOUT,
) -> dict:
    """Run the three-stage cascade review on a unified diff.

    For large diffs (over ~8000 chars or 20 files), automatically splits
    into per-file chunks and runs the cascade on each file separately,
    then aggregates findings. Small diffs run the cascade on the full
    diff in a single pass.

    Args:
        diff_text: Unified diff text to review.
        threshold: Noul score threshold for flagging findings.
        timeout: Jev HTTP call timeout in seconds per stage.

    Returns:
        Dict with classification, findings, verified_findings, stages,
        jev_calls, and latency_ms.
    """
    available, reason = jev_router_common.typesafe_available()
    if not available:
        return {
            "error": f"TypeSafe unavailable: {reason}",
            "classification": None,
            "findings": [],
            "verified_findings": [],
            "stages": 0,
            "jev_calls": 0,
            "latency_ms": {"stage1": 0, "stage2": 0, "stage3": 0, "total": 0},
        }

    if not diff_text or not diff_text.strip():
        return {
            "classification": None,
            "findings": [],
            "verified_findings": [],
            "stages": 0,
            "jev_calls": 0,
            "latency_ms": {"stage1": 0, "stage2": 0, "stage3": 0, "total": 0},
        }

    if not _diff_exceeds_threshold(diff_text):
        return _cascade_review_single(diff_text, threshold=threshold, timeout=timeout)

    # Large diff: split into per-file chunks and run each independently.
    file_chunks = _split_diff_by_file(diff_text)
    if not file_chunks:
        return _cascade_review_single(diff_text, threshold=threshold, timeout=timeout)

    print(
        f"[cascade-review] large diff ({len(diff_text)} chars, {len(file_chunks)} files), splitting per file",
        file=sys.stderr,
    )

    per_file_results: list[dict] = []
    for filename, file_diff in file_chunks:
        result = _cascade_review_single(file_diff, threshold=threshold, timeout=timeout)
        # Tag findings with their source file for traceability.
        for finding in result.get("findings", []):
            finding.setdefault("file", filename)
        for verified in result.get("verified_findings", []):
            verified.setdefault("file", filename)
        per_file_results.append(result)

    return _aggregate_cascade_results(per_file_results)


def _format_summary(result: dict) -> str:
    """Format cascade review result as a human-readable summary."""
    lines: list[str] = []

    if "error" in result:
        lines.append(f"Error: {result['error']}")
        return "\n".join(lines)

    classification = result.get("classification")
    if not classification:
        lines.append("No diff to review.")
        return "\n".join(lines)

    lines.append("=" * 60)
    lines.append("  CASCADE CODE REVIEW")
    lines.append("=" * 60)
    lines.append(f"  Type:      {classification['type']}")
    lines.append(f"  Scope:     {classification['scope']}")
    lines.append(f"  Risk:      {classification['risk']}")
    lines.append(f"  Language:  {classification['language']}")
    lines.append(f"  Stages:    {result['stages']}")
    lines.append(f"  Jev calls: {result['jev_calls']}")
    lat = result.get("latency_ms", {})
    lines.append(
        f"  Latency:   {lat.get('total', 0)}ms (s1:{lat.get('stage1', 0)} s2:{lat.get('stage2', 0)} s3:{lat.get('stage3', 0)})"
    )

    findings = result.get("findings", [])
    flagged = [f for f in findings if f.get("flagged")]
    lines.append(f"\n  Findings:  {len(findings)} checks, {len(flagged)} flagged")

    if flagged:
        lines.append("")
        lines.append("  FLAGGED:")
        for f in flagged:
            lines.append(f"    {f['check']:<30s} score={f['score']:<8} {f['description']}")

    verified = result.get("verified_findings", [])
    if verified:
        confirmed = [v for v in verified if v.get("verified")]
        unverified = [v for v in verified if not v.get("verified") and v.get("reason") == "verification_failed"]
        dismissed = [v for v in verified if not v.get("verified") and v.get("reason") != "verification_failed"]
        lines.append("")
        lines.append(f"  VERIFIED: {len(confirmed)} confirmed, {len(dismissed)} dismissed as false positives")
        if unverified:
            lines.append(f"  UNVERIFIED (stage 3 failed): {len(unverified)} findings stand unconfirmed")
        for v in unverified:
            lines.append(f"    [UNVERIFIED] {v['check']:<25s}")
        for v in confirmed:
            sev = v.get("severity", "?")
            if isinstance(sev, str) and " -- " in sev:
                sev = sev.split(" -- ")[0]
            repro = "repro" if v.get("has_repro") else "no-repro"
            fix = "easy-fix" if v.get("fix_straightforward") else "complex-fix"
            lines.append(
                f"    [CONFIRMED] {v['check']:<25s} confidence={v['confidence']:.2f} severity={sev} {repro} {fix}"
            )
        for v in dismissed:
            lines.append(f"    [DISMISSED] {v['check']:<25s} confidence={v['confidence']:.2f}")

    lines.append("=" * 60)
    return "\n".join(lines)


def _read_diff(args: argparse.Namespace) -> str:
    """Read diff text from the source specified by CLI args."""
    if args.diff_file:
        return Path(args.diff_file).read_text(encoding="utf-8")
    if args.pr is not None:
        proc = subprocess.run(
            ["gh", "pr", "diff", str(args.pr)],
            capture_output=True,
            text=True,
            timeout=30,
            check=False,
        )
        if proc.returncode != 0:
            print(f"[cascade-review] gh pr diff failed: {proc.stderr.strip()[:200]}", file=sys.stderr)
            return ""
        return proc.stdout
    if sys.stdin.isatty():
        print("[cascade-review] reading diff from stdin (pipe a diff or use --diff-file / --pr)", file=sys.stderr)
    return sys.stdin.read()


def main() -> int:
    """CLI entry point."""
    parser = argparse.ArgumentParser(
        description="Multi-stage Jev cascade review for code diffs.",
    )
    input_group = parser.add_mutually_exclusive_group()
    input_group.add_argument("--diff-file", help="Path to a unified diff file.")
    input_group.add_argument("--pr", type=int, help="GitHub PR number (runs gh pr diff).")
    parser.add_argument(
        "--threshold",
        type=float,
        default=DEFAULT_THRESHOLD,
        help=f"Noul score threshold for flagging findings (default {DEFAULT_THRESHOLD}).",
    )
    parser.add_argument(
        "--timeout",
        type=float,
        default=DEFAULT_TIMEOUT,
        help=f"Jev HTTP call timeout in seconds per stage (default {DEFAULT_TIMEOUT}).",
    )
    parser.add_argument("--json-compact", action="store_true", help="Output compact JSON (no indentation).")
    parser.add_argument("--summary", action="store_true", help="Print human-readable summary instead of JSON.")
    parser.add_argument("--verbose", action="store_true", help="Print stage progress to stderr.")
    args = parser.parse_args()

    try:
        diff_text = _read_diff(args)

        if args.verbose:
            print("[cascade-review] starting cascade review...", file=sys.stderr)

        result = cascade_review(diff_text, threshold=args.threshold, timeout=args.timeout)

        if args.verbose:
            print(
                f"[cascade-review] done: {result.get('stages', 0)} stages, {result.get('jev_calls', 0)} jev calls",
                file=sys.stderr,
            )
    except Exception as exc:
        import traceback

        traceback.print_exc(file=sys.stderr)
        result = {
            "error": f"{type(exc).__name__}: {str(exc)[:200]}",
            "classification": None,
            "findings": [],
            "verified_findings": [],
            "stages": 0,
            "jev_calls": 0,
            "latency_ms": {"stage1": 0, "stage2": 0, "stage3": 0, "total": 0},
        }

    if args.summary:
        print(_format_summary(result))
    else:
        indent = None if args.json_compact else 2
        print(json.dumps(result, indent=indent))
    return 0


if __name__ == "__main__":
    sys.exit(main())
