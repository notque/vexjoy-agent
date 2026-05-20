#!/usr/bin/env python3
"""Chrome-headless PDF generator for html-artifact outputs.

Auto-detects shape from `<body data-shape="...">`, drives Chrome headless,
and validates the result. Page sizing is controlled by the HTML's `@page`
CSS rule; this script does not pass paper dimensions to Chrome.

Phase 6 EXPORT of the html-artifact pipeline.

Exit codes:
    0: PDF generated and validated successfully.
    1: PDF generated but validation flagged issues (see `warnings`).
    2: Chrome not found.
    3: Input file missing or unreadable.
    4: Generation failed (Chrome error or no output file).

Usage:
    python3 to-pdf.py --input artifact.html
    python3 to-pdf.py --input deck.html --output deck.pdf --shape deck
    python3 to-pdf.py --input report.html --json
"""

from __future__ import annotations

import argparse
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
from dataclasses import dataclass, field
from pathlib import Path

CHROME_FALLBACKS: tuple[str, ...] = (
    "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome",
    "chromium",
    "google-chrome",
    "chrome",
)

# Map shape -> page-size token. Only used when --page-size is not "auto".
# Note: actual paper size is driven by HTML `@page` CSS; these labels are
# advisory and reported in JSON output for downstream tooling.
SHAPE_PAGE_SIZE: dict[str, str] = {
    "deck": "deck-16x9",
    "report": "letter-portrait",
    "spec": "letter-landscape",
    "data-viz": "letter-portrait",
}
DEFAULT_PAGE_SIZE = "letter-portrait"

CHROME_TIMEOUT_SECONDS = 90
MIN_PDF_SIZE_BYTES = 10 * 1024  # 10KB


@dataclass
class PdfResult:
    """Aggregate result of a PDF generation + validation run."""

    ok: bool = False
    input: str = ""
    output: str = ""
    shape: str = ""
    page_size: str = ""
    size_bytes: int = 0
    pages: int = 0
    expected_pages: int | None = None
    chrome_path: str = ""
    warnings: list[str] = field(default_factory=list)
    errors: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, object]:
        return {
            "ok": self.ok,
            "input": self.input,
            "output": self.output,
            "shape": self.shape,
            "page_size": self.page_size,
            "size_bytes": self.size_bytes,
            "pages": self.pages,
            "expected_pages": self.expected_pages,
            "chrome_path": self.chrome_path,
            "warnings": self.warnings,
            "errors": self.errors,
        }


def find_chrome(override: str | None = None) -> str | None:
    """Locate a Chrome/Chromium binary.

    Resolution order:
        1. Explicit `--chrome-path` (override).
        2. `CHROME_PATH` environment variable.
        3. macOS Google Chrome bundle path.
        4. `chromium`, `google-chrome`, `chrome` on PATH.

    Returns the absolute path or None if no executable was found.
    """
    candidates: list[str] = []
    if override:
        candidates.append(override)
    env_path = os.environ.get("CHROME_PATH")
    if env_path:
        candidates.append(env_path)
    candidates.extend(CHROME_FALLBACKS)

    for cand in candidates:
        if "/" in cand or "\\" in cand:
            p = Path(cand)
            if p.is_file() and os.access(p, os.X_OK):
                return str(p)
        else:
            found = shutil.which(cand)
            if found:
                return found
    return None


def detect_shape(html: str) -> str | None:
    """Extract `data-shape="..."` attribute from the `<body>` tag."""
    match = re.search(r"<body\b[^>]*\bdata-shape=[\"']([^\"']+)[\"']", html, re.IGNORECASE)
    if match:
        return match.group(1).strip().lower()
    return None


def count_slides(html: str) -> int:
    """Count `<section class="slide">` and `<div class="slide">` elements."""
    pattern = r"<(?:section|div)\b[^>]*\bclass=[\"'][^\"']*\bslide\b[^\"']*[\"'][^>]*>"
    return len(re.findall(pattern, html, re.IGNORECASE))


