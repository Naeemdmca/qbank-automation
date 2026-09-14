#!/usr/bin/env python3
"""
md_to_csv.py
============
Step 4: Convert Marker-generated Markdown -> final_qbank.csv.

Usage:
    python md_to_csv.py
"""

import re
import csv
from pathlib import Path
import pandas as pd

import ui

BASE_DIR       = Path(__file__).resolve().parent
INPUT_TEMP     = BASE_DIR / "output" / "temp_markdown"
OUTPUT_IMAGES  = BASE_DIR / "output" / "images"
OUTPUT_CSV     = BASE_DIR / "output" / "final_qbank.csv"

CSV_COLUMNS    = [
    "Question_ID", "Question_Stem", "Options_HTML",
    "Correct_Answer", "Explanation_HTML", "Image_References", "Topic",
]


def find_markdown_files():
    if not INPUT_TEMP.exists():
        return []
    return sorted(INPUT_TEMP.rglob("*.md"))


def normalise_image_path(src):
    filename = Path(src).name
    return f"output/images/{filename}"


def extract_image_refs(content):
    refs = []
    img_tag_pattern = r'<img[^>]+src=["\']([^"\']+)["\'][^>]*>'
    for m in re.finditer(img_tag_pattern, content, re.IGNORECASE):
        refs.append(f"<img src='{normalise_image_path(m.group(1))}' />")
    md_img_pattern = r'!\[([^\]]*)\]\(([^)]+)\)'
    for m in re.finditer(md_img_pattern, content):
        refs.append(f"<img src='{normalise_image_path(m.group(2))}' />")
    seen = set()
    unique = []
    for r in refs:
        if r not in seen:
            seen.add(r)
            unique.append(r)
    return ", ".join(unique)



def md_bold_to_html(text):
    return re.sub(r'\*\*(.+?)\*\*', r'<b>\1</b>', text)


def md_table_to_html(lines):
    html_parts = ["<table>"]
    rows = []
    for line in lines:
        cells = [c.strip() for c in line.split("|")]
        if cells and cells[0] == "":
            cells = cells[1:]
        if cells and cells[-1] == "":
            cells = cells[:-1]
        if not cells:
            continue
        if all(re.match(r'^[-:|=]+$', c) for c in cells):
            continue
        rows.append(cells)
    for i, cells in enumerate(rows):
        tag = "th" if i == 0 else "td"
        cell_tags = "".join(f"<{tag}>{md_bold_to_html(c)}</{tag}>" for c in cells)
        html_parts.append(f"  <tr>{cell_tags}</tr>")
    html_parts.append("</table>")
    return "\n".join(html_parts)


def md_to_html(text):
    img_placeholders = {}
    img_counter = [0]

    def _protect_img(match):
        key = f"__IMG_{img_counter[0]}__"
        img_placeholders[key] = match.group(0)
        img_counter[0] += 1
        return key

    def _convert_md_img(match):
        src = match.group(2)
        return f"<img src='{normalise_image_path(src)}' />"

    text = re.sub(r'!\[([^\]]*)\]\(([^)]+)\)', _convert_md_img, text)
    # Convert markdown images ![]() to <img> with normalized paths

    text = re.sub(r'<img[^>]*>', _protect_img, text)

    lines = text.split("\n")
    result_lines = []
    table_lines = []
    in_table = False

    for line in lines:
        stripped = line.strip()
        if stripped.startswith("|") and "|" in stripped:
            table_lines.append(line)
            in_table = True
        else:
            if in_table:
                result_lines.append("[TABLE]")
                result_lines.append("\n".join(table_lines))
                result_lines.append("[/TABLE]")
                table_lines = []
                in_table = False
            result_lines.append(line)
    if in_table:
        result_lines.append("[TABLE]")
        result_lines.append("\n".join(table_lines))
        result_lines.append("[/TABLE]")

    processed = "\n".join(result_lines)

    table_html_placeholders = {}
    table_counter = [0]

    def _convert_table(match):
        table_lines_list = match.group(1).strip().split("\n")
        table_html = md_table_to_html(table_lines_list)
        key = f"__TABLE_{table_counter[0]}__"
        table_html_placeholders[key] = table_html
        table_counter[0] += 1
        return key

    processed = re.sub(r'\[TABLE\](.*?)\[/TABLE\]', _convert_table, processed, flags=re.DOTALL)

    paragraphs = re.split(r'\n\s*\n', processed.strip())
    html_paragraphs = []

    for para in paragraphs:
        para = para.strip()
        if not para:
            continue
        para = md_bold_to_html(para)
        if re.fullmatch(r'__TABLE_\d+__', para):
            html_paragraphs.append(para)
        else:
            para = para.replace("\n", "<br>\n")
            html_paragraphs.append(f"<p>{para}</p>")

    result = "\n".join(html_paragraphs)

    for key, table_html in table_html_placeholders.items():
        result = result.replace(key, table_html)
    for key, img_tag in img_placeholders.items():
        result = result.replace(key, img_tag)

    return result



