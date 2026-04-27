"""Tests for check-skill-verdicts.py.

Covers happy path (every pattern carries KEEP/FOOTNOTE), missing verdict,
DROP leaked into shipped file, mixed KEEP+FOOTNOTE, and false-positive
guards (H3 outside a recognized parent H2).
"""

from __future__ import annotations

import importlib.util
import sys
import unittest
from pathlib import Path
from tempfile import TemporaryDirectory

# Load the hyphenated script as a module via importlib.
SCRIPT_PATH = Path(__file__).resolve().parent / "check-skill-verdicts.py"
_spec = importlib.util.spec_from_file_location("check_skill_verdicts", SCRIPT_PATH)
assert _spec is not None and _spec.loader is not None
checker = importlib.util.module_from_spec(_spec)
sys.modules["check_skill_verdicts"] = checker
_spec.loader.exec_module(checker)


# ---- Synthetic SKILL.md fixtures -------------------------------------------

HAPPY_PATH = """---
name: voice-test
---

# Voice: Test

## Mental Models

### M1: Mechanism-first

Body text describing the model.

**Verdict**: KEEP

### M2: Hand-worked example

Body text.

**Verdict**: KEEP

## Heuristics

### H1: Refuse jargon

**Verdict**: KEEP

## Phrase Fingerprints

### P1: "That's all there is to it." (KEEP)

Inline tag form is also accepted.
"""


MIXED_KEEP_FOOTNOTE = """---
name: voice-mixed
---

## Mental Models

### M1: Strong pattern

**Verdict**: KEEP

### M2: Scoped pattern

Only applies in long-form mode.

**Verdict**: FOOTNOTE
"""


MISSING_VERDICT = """---
name: voice-missing
---

## Mental Models

### M1: Has a verdict

**Verdict**: KEEP

### M2: Forgot the verdict

This block has body text but nobody wrote a verdict line.
"""


DROP_LEAKED = """---
name: voice-drop-leak
---

## Heuristics

### H1: Should not have shipped

**Verdict**: DROP
"""


FALSE_POSITIVE_GUARD = """---
name: skill-with-other-h3
---

## Operator Context

### Hardcoded behaviors

This is an H3 outside a recognized pattern parent. It must NOT require a
verdict, otherwise the check fires on routine skill structure.

## Workflow

### Phase 1: Gather

Same -- this is a phase, not a pattern. No verdict required.

## Mental Models

### M1: Real pattern

**Verdict**: KEEP
"""


INLINE_DROP_TAG = """---
name: voice-inline-drop
---

## Phrase Fingerprints

### P1: Em-dashes (DROP)

Inline DROP tag should still fail the gate.
"""


PARENT_BLANKET = """---
name: voice-blanket
---

## Mental Models (KEEP-verdict)

### M1: Mechanism-first

Body text without an explicit verdict line; the parent H2 declares the
blanket KEEP-verdict so this counts as KEEP.

### M2: Hand-worked example

Same -- inherits KEEP from the parent.

## Phrase Fingerprints (FOOTNOTE-verdict, scoped use only)

### P1: "y'know" / "see"

Inherits FOOTNOTE from the parent blanket.
"""


PARENT_BLANKET_OVERRIDE = """---
name: voice-blanket-override
---

## Mental Models (KEEP-verdict)

### M1: Inherits KEEP

Body text.

### M2: Explicit DROP override

The body says DROP even though the parent declares KEEP -- the per-block
verdict must win, so the gate must fail.

**Verdict**: DROP
"""


# ---- Helpers ---------------------------------------------------------------


