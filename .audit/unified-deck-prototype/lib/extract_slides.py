#!/usr/bin/env python3
"""HTML deck -> slide-map JSON extractor.

Parses an html-artifact deck-shape HTML file. Each `<section class="slide">`
becomes one slide-map entry. Detects layout family from class hints and
inner-element signatures.

Output schema (extended from pptx-generator's slide-map):

    {
        "type": "title" | "content" | "metric_grid" | "layer_rows" |
                "pipeline" | "code_block" | "compare_table_2col" |
                "compare_table_3col" | "outcome_grid" | "split_narrow" |
                "closing",
        "eyebrow": "...",
        "title":   "...",
        "subtitle": "...",
        "lead":    "...",
        "callout": "...",
        "bullets": [ {"text": "...", "bold_prefix": "Agents"} , ...],
        "metrics": [ {"value": "...", "label": "...", "desc": "..."}, ...],
        "layers":  [ {"name": "...", "count": "...", "desc": "..."}, ...],
        "pipeline_steps": ["ROUTE", "PLAN", ...],
        "code":    "$ claude\\n\\n> /do ...",
        "table":   {"headers": [...], "rows": [[...], ...]},
        "outcomes":[ {"heading": "...", "body": "..."}, ...],
        "split":   {"left": {...}, "right_card_rows": [{"name": "...", "trigger": "..."}]},
    }

Usage:
    python3 extract_slides.py --input deck.html --output slides.json
"""
from __future__ import annotations

import argparse
import json
import re
import sys
from html.parser import HTMLParser
from pathlib import Path


# ---------------------------------------------------------------------------
# Stdlib HTML walker -> tree of dicts
# ---------------------------------------------------------------------------


class _DOMBuilder(HTMLParser):
    """Build a lightweight tree of {tag, attrs, children, text} dicts."""

    VOID = {"br", "hr", "img", "meta", "link", "input"}

    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.root = {"tag": "_root", "attrs": {}, "children": []}
        self.stack = [self.root]

    def handle_starttag(self, tag, attrs):
        node = {"tag": tag, "attrs": dict(attrs), "children": []}
        self.stack[-1]["children"].append(node)
        if tag not in self.VOID:
            self.stack.append(node)

    def handle_startendtag(self, tag, attrs):
        node = {"tag": tag, "attrs": dict(attrs), "children": []}
        self.stack[-1]["children"].append(node)

    def handle_endtag(self, tag):
        # Pop until we close the matching tag (tolerant to malformed input).
        for i in range(len(self.stack) - 1, 0, -1):
            if self.stack[i]["tag"] == tag:
                del self.stack[i:]
                return

    def handle_data(self, data):
        if not data:
            return
        # Attach as text-node child to current parent.
        self.stack[-1]["children"].append({"tag": "_text", "text": data})


def _has_class(node: dict, cls: str) -> bool:
    classes = (node.get("attrs", {}).get("class") or "").split()
    return cls in classes


def _classes(node: dict) -> list[str]:
    return (node.get("attrs", {}).get("class") or "").split()


def _walk(node: dict):
    yield node
    for c in node.get("children", []):
        yield from _walk(c)


def _find_all(node: dict, tag: str | None = None, cls: str | None = None) -> list[dict]:
    out = []
    for n in _walk(node):
        if n.get("tag") == "_text":
            continue
        if tag is not None and n["tag"] != tag:
            continue
        if cls is not None and not _has_class(n, cls):
            continue
        out.append(n)
    return out


def _find(node, tag=None, cls=None):
    res = _find_all(node, tag, cls)
    return res[0] if res else None


def _text(node: dict) -> str:
    """Recursively concatenate visible text; collapse internal whitespace."""
    if node is None:
        return ""
    if node.get("tag") == "_text":
        return node.get("text", "")
    out = []
    for c in node.get("children", []):
        out.append(_text(c))
    s = "".join(out)
    # Normalize whitespace inside a single block.
    s = re.sub(r"[ \t\r\f\v]+", " ", s)
    return s.strip()


def _raw_inner(node: dict) -> str:
    """Concatenate text including \n exactly (for code blocks)."""
    if node is None:
        return ""
    if node.get("tag") == "_text":
        return node.get("text", "")
    return "".join(_raw_inner(c) for c in node.get("children", []))