QUESTION_HEADER_RE = re.compile(
    r'^#*\s*(?:Item|Question|Q)\s*(\d+)\s*$',
    re.MULTILINE | re.IGNORECASE
)

OPTION_RE = re.compile(
    r'^[ \t]*\**\s*([A-F])\.\**\s+(.*)$',
    re.MULTILINE
)

CORRECT_ANSWER_RE = re.compile(
    r'Correct answer:\s*([A-F])',
    re.IGNORECASE
)

CHOICE_RE = re.compile(
    r'\(Choice\s*([A-F])\)',
    re.IGNORECASE
)

EXPLANATION_HEADER_RE = re.compile(
    r'^##*\s*Explanation',
    re.MULTILINE | re.IGNORECASE
)


def split_questions(content):
    matches = list(QUESTION_HEADER_RE.finditer(content))
    if not matches:
        return [("1", content)]
    questions = []
    for i, match in enumerate(matches):
        start = match.end()
        end = matches[i + 1].start() if i + 1 < len(matches) else len(content)
        qid = match.group(1)
        block = content[start:end].strip()
        questions.append((qid, block))
    return questions


def parse_question(qid, block):
    exp_match = EXPLANATION_HEADER_RE.search(block)
    if exp_match:
        before_explanation = block[:exp_match.start()]
        explanation_md = block[exp_match.end():]
    else:
        before_explanation = block
        explanation_md = ""

    correct_match = CORRECT_ANSWER_RE.search(before_explanation)
    if not correct_match:
        correct_match = CORRECT_ANSWER_RE.search(block)

    choice_matches = CHOICE_RE.findall(explanation_md) if explanation_md else []

    if correct_match:
        correct_answer = correct_match.group(1).upper()
    elif choice_matches:
        correct_answer = choice_matches[-1].upper()
    else:
        correct_answer = ""

    before_explanation = CORRECT_ANSWER_RE.sub("", before_explanation)
    before_explanation = CHOICE_RE.sub("", before_explanation)

    option_matches = list(OPTION_RE.finditer(before_explanation))
    options_html = ""
    if option_matches:
        option_parts = []
        for m in option_matches:
            letter = m.group(1).upper()
            text_part = m.group(2).strip()
            text_part = md_bold_to_html(text_part)
            option_parts.append(f"<b>{letter}.</b> {text_part}")
        options_html = " <br> ".join(option_parts)

    if option_matches:
        stem_end = option_matches[0].start()
    else:
        stem_end = len(before_explanation)

    stem_text = before_explanation[:stem_end].strip()
    stem_text = EXPLANATION_HEADER_RE.sub("", stem_text)
    stem_html = md_to_html(stem_text)

    explanation_html = md_to_html(explanation_md)
    image_refs = extract_image_refs(block)
    topic = ""

    return {
        "Question_ID": qid,
        "Question_Stem": stem_html,
        "Options_HTML": options_html,
        "Correct_Answer": correct_answer,
        "Explanation_HTML": explanation_html,
        "Image_References": image_refs,
        "Topic": topic,
    }


def main():
    ui.banner("M A R K D O W N   ->   C S V", "Smart Markdown Parser")
    ui.section("INPUT")

    md_files = find_markdown_files()
    if not md_files:
        ui.error("No Markdown files found in ./output/temp_markdown/")
        ui.info("Run pdf_processor.py first, or place .md files there manually.")
        return

    ui.info(f"Found {len(md_files)} markdown file(s).")
    print()

    all_rows = []
    for md_file in md_files:
        try:
            content = md_file.read_text(encoding="utf-8")
            questions = split_questions(content)
            ui.info(f"Parsing {md_file.name} ({len(questions)} question(s))")
            for qid, block in questions:
                row = parse_question(qid, block)
                all_rows.append(row)
                ui.success(f"  Question {qid} parsed")
        except Exception as exc:
            ui.error(f"{md_file.name}: {exc}")
        print()

    if not all_rows:
        ui.warning("No questions were extracted.")
        return

    df = pd.DataFrame(all_rows, columns=CSV_COLUMNS)
    df.to_csv(OUTPUT_CSV, index=False, quoting=csv.QUOTE_ALL)

    ui.section("RESULT")
    ui.success(f"Processed {len(all_rows)} question(s)")
    ui.status("Output CSV", "./output/final_qbank.csv")
    ui.status("Images", "./output/images/")
    print()

    ui.table(["Question_ID", "Correct", "Options", "Image Ref"],
             [(r["Question_ID"], r["Correct_Answer"] or "-",
               str(len([x for x in (r.get("Options_HTML") or "").split("<br>") if x.strip()])),
               "yes" if r["Image_References"] else "no") for r in all_rows[:10]])


if __name__ == "__main__":
    main()
