"""Security tests for the deterministic GitHub issues renderer."""

from __future__ import annotations

import importlib.util
from pathlib import Path

SCRIPT = Path(__file__).parent.parent / "render-github-issues.py"
SPEC = importlib.util.spec_from_file_location("html_artifact_render_github_issues", SCRIPT)
assert SPEC and SPEC.loader
MODULE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(MODULE)


def test_text_placeholders_cannot_inject_markup() -> None:
    rendered = MODULE.render(
        [],
        '</title><script>alert("title")</script><title>',
        '<img src=x onerror="alert(1)">',
    )

    assert "</title><script>" not in rendered
    assert '<img src=x onerror="alert(1)">' not in rendered
    assert "&lt;/title&gt;&lt;script&gt;alert(&quot;title&quot;)&lt;/script&gt;&lt;title&gt;" in rendered
    assert "&lt;img src=x onerror=&quot;alert(1)&quot;&gt;" in rendered
