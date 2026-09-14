#!/usr/bin/env python3
"""
image_processor.py
==================
Step 3: Image / Screenshot Processing using Gemini 1.5 Flash.

This script is the **fallback** when there are no PDFs — only screenshots
inside ./input_images/.

It:
  1. Scans ./input_images/ for image files.
  2. Sends each image to the Gemini 1.5 Flash model with a structured prompt.
  3. Parses the CSV-formatted response into rows.
  4. Writes results into ./output/qbank_from_images.csv.

The Google API key is read from the environment variable ``GEMINI_API_KEY``.
You can set it in the terminal before running:

    set GEMINI_API_KEY=YOUR_KEY_HERE
    python image_processor.py

You will be prompted for the key if it is not already set.
"""

import os
import sys
import csv
import base64
import time
from pathlib import Path

import ui

# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------
BASE_DIR       = Path(__file__).resolve().parent
INPUT_IMG_DIR  = BASE_DIR / "input_images"
OUTPUT_DIR     = BASE_DIR / "output"
OUTPUT_CSV     = OUTPUT_DIR / "qbank_from_images.csv"

IMAGE_EXTS     = {".png", ".jpg", ".jpeg", ".gif", ".webp", ".bmp", ".tiff"}
CSV_COLUMNS    = [
    "Question_ID",
    "Question_Stem",
    "Options_HTML",
    "Correct_Answer",
    "Explanation_HTML",
    "Image_References",
    "Topic",
]

# Prompt sent to Gemini
GEMINI_PROMPT = (
    "Extract this medical question into CSV row format with these exact columns: "
    "Question_ID, Question_Stem, Options_HTML, Correct_Answer, "
    "Explanation_HTML, Image_References, Topic. "
    "Use valid HTML tags (<p>, <b>, <table>, <tr>, <td>, <th>) in the fields. "
    "Wrap every field value in double quotes and escape any internal double quotes by doubling them. "
    "For Options_HTML, list choices A-F as <b>A.</b> text, separated by <br>. "
    "For Image_References, list any image references as <img src='...' />. "
    "If a field is empty, output an empty string (two consecutive double quotes). "
    "Output ONLY the CSV row — no extra text, no markdown fences, no explanations."
)

# Rate limit: Gemini free tier allows ~15 req/min → add 5s delay
RATE_LIMIT_DELAY = 5  # seconds


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------
def find_images(directory: Path) -> list[Path]:
    """Return sorted list of image files in *directory*."""
    if not directory.exists():
        return []
    files = [f for f in directory.iterdir()
             if f.is_file() and f.suffix.lower() in IMAGE_EXTS]
    return sorted(files, key=lambda x: x.name)


def get_api_key() -> str:
    """Retrieve Gemini API key from env, .env file, or prompt the user."""
    key = os.environ.get("GEMINI_API_KEY")
    if key:
        return key

    # Check .env file
    env_file = BASE_DIR / ".env"
    if env_file.exists():
        for line in env_file.read_text(encoding="utf-8").splitlines():
            if line.strip().startswith("GEMINI_API_KEY="):
                key = line.strip().split("=", 1)[1].strip().strip('"').strip("'")
                if key:
                    os.environ["GEMINI_API_KEY"] = key
                    return key

    # Prompt user
    key = input("Enter your Gemini API key (from aistudio.google.com): ").strip()
    if not key:
        print("No API key provided. Exiting.")
        sys.exit(1)
    os.environ["GEMINI_API_KEY"] = key
    return key


def init_gemini(api_key: str):
    """Initialise the Google Generative AI client."""
    try:
        import google.generativeai as genai
        genai.configure(api_key=api_key)
        model = genai.GenerativeModel("gemini-1.5-flash")
        return model, genai
    except ImportError:
        print("google-generativeai not installed. Run: pip install google-generativeai")
        sys.exit(1)


def encode_image(path: Path) -> dict:
    """Encode an image file for the Gemini API (inline data)."""
    img_bytes = path.read_bytes()
    mime = "image/png"
    ext = path.suffix.lower()
    if ext in (".jpg", ".jpeg"):
        mime = "image/jpeg"
    elif ext == ".gif":
        mime = "image/gif"
    elif ext == ".webp":
        mime = "image/webp"
    elif ext == ".bmp":
        mime = "image/bmp"
    return {"mime_type": mime, "data": base64.b64encode(img_bytes).decode("utf-8")}


# ---------------------------------------------------------------------------
# Response parsing
# ---------------------------------------------------------------------------
def parse_gemini_csv(response_text: str) -> dict:
    """Parse a single CSV row returned by Gemini into a dict."""
    reader = csv.reader([response_text.strip()])
    row = next(reader, [])

    # Pad / truncate to match columns
    while len(row) < len(CSV_COLUMNS):
        row.append("")
    row = row[:len(CSV_COLUMNS)]

    return dict(zip(CSV_COLUMNS, row))


def process_image(model, img_path: Path, img_index: int) -> dict | None:
    """Send one image to Gemini and return a parsed row dict."""
    print(f"  >> [{img_index}] Processing: {img_path.name}")
    try:
        img_data = encode_image(img_path)
        response = model.generate_content(
            contents=[
                GEMINI_PROMPT,
                img_data,
            ],
            generation_config={
                "temperature": 0.1,
                "max_output_tokens": 4096,
            },
        )
        text = response.text.strip()
        row = parse_gemini_csv(text)

        # If Question_ID is empty, assign a sequential one
        if not row.get("Question_ID"):
            row["Question_ID"] = img_index
        print(f"     OK (ID: {row.get('Question_ID', '?')})")
        return row

    except Exception as exc:
        print(f"     ERROR: {exc}")
        return None


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------
def main() -> None:
    ui.banner("I M A G E   P R O C E S S O R", "Gemini 1.5 Flash extractor")
    ui.section("INPUT")

    images = find_images(INPUT_IMG_DIR)
    if not images:
        ui.warning("No image files found in ./input_images/")
        ui.info("Place screenshots there and re-run, or use pdf_processor.py for PDFs.")
        return

    ui.info(f"Found {len(images)} image(s) to process.\n")

    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

    api_key = get_api_key()
    model, _ = init_gemini(api_key)

    results = []
    for idx, img_path in enumerate(images, start=1):
        ui.progress_bar(idx - 1, len(images), "Extracting", suffix=img_path.name[:30])
        row = process_image(model, img_path, idx)
        if row is not None:
            results.append(row)
        if idx < len(images):
            ui.info(f"  rate-limit pause ({RATE_LIMIT_DELAY}s) ...")
            time.sleep(RATE_LIMIT_DELAY)
    ui.progress_bar(len(images), len(images), "Done", suffix="")

    # Write CSV
    with open(OUTPUT_CSV, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=CSV_COLUMNS, quoting=csv.QUOTE_ALL)
        writer.writeheader()
        for row in results:
            writer.writerow(row)

    ui.section("RESULT")
    ui.success(f"Processed: {len(results)} / {len(images)} images successfully")
    ui.status("Output CSV", "./output/qbank_from_images.csv")
    print()


if __name__ == "__main__":
    main()