def count_pdf_pages(pdf_path: Path) -> int:
    """Best-effort PDF page count. Prefer pypdfium2; fall back to byte scan."""
    try:
        import pypdfium2  # type: ignore[import-not-found]

        pdf = pypdfium2.PdfDocument(str(pdf_path))
        try:
            return len(pdf)
        finally:
            pdf.close()
    except ImportError:
        pass
    except Exception:
        pass

    # Fallback: scan raw bytes for `/Type /Page` markers (not /Pages).
    try:
        data = pdf_path.read_bytes()
    except OSError:
        return 0
    # Match "/Type" + whitespace + "/Page" not followed by 's' (which would be /Pages).
    matches = re.findall(rb"/Type\s*/Page(?![a-zA-Z])", data)
    return len(matches)


def resolve_page_size(shape: str, override: str) -> str:
    """Resolve the advisory page-size token."""
    if override != "auto":
        return override
    return SHAPE_PAGE_SIZE.get(shape, DEFAULT_PAGE_SIZE)


def run_chrome(
    chrome_path: str,
    input_url: str,
    output_path: Path,
    verbose: bool,
    timeout_seconds: int = CHROME_TIMEOUT_SECONDS,
) -> tuple[int, str]:
    """Invoke Chrome headless to render `input_url` to `output_path`.

    Uses an ephemeral `--user-data-dir` so the user's Chrome profile is
    untouched.

    Returns (return_code, stderr_text). On timeout, return_code = 124 and
    stderr contains a synthetic message.
    """
    with tempfile.TemporaryDirectory(prefix="to-pdf-chrome-") as user_data_dir:
        cmd = [
            chrome_path,
            "--headless=new",
            "--disable-gpu",
            "--no-pdf-header-footer",
            "--virtual-time-budget=10000",
            "--hide-scrollbars",
            f"--user-data-dir={user_data_dir}",
            f"--print-to-pdf={output_path}",
            input_url,
        ]
        # Chrome on macOS can spawn helper processes that inherit our pipes
        # and keep them open after the parent exits, deadlocking
        # subprocess.run's capture machinery. When not verbose, send stderr
        # to DEVNULL so helpers can't hold us open.
        stderr_target: int = subprocess.PIPE if verbose else subprocess.DEVNULL
        try:
            proc = subprocess.run(
                cmd,
                stdout=subprocess.DEVNULL,
                stderr=stderr_target,
                text=True,
                timeout=timeout_seconds,
                check=False,
            )
        except subprocess.TimeoutExpired as exc:
            return 124, f"Chrome timed out after {timeout_seconds}s: {exc}"

        if verbose and proc.stderr:
            sys.stderr.write(proc.stderr)
        return proc.returncode, proc.stderr or ""


def generate_pdf(
    input_path: Path,
    output_path: Path,
    shape_override: str | None,
    page_size_override: str,
    chrome_override: str | None,
    verbose: bool,
    timeout_seconds: int = CHROME_TIMEOUT_SECONDS,
) -> PdfResult:
    """Drive the full generate + validate flow. Caller handles exit codes."""
    result = PdfResult(input=str(input_path), output=str(output_path))

    chrome_path = find_chrome(chrome_override)
    if chrome_path is None:
        result.errors.append("Chrome not found. Install Google Chrome or set CHROME_PATH env var.")
        return result
    result.chrome_path = chrome_path

    try:
        html = input_path.read_text(encoding="utf-8")
    except (OSError, UnicodeDecodeError) as e:
        result.errors.append(f"Cannot read input file: {e}")
        return result

    detected = detect_shape(html)
    shape = (shape_override or detected or "report").lower()
    if shape_override is None and detected is None:
        result.warnings.append("No data-shape attribute found on <body>; defaulting to 'report'.")
    result.shape = shape
    result.page_size = resolve_page_size(shape, page_size_override)

    if shape == "deck":
        slides = count_slides(html)
        if slides > 0:
            result.expected_pages = slides

    input_url = f"file://{input_path.resolve()}"
    rc, stderr_text = run_chrome(chrome_path, input_url, output_path, verbose, timeout_seconds)

    if rc != 0:
        # Chrome on macOS sometimes hangs on subprocess shutdown after the
        # PDF is already on disk (helper processes hold pipes open). Recover:
        # if the output file exists and exceeds the minimum size, treat the
        # generation as successful and record a warning.
        if rc == 124 and output_path.is_file() and output_path.stat().st_size >= MIN_PDF_SIZE_BYTES:
            result.warnings.append(
                f"Chrome did not exit within {timeout_seconds}s, but PDF was written. "
                "Recovered output; helper-process shutdown stalled."
            )
        else:
            snippet = stderr_text.strip().splitlines()[-1] if stderr_text.strip() else ""
            msg = f"Chrome exited with code {rc}."
            if snippet:
                msg += f" Last stderr: {snippet}"
            result.errors.append(msg)
            return result

    if not output_path.is_file():
        result.errors.append(f"Chrome reported success but no output file at {output_path}.")
        return result

    result.size_bytes = output_path.stat().st_size
    if result.size_bytes < MIN_PDF_SIZE_BYTES:
        result.warnings.append(
            f"PDF size {result.size_bytes} bytes is below {MIN_PDF_SIZE_BYTES} threshold (may be blank or error page)."
        )

    result.pages = count_pdf_pages(output_path)
    if result.pages == 0:
        result.warnings.append("Could not determine page count (or PDF has 0 pages).")

    if result.expected_pages is not None and result.pages != result.expected_pages:
        result.warnings.append(f"Page count mismatch: expected {result.expected_pages} (slides), got {result.pages}.")

    result.ok = not result.warnings and not result.errors
    return result