# ---------------------------------------------------------------------------
# Layout detection + extraction
# ---------------------------------------------------------------------------


def detect_layout(section: dict) -> str:
    classes = _classes(section)
    aria = (section.get("attrs", {}) or {}).get("aria-label", "").lower()

    if "slide-title" in classes and "active" in classes:
        return "title"
    # Closing slide is also slide-title without "active"
    if "slide-title" in classes:
        return "closing"

    # Structural detectors (order matters: most specific first).
    if _find(section, cls="metric-grid"):
        return "metric_grid"
    if _find(section, cls="layer-row"):
        return "layer_rows"
    if _find(section, cls="pipeline"):
        return "pipeline"
    if _find(section, cls="code-block"):
        return "code_block"
    if _find(section, cls="compare-table"):
        # 2-col vs 3-col
        thead = _find(section, tag="thead")
        if thead:
            ths = _find_all(thead, tag="th")
            return "compare_table_3col" if len(ths) >= 3 else "compare_table_2col"
        return "compare_table_2col"
    if _find(section, cls="outcome-grid"):
        return "outcome_grid"
    if _find(section, cls="split-narrow"):
        return "split_narrow"

    # Generic prose with bullets or callout.
    return "content"


def _extract_eyebrow(section: dict) -> str:
    n = _find(section, cls="eyebrow") or _find(section, cls="eyebrow-h2")
    return _text(n) if n else ""


def _extract_title(section: dict) -> str:
    h1 = _find(section, tag="h1")
    if h1:
        return _text(h1)
    h2 = _find(section, tag="h2")
    return _text(h2) if h2 else ""


def _extract_subtitle(section: dict) -> str:
    n = _find(section, cls="subtitle")
    return _text(n) if n else ""


def _extract_lead(section: dict) -> str:
    n = _find(section, cls="lead")
    return _text(n) if n else ""


def _extract_callout(section: dict) -> str:
    n = _find(section, cls="callout")
    return _text(n) if n else ""


def _extract_bullets(section: dict) -> list[dict]:
    ul = _find(section, tag="ul")
    if not ul:
        return []
    out = []
    for li in _find_all(ul, tag="li"):
        # Detect "<strong>X</strong> rest" pattern.
        strong = _find(li, tag="strong")
        if strong:
            bold_prefix = _text(strong)
            full = _text(li)
            # Tail = everything after the strong text.
            tail = full[len(bold_prefix):].lstrip(" -—:")
            out.append({"text": tail, "bold_prefix": bold_prefix})
        else:
            out.append({"text": _text(li), "bold_prefix": ""})
    return out


def _extract_metrics(section: dict) -> list[dict]:
    grid = _find(section, cls="metric-grid")
    if not grid:
        return []
    out = []
    for m in _find_all(grid, cls="metric"):
        out.append({
            "value": _text(_find(m, cls="metric-value")),
            "label": _text(_find(m, cls="metric-label")),
            "desc":  _text(_find(m, cls="metric-desc")),
        })
    return out


def _extract_layers(section: dict) -> list[dict]:
    out = []
    for row in _find_all(section, cls="layer-row"):
        out.append({
            "name":  _text(_find(row, cls="layer-name")),
            "count": _text(_find(row, cls="layer-count")),
            "desc":  _text(_find(row, cls="layer-desc")),
        })
    return out


def _extract_pipeline(section: dict) -> list[dict]:
    out = []
    for step in _find_all(section, cls="pipeline-step"):
        out.append({
            "label": _text(_find(step, cls="step-label")),
            "name":  _text(_find(step, cls="step-name")),
        })
    return out


def _extract_pipeline_caption(section: dict) -> str:
    # The <p> that follows the .pipeline div.
    paragraphs = _find_all(section, tag="p")
    return _text(paragraphs[-1]) if paragraphs else ""


def _extract_code(section: dict) -> str:
    code_node = _find(section, cls="code-block")
    if not code_node:
        return ""
    # Preserve newlines; flatten span tags but keep their text.
    return _raw_inner(code_node).strip("\n")


