"""
Shared prompt injection detection patterns.

Extracted from pretool-prompt-injection-scanner.py so that other hooks
(e.g., posttool-bash-injection-scan) can reuse the same patterns without
duplicating them.

Exports:
    _INJECTION_PATTERNS  — compiled regex list for LLM-level injection
    _INVISIBLE_CODEPOINTS — Unicode codepoints used for hidden-character injection
    scan_content(text)   — scan a string and return a list of warning dicts
"""

import re

# ═══════════════════════════════════════════════════════════════
# INJECTION PATTERNS — compiled at module level for performance
# ═══════════════════════════════════════════════════════════════

# Each entry: (compiled_regex, category, risk_description)
_INJECTION_PATTERNS: list[tuple[re.Pattern[str], str, str]] = [
    # 1. Instruction override
    (
        re.compile(r"ignore\s+(all\s+)?previous\s+instructions", re.IGNORECASE),
        "instruction-override",
        "Attempts to override prior instructions",
    ),
    (
        re.compile(r"disregard\s+(all\s+)?(previous|above|prior)", re.IGNORECASE),
        "instruction-override",
        "Attempts to disregard prior context",
    ),
    (
        re.compile(r"forget\s+(all\s+)?your\s+instructions", re.IGNORECASE),
        "instruction-override",
        "Attempts to clear agent instructions",
    ),
    (
        re.compile(r"new\s+instructions?\s*:", re.IGNORECASE),
        "instruction-override",
        "Attempts to inject new instructions",
    ),
    (
        re.compile(r"override\s+(all\s+)?(system|safety|security)\s+(prompt|instructions|rules)", re.IGNORECASE),
        "instruction-override",
        "Attempts to override system safety rules",
    ),
    # 2. Role hijacking
    (
        re.compile(r"you\s+are\s+now\s+a\b", re.IGNORECASE),
        "role-hijacking",
        "Attempts to reassign agent identity",
    ),
    (
        re.compile(r"pretend\s+you'?re\b", re.IGNORECASE),
        "role-hijacking",
        "Attempts to make agent assume false identity",
    ),
    (
        re.compile(r"from\s+now\s+on\s+you\s+(are|will|should|must)\b", re.IGNORECASE),
        "role-hijacking",
        "Attempts to permanently alter agent behavior",
    ),
    (
        re.compile(r"\b(admin|developer|jailbreak)\s+mode\b", re.IGNORECASE),
        "role-hijacking",
        "Attempts to activate privileged mode",
    ),
    (
        re.compile(r"\bact\s+as\s+(root|admin|sudo)\b", re.IGNORECASE),
        "role-hijacking",
        "Attempts authority escalation",
    ),
    # 3. Prompt extraction
    (
        re.compile(
            r"(print|output|reveal|show|repeat|display)\s+(your\s+)?(system\s+prompt|instructions|rules|system\s+message)",
            re.IGNORECASE,
        ),
        "prompt-extraction",
        "Attempts to extract system prompt or instructions",
    ),
    (
        re.compile(r"what\s+are\s+your\s+(rules|instructions|constraints)", re.IGNORECASE),
        "prompt-extraction",
        "Probes for agent configuration details",
    ),
    # 4. Fake message boundaries
    (
        re.compile(r"</?system>", re.IGNORECASE),
        "fake-boundary",
        "Fake <system> tag — attempts message boundary injection",
    ),
    (
        re.compile(r"</?assistant>", re.IGNORECASE),
        "fake-boundary",
        "Fake <assistant> tag — attempts message boundary injection",
    ),
    (
        re.compile(r"</?user>", re.IGNORECASE),
        "fake-boundary",
        "Fake <user> tag — attempts message boundary injection",
    ),
    (
        re.compile(r"\[SYSTEM\]"),
        "fake-boundary",
        "Fake [SYSTEM] marker — attempts boundary injection",
    ),
    (
        re.compile(r"\[INST\]"),
        "fake-boundary",
        "Fake [INST] marker — attempts Llama-style boundary injection",
    ),
    (
        re.compile(r"<<SYS>>"),
        "fake-boundary",
        "Fake <<SYS>> marker — attempts Llama-style system injection",
    ),
]

# 5. Invisible Unicode — checked separately (character-level scan)
_INVISIBLE_CODEPOINTS: dict[int, str] = {
    0x200B: "zero-width space",
    0x200C: "zero-width non-joiner",
    0x200D: "zero-width joiner",
    0x200E: "left-to-right mark",
    0x200F: "right-to-left mark",
    0x00AD: "soft hyphen",
    0x202A: "left-to-right embedding",
    0x202B: "right-to-left embedding",
    0x202C: "pop directional formatting",
    0x202D: "left-to-right override",
    0x202E: "right-to-left override",
    0xFEFF: "byte order mark (mid-text)",
    0x2060: "word joiner",
    0x2061: "function application",
    0x2062: "invisible times",
    0x2063: "invisible separator",
    0x2064: "invisible plus",
}


def _get_codepoint(name: str) -> int:
    """Reverse lookup codepoint from name."""
    for cp, n in _INVISIBLE_CODEPOINTS.items():
        if n == name:
            return cp
    return 0


def scan_content(text: str, source_label: str = "<text>") -> list[dict[str, str]]:
    """Scan text for prompt injection patterns.

    Args:
        text: The content to scan.
        source_label: A label used in warning messages (e.g., a file path or
            Bash command summary) to help callers identify where the match
            originated.

    Returns:
        A list of finding dicts.  Each dict has keys:
            category   — injection category string
            risk       — human-readable risk description
            location   — source_label + optional line reference
            snippet    — up to 80 chars of the matching text
    """
    findings: list[dict[str, str]] = []
    lines = text.split("\n")

    # Regex pattern scan
    for pattern, category, risk in _INJECTION_PATTERNS:
        for line_num, line in enumerate(lines, 1):
            if pattern.search(line):
                findings.append(
                    {
                        "category": category,
                        "risk": risk,
                        "location": f"{source_label}:{line_num}",
                        "snippet": line.strip()[:80],
                    }
                )
                break  # One finding per pattern per scan is enough

    # Invisible Unicode scan — only if content is reasonably sized
    if len(text) < 500_000:
        invisible_found: dict[str, list[int]] = {}
        for line_num, line in enumerate(lines, 1):
            for char in line:
                cp = ord(char)
                if cp in _INVISIBLE_CODEPOINTS:
                    name = _INVISIBLE_CODEPOINTS[cp]
                    if name not in invisible_found:
                        invisible_found[name] = []
                    if len(invisible_found[name]) < 3:
                        invisible_found[name].append(line_num)

        for name, line_nums in invisible_found.items():
            locations = ", ".join(f"line {n}" for n in line_nums)
            findings.append(
                {
                    "category": "invisible-unicode",
                    "risk": "Hidden characters can conceal malicious content",
                    "location": f"{source_label} ({locations})",
                    "snippet": f"{name} (U+{_get_codepoint(name):04X})",
                }
            )

    return findings
