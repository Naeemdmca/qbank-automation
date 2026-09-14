#!/usr/bin/env python3
"""
run_all.py
==========
QBank Automation - Master Orchestrator v2.0

A beautiful, easy-to-use pipeline that converts UWorld PDFs or
screenshots into a structured CSV package for QBank import.

Flow:
  PDFs      -> marker_single -> Markdown -> final_qbank.csv
  Markdown  -> (skip PDF step)         -> final_qbank.csv
  Images    -> Gemini API              -> qbank_from_images.csv
"""

import sys
from pathlib import Path
import os

import ui
import pdf_processor
import md_to_csv
import image_processor

BASE_DIR = Path(__file__).resolve().parent
VERSION = "2.0"


# ---------------------------------------------------------------------------
# Input discovery
# ---------------------------------------------------------------------------
def scan_inputs() -> dict:
    """Scan input folders and return what was found."""
    pdf_dir = BASE_DIR / "input_pdfs"
    img_dir = BASE_DIR / "input_images"
    md_dir  = BASE_DIR / "output" / "temp_markdown"

    pdfs = sorted(pdf_dir.glob("*.pdf")) if pdf_dir.exists() else []
    mds  = sorted(md_dir.rglob("*.md"))  if md_dir.exists()  else []
    imgs = []
    if img_dir.exists():
        for pattern in ("*.png", "*.jpg", "*.jpeg", "*.gif", "*.webp", "*.bmp"):
            imgs.extend(img_dir.glob(pattern))
        imgs = sorted(set(imgs))

    return {"pdfs": pdfs, "images": imgs, "markdown": mds}


def resolve_gemini_key() -> str:
    """Get the Gemini API key from env, .env, or prompt."""
    key = os.environ.get("GEMINI_API_KEY")
    if key:
        return key
    env_file = BASE_DIR / ".env"
    if env_file.exists():
        for line in env_file.read_text(encoding="utf-8").splitlines():
            s = line.strip()
            if s.startswith("GEMINI_API_KEY="):
                key = s.split("=", 1)[1].strip().strip("'").strip('"')
                if key:
                    return key
    key = input(ui.c("  Enter your Gemini API key (aistudio.google.com): ",
                     ui.BRIGHT_YELLOW, ui.BOLD)).strip()
    if not key:
        return key
    try:
        env_file.write_text(f"GEMINI_API_KEY={key}\n", encoding="utf-8")
        ui.info("Saved key to .env for future runs.")
    except Exception:
        pass
    return key


# ---------------------------------------------------------------------------
# Pipeline stages
# ---------------------------------------------------------------------------
def stage_pdfs(pdfs) -> bool:
    """Run marker_single on all PDFs. Returns True if at least one succeeded."""
    ui.section("STEP 1/3  PDF to Markdown (marker_single)")

    marker_cmd = pdf_processor.find_marker_command()
    if marker_cmd is None:
        ui.error("marker_single could not be found. Is marker-pdf installed?")
        return False

    ui.info(f"Tool: {marker_cmd}")
    ui.info(f"PDFs found: {len(pdfs)}")
    print()

    ok = 0
    fail = 0
    for i, pdf_path in enumerate(pdfs, 1):
        ui.progress_bar(i - 1, len(pdfs), "Processing", suffix=pdf_path.name[:30])
        if pdf_processor.process_single_pdf(pdf_path, marker_cmd):
            ok += 1
        else:
            fail += 1
    ui.progress_bar(len(pdfs), len(pdfs), "Done", suffix="")

    if ok:
        ui.success(f"Processed {ok} PDF(s).")
    if fail:
        ui.warning(f"{fail} PDF(s) had errors and were skipped.")
        return fail == 0
    return True


def stage_markdown_to_csv() -> int:
    """Convert all markdown files to final_qbank.csv. Returns question count."""
    ui.section("STEP 2/3  Markdown  ->  final_qbank.csv")

    md_files = md_to_csv.find_markdown_files()
    if not md_files:
        ui.warning("No markdown files in ./output/temp_markdown/")
        return 0

    ui.info(f"Parsing {len(md_files)} markdown file(s)...")
    print()

    all_rows = []
    for md_file in md_files:
        content = md_file.read_text(encoding="utf-8")
        questions = md_to_csv.split_questions(content)
        for qid, block in questions:
            row = md_to_csv.parse_question(qid, block)
            all_rows.append(row)

    if not all_rows:
        ui.warning("No questions were extracted.")
        return 0

    import pandas as pd
    import csv as _csv
    df = pd.DataFrame(all_rows, columns=md_to_csv.CSV_COLUMNS)
    df.to_csv(md_to_csv.OUTPUT_CSV, index=False, quoting=_csv.QUOTE_ALL)

    ui.success(f"Wrote {len(all_rows)} question(s) to final_qbank.csv")
    return len(all_rows)


