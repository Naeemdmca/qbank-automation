#!/usr/bin/env python3
"""
pdf_processor.py
================
Step 2: PDF Processing using Marker-PDF.

This script:
  1. Scans ./input_pdfs/ for PDF files.
  2. Runs ``marker_single`` (or ``marker``) on each PDF to produce Markdown
     + an ``images`` sub-directory under ./output/temp_markdown/.
  3. Copies every extracted image into ./output/images/ (centralised folder).
  4. Logs errors gracefully and continues with the next PDF.

Usage:
    python pdf_processor.py
"""

import os
import re
import shutil
import subprocess
import sys
from pathlib import Path

import ui

# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------
BASE_DIR       = Path(__file__).resolve().parent
INPUT_PDF_DIR  = BASE_DIR / "input_pdfs"
OUTPUT_TEMP    = BASE_DIR / "output" / "temp_markdown"
OUTPUT_IMAGES  = BASE_DIR / "output" / "images"

# Image extensions to look for
IMAGE_EXTS     = {".png", ".jpg", ".jpeg", ".gif", ".webp", ".bmp", ".tiff"}


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------
def find_marker_command() -> str | None:
    """Try several ways to invoke Marker from the command line."""
    import sys

    # Build list of candidates including full path to Scripts dir
    scripts_dir = Path(sys.executable).parent
    scripts_marker = scripts_dir / "marker_single.exe"
    scripts_marker_py = scripts_dir / "marker_single"

    candidates = [
        "marker_single",
        "marker",
        str(scripts_marker),
        str(scripts_marker_py),
        "python -m marker",
        "python -m marker_single",
    ]

    for cmd in candidates:
        try:
            result = subprocess.run(
                f"{cmd} --help",
                shell=True,
                capture_output=True,
                text=True,
                timeout=15,
            )
            if result.returncode == 0 or result.stdout or result.stderr:
                return cmd
        except Exception:
            continue
    return None


def ensure_dirs() -> None:
    """Create the output directories if they do not exist."""
    OUTPUT_TEMP.mkdir(parents=True, exist_ok=True)
    OUTPUT_IMAGES.mkdir(parents=True, exist_ok=True)


def find_images(directory: Path) -> list[Path]:
    """Recursively find image files in *directory*."""
    images = []
    if not directory.exists():
        return images
    for item in directory.rglob("*"):
        if item.is_file() and item.suffix.lower() in IMAGE_EXTS:
            images.append(item)
    return images


# ---------------------------------------------------------------------------
# Main logic
# ---------------------------------------------------------------------------
def process_single_pdf(pdf_path: Path, marker_cmd: str) -> bool:
    """Process one PDF with marker_single and copy its images.

    Returns ``True`` on success, ``False`` on failure.
    """
    print(f"  >> Processing: {pdf_path.name}")

    # Build environment with Scripts dir in PATH for marker_single
    env = os.environ.copy()
    scripts_dir = str(Path(sys.executable).parent)
    if scripts_dir not in env.get("PATH", ""):
        env["PATH"] = scripts_dir + os.pathsep + env.get("PATH", "")

    # Run marker_single — each PDF gets its own sub-folder under OUTPUT_TEMP
    cmd_str = f'{marker_cmd} "{pdf_path}" --output_dir "{OUTPUT_TEMP}"'
    try:
        result = subprocess.run(
            cmd_str,
            shell=True,
            capture_output=True,
            text=True,
            timeout=600,
            env=env,
        )
        if result.returncode != 0:
            print(f"     WARNING: marker returned non-zero exit code {result.returncode}")
            print(f"     stderr: {result.stderr[-500:]}")
    except subprocess.TimeoutExpired:
        print(f"     ERROR: marker timed out after 600s for {pdf_path.name}")
        return False
    except Exception as exc:
        print(f"     ERROR: {exc}")
        return False

    # Copy images from this PDF's output folder into the central images dir.
    # Marker creates: output_dir / <pdf_stem> / images / *.{ext}
    pdf_stem = pdf_path.stem
    possible_dirs = [
        OUTPUT_TEMP / pdf_stem / "images",
        OUTPUT_TEMP / pdf_stem,
    ]
    copied = 0
    for search_dir in possible_dirs:
        if search_dir.exists():
            for img in find_images(search_dir):
                dest = OUTPUT_IMAGES / img.name
                if dest.exists():
                    stem = img.stem
                    dest = OUTPUT_IMAGES / f"{stem}_{copied}{img.suffix}"
                shutil.copy2(img, dest)
                copied += 1
                print(f"     Copied: {img.name} -> output/images/{dest.name}")

    # Also search everywhere in temp_markdown (marker sometimes places differently)
    for img in find_images(OUTPUT_TEMP):
        if img.parent == OUTPUT_IMAGES:
            continue
        dest = OUTPUT_IMAGES / img.name
        if dest.exists():
            continue
        shutil.copy2(img, dest)
        copied += 1
        print(f"     Copied: {img.name} -> output/images/{dest.name}")

    if copied == 0:
        print("     (no images extracted from this PDF)")
    return True


def main() -> None:
    ui.banner("P D F   P R O C E S S O R", "Marker-PDF converter")
    ui.section("INPUT")

    ensure_dirs()

    # Check for PDFs
    pdf_files = sorted(INPUT_PDF_DIR.glob("*.pdf"))
    if not pdf_files:
        ui.warning("No PDF files found in ./input_pdfs/")
        ui.info("Place PDFs there and re-run, or use image_processor.py for screenshots.")
        return

    ui.info(f"Found {len(pdf_files)} PDF file(s).\n")

    # Locate marker command
    marker_cmd = find_marker_command()
    if marker_cmd is None:
        ui.error("Could not find marker_single command.")
        ui.info("Is marker-pdf installed? Try: python -m pip install marker-pdf")
        sys.exit(1)

    ui.status("Marker tool", marker_cmd)
    print()

    success_count = 0
    fail_count = 0

    for i, pdf_path in enumerate(pdf_files, 1):
        ui.progress_bar(i - 1, len(pdf_files), "Converting", suffix=pdf_path.name[:30])
        if process_single_pdf(pdf_path, marker_cmd):
            success_count += 1
        else:
            fail_count += 1
    ui.progress_bar(len(pdf_files), len(pdf_files), "Done", suffix="")

    ui.section("RESULT")
    ui.success(f"Processed: {success_count}  |  Failed: {fail_count}")
    ui.status("Images", "./output/images/")
    ui.status("Markdown", "./output/temp_markdown/")
    print()


if __name__ == "__main__":
    main()