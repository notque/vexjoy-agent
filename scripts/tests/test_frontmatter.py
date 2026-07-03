"""Tests for the shared frontmatter parser (scripts/lib/frontmatter.py)."""

from __future__ import annotations

from scripts.lib.frontmatter import extract_frontmatter_block, parse_frontmatter


class TestExtractFrontmatterBlock:
    def test_normal_frontmatter(self) -> None:
        text = "---\nname: foo\ndescription: bar\n---\n\n# Body\n"
        assert extract_frontmatter_block(text) == "name: foo\ndescription: bar"

    def test_missing_frontmatter(self) -> None:
        assert extract_frontmatter_block("# Just a heading\n") is None

    def test_empty_file(self) -> None:
        assert extract_frontmatter_block("") is None

    def test_unterminated_frontmatter(self) -> None:
        assert extract_frontmatter_block("---\nname: foo\n") is None


class TestParseFrontmatter:
    def test_normal_frontmatter(self) -> None:
        text = "---\nname: foo\ndescription: bar\n---\n\n# Body\ncontent here\n"
        fm, body = parse_frontmatter(text)
        assert fm == {"name": "foo", "description": "bar"}
        assert body == "\n# Body\ncontent here\n"

    def test_block_scalar_literal(self) -> None:
        text = "---\nname: foo\ndescription: |\n  Line one.\n  Line two.\n---\n# Body\n"
        fm, body = parse_frontmatter(text)
        assert fm is not None
        assert fm["name"] == "foo"
        assert fm["description"] == "Line one.\nLine two.\n"
        assert body == "# Body\n"

    def test_block_scalar_folded(self) -> None:
        text = "---\nname: foo\ndescription: >\n  This is a long\n  folded description.\n---\n# Body\n"
        fm, body = parse_frontmatter(text)
        assert fm is not None
        assert fm["description"] == "This is a long folded description.\n"

    def test_block_scalar_with_colons_in_description(self) -> None:
        """Block scalars can contain colons that would break naive line splitters."""
        text = "---\nname: foo\ndescription: |\n  Example: do X, then Y: Z.\n---\nbody\n"
        fm, _body = parse_frontmatter(text)
        assert fm is not None
        assert fm["description"] == "Example: do X, then Y: Z.\n"

    def test_missing_frontmatter(self) -> None:
        text = "# Just a heading\n\nSome content.\n"
        fm, body = parse_frontmatter(text)
        assert fm is None
        assert body == text

    def test_empty_file(self) -> None:
        fm, body = parse_frontmatter("")
        assert fm is None
        assert body == ""

    def test_malformed_frontmatter_returns_none(self) -> None:
        # Unbalanced flow mapping -> YAMLError
        text = "---\nname: [unclosed\n---\nbody\n"
        fm, body = parse_frontmatter(text)
        assert fm is None
        assert body == "body\n"

    def test_non_mapping_frontmatter_returns_none(self) -> None:
        # Valid YAML, but not a mapping -> treated as no frontmatter dict.
        text = "---\n- one\n- two\n---\nbody\n"
        fm, body = parse_frontmatter(text)
        assert fm is None
        assert body == "body\n"

    def test_empty_frontmatter_block(self) -> None:
        # "---\n---" is a bare "---" line followed by the closing marker with
        # nothing in between them, so the pattern's non-greedy body match
        # requires at least the empty string before "\n---" -- this does not
        # match "---\n---\nbody\n" as a frontmatter block at all (there is no
        # content between the second "---" and a subsequent "\n---"), so it
        # is treated as "no frontmatter".
        text = "---\n---\nbody\n"
        fm, body = parse_frontmatter(text)
        assert fm is None
        assert body == text

    def test_unterminated_frontmatter(self) -> None:
        text = "---\nname: foo\nno closing marker\n"
        fm, body = parse_frontmatter(text)
        assert fm is None
        assert body == text
