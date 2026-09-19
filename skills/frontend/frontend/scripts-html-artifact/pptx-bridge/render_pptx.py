#!/usr/bin/env python3
"""
Convert PPTX to PDF and then to per-slide PNG images for visual QA.

Uses LibreOffice (soffice) for PPTX-to-PDF conversion and either
pdftoppm (poppler-utils) or LibreOffice for PDF-to-PNG conversion.

Usage:
    python3 convert_slides.py --input deck.pptx --output-dir ./qa_images/

Exit codes:
    0 = success
    1 = missing dependencies (LibreOffice not installed)
    2 = conversion failed
    3 = invalid input
"""

import argparse
import os
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path


def check_soffice() -> str | None:
    """Return path to soffice binary, or None if not found."""
    path = shutil.which("soffice")
    if path:
        return path
    # Check common install locations
    common_paths = [
        "/usr/bin/soffice",
        "/usr/local/bin/soffice",
        "/snap/bin/soffice",
        "/Applications/LibreOffice.app/Contents/MacOS/soffice",
    ]
    for p in common_paths:
        if os.path.isfile(p):
            return p
    return None


def check_pdftoppm() -> str | None:
    """Return path to pdftoppm binary, or None if not found."""
    return shutil.which("pdftoppm")


def pptx_to_pdf(soffice_path: str, pptx_path: str, output_dir: str) -> str:
    """Convert PPTX to PDF using LibreOffice headless mode.

    Returns path to generated PDF.
    """
    cmd = [
        soffice_path,
        "--headless",
        "--convert-to",
        "pdf",
        "--outdir",
        output_dir,
        pptx_path,
    ]

    result = subprocess.run(
        cmd,
        capture_output=True,
        text=True,
        timeout=120,  # 2 minute timeout for large presentations
    )

    if result.returncode != 0:
        raise RuntimeError(f"LibreOffice PDF conversion failed:\nstdout: {result.stdout}\nstderr: {result.stderr}")

    # Find the generated PDF
    pptx_name = Path(pptx_path).stem
    pdf_path = Path(output_dir) / f"{pptx_name}.pdf"

    if not pdf_path.exists():
        # Sometimes LibreOffice outputs to a slightly different name
        pdfs = list(Path(output_dir).glob("*.pdf"))
        if pdfs:
            pdf_path = pdfs[0]
        else:
            raise RuntimeError(
                f"PDF not found after conversion. Expected: {pdf_path}\nLibreOffice output: {result.stdout}"
            )

    return str(pdf_path)


def pdf_to_pngs_pdftoppm(pdftoppm_path: str, pdf_path: str, output_dir: str, dpi: int = 150) -> list[str]:
    """Convert PDF pages to PNGs using pdftoppm.

    Returns list of PNG paths sorted by page number.
    """
    prefix = str(Path(output_dir) / "slide")

    cmd = [
        pdftoppm_path,
        "-png",
        "-r",
        str(dpi),
        pdf_path,
        prefix,
    ]

    result = subprocess.run(cmd, capture_output=True, text=True, timeout=120)

    if result.returncode != 0:
        raise RuntimeError(f"pdftoppm conversion failed:\nstderr: {result.stderr}")

    # Find generated PNGs
    pngs = sorted(Path(output_dir).glob("slide-*.png"))
    return [str(p) for p in pngs]


def pdf_to_pngs_soffice(soffice_path: str, pdf_path: str, output_dir: str) -> list[str]:
    """Convert PDF pages to PNGs using LibreOffice (fallback).

    Note: This produces one image per page but quality may vary.
    Returns list of PNG paths.
    """
    cmd = [
        soffice_path,
        "--headless",
        "--convert-to",
        "png",
        "--outdir",
        output_dir,
        pdf_path,
    ]

    result = subprocess.run(cmd, capture_output=True, text=True, timeout=120)

    if result.returncode != 0:
        raise RuntimeError(f"LibreOffice PNG conversion failed:\nstderr: {result.stderr}")

    pngs = sorted(Path(output_dir).glob("*.png"))
    return [str(p) for p in pngs]


def convert(pptx_path: str, output_dir: str, dpi: int = 150, keep_pdf: bool = False) -> dict:
    """Full conversion pipeline: PPTX -> PDF -> PNGs.

    Returns dict with 'pdf_path', 'png_paths', and 'slide_count'.
    """
    # Validate input
    if not Path(pptx_path).exists():
        raise FileNotFoundError(f"PPTX file not found: {pptx_path}")

    if not Path(pptx_path).suffix.lower() == ".pptx":
        raise ValueError(f"File is not a .pptx: {pptx_path}")

    # Check dependencies
    soffice_path = check_soffice()
    if not soffice_path:
        raise EnvironmentError(
            "LibreOffice (soffice) not found. Install it:\n"
            "  Ubuntu/Debian: sudo apt install libreoffice-impress\n"
            "  macOS: brew install --cask libreoffice\n"
            "  Snap: sudo snap install libreoffice"
        )

    pdftoppm_path = check_pdftoppm()

    # Create output directory
    Path(output_dir).mkdir(parents=True, exist_ok=True)

    # Step 1: PPTX -> PDF
    print("Converting PPTX to PDF...")
    with tempfile.TemporaryDirectory() as tmpdir:
        pdf_path = pptx_to_pdf(soffice_path, pptx_path, tmpdir)

        # Move PDF to output dir if keeping
        final_pdf = str(Path(output_dir) / Path(pdf_path).name)
        shutil.copy2(pdf_path, final_pdf)

    # Step 2: PDF -> PNGs
    print(f"Converting PDF to slide images (DPI={dpi})...")
    if pdftoppm_path:
        print("  Using pdftoppm for high-quality conversion")
        png_paths = pdf_to_pngs_pdftoppm(pdftoppm_path, final_pdf, output_dir, dpi)
    else:
        print("  Using LibreOffice for PNG conversion (pdftoppm not available)")
        png_paths = pdf_to_pngs_soffice(soffice_path, final_pdf, output_dir)

    # Clean up PDF if not keeping
    if not keep_pdf and Path(final_pdf).exists():
        Path(final_pdf).unlink()

    return {
        "pdf_path": final_pdf if keep_pdf else None,
        "png_paths": png_paths,
        "slide_count": len(png_paths),
    }


def main():
    parser = argparse.ArgumentParser(description="Convert PPTX to PDF and per-slide PNG images.")
    parser.add_argument(
        "--input",
        required=True,
        help="Path to input .pptx file",
    )
    parser.add_argument(
        "--output-dir",
        required=True,
        help="Directory for output PNG files",
    )
    parser.add_argument(
        "--dpi",
        type=int,
        default=150,
        help="PNG resolution in DPI (default: 150)",
    )
    parser.add_argument(
        "--keep-pdf",
        action="store_true",
        help="Keep intermediate PDF file",
    )
    args = parser.parse_args()

    try:
        result = convert(args.input, args.output_dir, args.dpi, args.keep_pdf)
        print(f"\nSUCCESS: Converted {result['slide_count']} slides to PNG")
        for png in result["png_paths"]:
            print(f"  {png}")
        if result["pdf_path"]:
            print(f"  PDF: {result['pdf_path']}")
    except FileNotFoundError as e:
        print(f"ERROR: {e}", file=sys.stderr)
        sys.exit(3)
    except EnvironmentError as e:
        print(f"ERROR: {e}", file=sys.stderr)
        sys.exit(1)
    except Exception as e:
        print(f"ERROR: Conversion failed: {e}", file=sys.stderr)
        sys.exit(2)


if __name__ == "__main__":
    main()