def stage_images(images) -> int:
    """Use Gemini to extract questions from screenshot images."""
    ui.section("STEP 1/3  Screenshots -> CSV (Gemini)")

    api_key = resolve_gemini_key()
    if not api_key:
        ui.error("No API key provided. Exiting.")
        return 0

    model, genai = image_processor.init_gemini(api_key)

    rows = []
    for i, img_path in enumerate(images, 1):
        row = image_processor.process_image(model, img_path, i)
        if row:
            rows.append(row)
        if i < len(images):
            import time as _time
            ui.info(f"  rate-limit pause ({image_processor.RATE_LIMIT_DELAY}s) ...")
            _time.sleep(image_processor.RATE_LIMIT_DELAY)

    output_csv = BASE_DIR / "output" / "qbank_from_images.csv"
    import csv as _csv
    with open(output_csv, "w", newline="", encoding="utf-8") as fh:
        writer = _csv.DictWriter(fh, fieldnames=image_processor.CSV_COLUMNS,
                                 quoting=_csv.QUOTE_ALL)
        writer.writeheader()
        for r in rows:
            writer.writerow(r)

    ui.success(f"Processed {len(rows)}/{len(images)} image(s) successfully")
    return len(rows)



def show_summary(counts: dict) -> None:
    """Render the final summary card + table."""
    ui.section("SUMMARY")

    ui.card("DELIVERABLES",
            "  CSV   : ./output/final_qbank.csv  (or qbank_from_images.csv)\n"
            "  Images: ./output/images/  ->  move to your QBank media folder\n"
            "  Cache : ./output/temp_markdown/")

    rows = []
    if counts["pdfs"]:
        rows.append(("PDFs processed", str(counts["pdfs"])))
    if counts["markdown"]:
        rows.append(("Markdown files", str(counts["markdown"])))
    if counts["images"]:
        rows.append(("Images processed", str(counts["images"])))
    if counts["questions"]:
        rows.append(("Questions in CSV", str(counts["questions"])))

    if rows:
        ui.table(["Metric", "Count"], rows)
    else:
        ui.warning("Nothing was processed this run.")

    ui.success("All done!")


def main() -> None:
    ui.banner("Q B A N K   A U T O M A T I O N",
              f"UWorld PDFs / Screenshots -> Structured CSV  (v{VERSION})")

    ui.card("WHAT THIS DOES",
            "  Scans your input folders, extracts questions, options,\n"
            "  explanations, tables, and image references, then packages\n"
            "  everything into a clean CSV for your QBank import.")

    inputs = scan_inputs()

    ui.section("INPUT SCAN")
    ui.status("PDF input folder", f"{len(inputs['pdfs'])} file(s) in ./input_pdfs/")
    ui.status("Screenshot folder", f"{len(inputs['images'])} file(s) in ./input_images/")
    ui.status("Existing markdown", f"{len(inputs['markdown'])} file(s) in ./output/temp_markdown/")
    print()

    counts = {"pdfs": 0, "markdown": 0, "images": 0, "questions": 0}

    if inputs["pdfs"]:
        counts["pdfs"] = len(inputs["pdfs"])
        ok = stage_pdfs(inputs["pdfs"])
        if not ok:
            ui.warning("PDF processing had errors - continuing with markdown.")
        counts["questions"] = stage_markdown_to_csv()
    elif inputs["markdown"]:
        counts["markdown"] = len(inputs["markdown"])
        ui.info(f"Skipping PDF step - using {len(inputs['markdown'])} existing markdown file(s).")
        counts["questions"] = stage_markdown_to_csv()
    elif inputs["images"]:
        counts["images"] = stage_images(inputs["images"])
    else:
        ui.section("READY WHEN YOU ARE")
        ui.warning("No input files found yet. Drop your files and re-run:")
        ui.status("PDFs", "put them in  ./input_pdfs/")
        ui.status("Screenshots", "put them in ./input_images/")
        ui.status("Markdown", "place .md files in ./output/temp_markdown/")
        print()

    show_summary(counts)


if __name__ == "__main__":
    main()