class CheckSkillVerdictsTests(unittest.TestCase):
    def setUp(self) -> None:
        self._tmp = TemporaryDirectory()
        self.tmp_path = Path(self._tmp.name)

    def tearDown(self) -> None:
        self._tmp.cleanup()

    def _write(self, name: str, body: str) -> Path:
        path = self.tmp_path / name
        path.write_text(body, encoding="utf-8")
        return path

    def _run(self, path: Path, *extra: str) -> int:
        return checker.main([str(path), *extra])

    # ---- Happy path -------------------------------------------------------

    def test_happy_path_all_keep_exits_zero(self) -> None:
        path = self._write("happy.md", HAPPY_PATH)
        rc = self._run(path)
        self.assertEqual(rc, 0)

    def test_mixed_keep_and_footnote_exits_zero(self) -> None:
        path = self._write("mixed.md", MIXED_KEEP_FOOTNOTE)
        rc = self._run(path)
        self.assertEqual(rc, 0)

    # ---- Failure cases ----------------------------------------------------

    def test_missing_verdict_exits_one_and_names_the_pattern(self) -> None:
        path = self._write("missing.md", MISSING_VERDICT)

        # Capture stderr by redirecting at the sys level.
        from io import StringIO

        buf = StringIO()
        old_stderr = sys.stderr
        sys.stderr = buf
        try:
            rc = self._run(path)
        finally:
            sys.stderr = old_stderr

        self.assertEqual(rc, 1)
        stderr_text = buf.getvalue()
        self.assertIn("M2: Forgot the verdict", stderr_text)
        self.assertIn("missing", stderr_text.lower())

    def test_drop_in_shipped_file_exits_one(self) -> None:
        path = self._write("drop.md", DROP_LEAKED)

        from io import StringIO

        buf = StringIO()
        old_stderr = sys.stderr
        sys.stderr = buf
        try:
            rc = self._run(path)
        finally:
            sys.stderr = old_stderr

        self.assertEqual(rc, 1)
        stderr_text = buf.getvalue()
        self.assertIn("H1: Should not have shipped", stderr_text)
        self.assertIn("DROP", stderr_text)

    def test_inline_drop_tag_in_heading_also_fails(self) -> None:
        path = self._write("inline-drop.md", INLINE_DROP_TAG)
        rc = self._run(path)
        self.assertEqual(rc, 1)

    # ---- Parent H2 blanket verdict ---------------------------------------

    def test_parent_h2_blanket_verdict_covers_children(self) -> None:
        """`## Mental Models (KEEP-verdict)` applies to its H3 children.

        This is the convention voice-feynman ships -- a single declaration on
        the parent rather than a verdict line per pattern.
        """
        path = self._write("blanket.md", PARENT_BLANKET)
        rc = self._run(path)
        self.assertEqual(rc, 0)

    def test_per_block_verdict_overrides_parent_blanket(self) -> None:
        """If a block declares its own verdict, the blanket does not apply."""
        path = self._write("override.md", PARENT_BLANKET_OVERRIDE)
        rc = self._run(path)
        self.assertEqual(rc, 1)

    # ---- False-positive guards -------------------------------------------

    def test_h3_outside_recognized_parent_does_not_require_verdict(self) -> None:
        path = self._write("guard.md", FALSE_POSITIVE_GUARD)
        rc = self._run(path)
        self.assertEqual(rc, 0)

    def test_no_pattern_blocks_at_all_exits_zero(self) -> None:
        path = self._write("empty.md", "# Just a title\n\n## Workflow\n\nNo H3 patterns.\n")
        rc = self._run(path)
        self.assertEqual(rc, 0)

    # ---- File-handling edge case -----------------------------------------

    def test_missing_file_exits_one(self) -> None:
        rc = self._run(self.tmp_path / "does-not-exist.md")
        self.assertEqual(rc, 1)

    # ---- JSON output ------------------------------------------------------

    def test_json_output_has_required_fields(self) -> None:
        path = self._write("json.md", HAPPY_PATH)

        from io import StringIO

        buf = StringIO()
        old_stdout = sys.stdout
        sys.stdout = buf
        try:
            rc = self._run(path, "--json")
        finally:
            sys.stdout = old_stdout

        self.assertEqual(rc, 0)
        import json as _json

        report = _json.loads(buf.getvalue())
        self.assertTrue(report["ok"])
        self.assertEqual(report["total_patterns"], 4)
        self.assertEqual(report["keep_or_footnote"], 4)


if __name__ == "__main__":
    unittest.main()