def emit_human(result: PdfResult) -> None:
    """Human-readable stdout summary."""
    status = "OK" if result.ok else ("WARN" if not result.errors else "FAIL")
    sys.stdout.write(f"[{status}] {result.input} -> {result.output}\n")
    sys.stdout.write(
        f"  shape={result.shape}  page_size={result.page_size}  size={result.size_bytes}B  pages={result.pages}"
    )
    if result.expected_pages is not None:
        sys.stdout.write(f"  expected={result.expected_pages}")
    sys.stdout.write(f"\n  chrome={result.chrome_path}\n")
    for w in result.warnings:
        sys.stdout.write(f"  warning: {w}\n")
    for e in result.errors:
        sys.stdout.write(f"  error: {e}\n")


def emit_json(result: PdfResult) -> None:
    """JSON-only stdout for pipeline consumption."""
    json.dump(result.to_dict(), sys.stdout, indent=2)
    sys.stdout.write("\n")


def main() -> None:
    """CLI entry point."""
    parser = argparse.ArgumentParser(description="Render an html-artifact to PDF via headless Chrome.")
    parser.add_argument("--input", required=True, help="Path to the input .html file.")
    parser.add_argument("--output", default=None, help="Output .pdf path. Defaults to input with .pdf extension.")
    parser.add_argument(
        "--shape",
        default=None,
        help="Override shape detection (deck, report, spec, data-viz, ...). If omitted, parsed from <body data-shape>.",
    )
    parser.add_argument(
        "--page-size",
        default="auto",
        help="Advisory page-size token (auto|letter-portrait|letter-landscape|deck-16x9). "
        "Actual paper size is driven by HTML @page CSS; this is reported only.",
    )
    parser.add_argument("--chrome-path", default=None, help="Override Chrome binary path.")
    parser.add_argument(
        "--timeout",
        type=int,
        default=CHROME_TIMEOUT_SECONDS,
        help=f"Chrome subprocess timeout in seconds (default: {CHROME_TIMEOUT_SECONDS}).",
    )
    parser.add_argument("--json", action="store_true", help="Emit JSON to stdout instead of human-readable summary.")
    parser.add_argument("--verbose", action="store_true", help="Forward Chrome stderr to this process's stderr.")
    args = parser.parse_args()

    input_path = Path(args.input)
    if not input_path.is_file():
        result = PdfResult(input=args.input, errors=[f"Input file not found: {args.input}"])
        emit_json(result) if args.json else emit_human(result)
        sys.exit(3)

    if args.output:
        output_path = Path(args.output)
    else:
        output_path = input_path.with_suffix(".pdf")
    output_path = output_path.resolve()
    output_path.parent.mkdir(parents=True, exist_ok=True)

    result = generate_pdf(
        input_path=input_path,
        output_path=output_path,
        shape_override=args.shape,
        page_size_override=args.page_size,
        chrome_override=args.chrome_path,
        verbose=args.verbose,
        timeout_seconds=args.timeout,
    )

    emit_json(result) if args.json else emit_human(result)

    if result.errors:
        if any("Chrome not found" in e for e in result.errors):
            sys.exit(2)
        if any("Cannot read input" in e for e in result.errors):
            sys.exit(3)
        sys.exit(4)
    if result.warnings:
        sys.exit(1)
    sys.exit(0)


if __name__ == "__main__":
    main()