def _extract_table(section: dict) -> dict:
    table = _find(section, cls="compare-table")
    if not table:
        return {"headers": [], "rows": []}
    headers = []
    thead = _find(table, tag="thead")
    if thead:
        headers = [_text(th) for th in _find_all(thead, tag="th")]
    rows = []
    tbody = _find(table, tag="tbody")
    if tbody:
        for tr in _find_all(tbody, tag="tr"):
            cells = []
            for td in _find_all(tr, tag="td"):
                role = "label"
                cls = _classes(td)
                if "danger" in cls:
                    role = "danger"
                elif "success" in cls:
                    role = "success"
                cells.append({"text": _text(td), "role": role})
            rows.append(cells)
    return {"headers": headers, "rows": rows}


def _extract_outcomes(section: dict) -> list[dict]:
    grid = _find(section, cls="outcome-grid")
    if not grid:
        return []
    out = []
    for card in _find_all(grid, cls="outcome"):
        out.append({
            "heading": _text(_find(card, tag="h3")),
            "body":    _text(_find(card, tag="p")),
        })
    return out


def _extract_split(section: dict) -> dict:
    split = _find(section, cls="split-narrow")
    if not split:
        return {}
    # First child div is the left column (eyebrow, h2, p, callout).
    cols = [c for c in split.get("children", []) if c.get("tag") == "div"]
    left, right = cols[0] if cols else None, cols[1] if len(cols) > 1 else None
    rows = []
    if right:
        for r in _find_all(right, cls="cli-row"):
            rows.append({
                "name":    _text(_find(r, cls="cli-name")),
                "trigger": _text(_find(r, cls="cli-trigger")),
            })
    return {
        "left": {
            "eyebrow":  _text(_find(left, cls="eyebrow-h2")) if left else "",
            "title":    _text(_find(left, tag="h2"))      if left else "",
            "lead":     _text(_find(left, tag="p"))       if left else "",
            "callout":  _text(_find(left, cls="callout")) if left else "",
        },
        "rows": rows,
    }


# ---------------------------------------------------------------------------
# Top-level pipeline
# ---------------------------------------------------------------------------


def extract_slides(html: str) -> list[dict]:
    parser = _DOMBuilder()
    parser.feed(html)
    sections = _find_all(parser.root, tag="section", cls="slide")
    out = []
    for section in sections:
        layout = detect_layout(section)
        slide: dict = {
            "type": layout,
            "eyebrow":  _extract_eyebrow(section),
            "title":    _extract_title(section),
            "subtitle": _extract_subtitle(section),
            "lead":     _extract_lead(section),
            "callout":  _extract_callout(section),
        }
        if layout == "content":
            slide["bullets"] = _extract_bullets(section)
        elif layout == "metric_grid":
            slide["metrics"] = _extract_metrics(section)
        elif layout == "layer_rows":
            slide["layers"] = _extract_layers(section)
        elif layout == "pipeline":
            slide["pipeline_steps"] = _extract_pipeline(section)
            slide["pipeline_caption"] = _extract_pipeline_caption(section)
        elif layout == "code_block":
            slide["code"] = _extract_code(section)
        elif layout in ("compare_table_2col", "compare_table_3col"):
            slide["table"] = _extract_table(section)
            # Optional p-tag intro.
            ps = _find_all(section, tag="p")
            slide["intro"] = _text(ps[0]) if ps else ""
        elif layout == "outcome_grid":
            slide["outcomes"] = _extract_outcomes(section)
        elif layout == "split_narrow":
            slide["split"] = _extract_split(section)
        elif layout == "closing":
            # h2 may contain an inline accent span; capture both halves.
            h2 = _find(section, tag="h2")
            spans = _find_all(h2, tag="span") if h2 else []
            slide["title"] = _text(h2)
            slide["accent_text"] = _text(spans[0]) if spans else ""
        out.append(slide)
    return out


def main():
    ap = argparse.ArgumentParser(description="Extract slide map from html-artifact deck HTML.")
    ap.add_argument("--input",  required=True, help="Input HTML deck file")
    ap.add_argument("--output", required=True, help="Output JSON slide-map path")
    args = ap.parse_args()

    src = Path(args.input)
    if not src.exists():
        print(f"ERROR: input not found: {src}", file=sys.stderr)
        sys.exit(2)

    slides = extract_slides(src.read_text(encoding="utf-8"))
    if not slides:
        print("ERROR: no <section class='slide'> blocks found", file=sys.stderr)
        sys.exit(3)

    out = Path(args.output)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(slides, indent=2, ensure_ascii=False))
    print(f"Extracted {len(slides)} slides -> {out}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
