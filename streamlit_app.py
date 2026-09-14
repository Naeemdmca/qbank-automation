#!/usr/bin/env python3
"""streamlit_app.py - Browser frontend for QBank Automation.
Run:  python -m streamlit run streamlit_app.py"""
from __future__ import annotations
import os, sys, time
from pathlib import Path
import streamlit as st

BASE_DIR = Path(__file__).resolve().parent
INPUT_PDF_DIR = BASE_DIR / "input_pdfs"
INPUT_IMG_DIR = BASE_DIR / "input_images"
OUTPUT_TEMP = BASE_DIR / "output" / "temp_markdown"
OUTPUT_IMAGES = BASE_DIR / "output" / "images"
OUTPUT_DIR = BASE_DIR / "output"
FINAL_CSV = OUTPUT_DIR / "final_qbank.csv"

for d in (INPUT_PDF_DIR, INPUT_IMG_DIR, OUTPUT_TEMP, OUTPUT_IMAGES, OUTPUT_DIR):
    d.mkdir(parents=True, exist_ok=True)

st.set_page_config(page_title="QBank Automation", page_icon="\u2695\ufe0f", layout="wide", initial_sidebar_state="expanded")

st.markdown(
    """
    <style>
    .stApp { background: #f0f2f6; }
    .hero { text-align: center; padding: 2rem 1rem;
        background: linear-gradient(135deg, #1e3c72 0%, #2a5298 50%, #1e3c72 100%);
        border-radius: 0.75rem; margin-bottom: 1.5rem; }
    .hero h1 { color: white; margin: 0; font-size: 2.2rem; }
    .hero p  { color: #c9d6e5; margin: 0.5rem 0 0; }
    .section-h { font-size: 1.15rem; font-weight: 700; color: #1e3c72;
        border-left: 4px solid #2a5298; padding-left: 0.6rem; }
    .stat-card { background: white; border-radius: 0.5rem; padding: 1rem;
        text-align: center; box-shadow: 0 1px 6px rgba(0,0,0,0.08); }
    .stat-card .num { font-size: 2rem; font-weight: 800; color: #1e3c72; }
    .stat-card .lbl { font-size: 0.8rem; color: #666; }
    .file-item { background: white; border-radius: 0.4rem; padding: 0.5rem 0.8rem;
        border-left: 3px solid #2a5298; }
    .download-area { background: white; border-radius: 0.5rem; padding: 1.5rem;
        text-align: center; border: 2px dashed #2a5298; }
    footer { visibility: hidden; }
    </style>
    """,
    unsafe_allow_html=True,
)

st.markdown(
    '<div class="hero"><h1>\u2695\ufe0f QBank Automation</h1>'
    '<p>Extract UWorld medical questions from PDFs or screenshots</p></div>',
    unsafe_allow_html=True,
)

# Sidebar
with st.sidebar:
    st.markdown("### \u2699\ufe0f Settings")
    api_key = st.text_input(
        "\U0001f511 Gemini API Key",
        type="password",
        help="Only needed for screenshot extraction.",
    )
    if api_key:
        os.environ["GEMINI_API_KEY"] = api_key
        st.success("Key set \u2705")
    st.markdown("---")
    st.markdown("### \U0001f4c1 Input Folders")
    with st.expander("\U0001f4c4 PDFs"):
        pdfs = sorted(INPUT_PDF_DIR.glob("*.pdf")) if INPUT_PDF_DIR.exists() else []
        for pf in pdfs:
            st.markdown(f"`{pf.name}`")
        if not pdfs:
            st.caption("Empty")
    with st.expander("\U0001f5bc\ufe0f Images"):
        ie = ("*.png", "*.jpg", "*.jpeg", "*.gif", "*.webp", "*.bmp")
        imgs = sorted(f for ext in ie for f in INPUT_IMG_DIR.glob(ext)) if INPUT_IMG_DIR.exists() else []
        for imf in imgs:
            st.markdown(f"`{imf.name}`")
        if not imgs:
            st.caption("Empty")
    st.markdown("---")
    st.markdown("### \U0001f4ca Output")
    if FINAL_CSV.exists():
        st.success(f"final_qbank.csv ({FINAL_CSV.stat().st_size / 1024:.1f} KB)")
    else:
        st.caption("No output yet")

# Main layout
col_up, col_run = st.columns([3, 1])
with col_up:
    st.markdown('<div class="section-h">\U0001f4e4 Upload Files</div>', unsafe_allow_html=True)
    uploaded = st.file_uploader(
        "Drag & drop PDFs or screenshots",
        accept_multiple_files=True,
        type=["pdf", "png", "jpg", "jpeg", "gif", "webp", "bmp"],
        label_visibility="collapsed",
    )
if uploaded:
    with st.spinner("Saving..."):
        for upf in uploaded:
            target_dir = INPUT_IMG_DIR if upf.type and upf.type.startswith("image/") else INPUT_PDF_DIR
            (target_dir / upf.name).write_bytes(upf.read())
            st.markdown(f'<div class="file-item">\u2705 {upf.name}</div>', unsafe_allow_html=True)
with col_run:
    st.markdown('<div class="section-h">&nbsp;</div>', unsafe_allow_html=True)
    run_clicked = st.button("\U0001f680 Run Extraction", type="primary", use_container_width=True)

# Processing
if run_clicked:
    pdf_files = sorted(INPUT_PDF_DIR.glob("*.pdf"))
    ie = ("*.png", "*.jpg", "*.jpeg", "*.gif", "*.webp", "*.bmp")
    img_files = sorted(f for ext in ie for f in INPUT_IMG_DIR.glob(ext))
    if not pdf_files and not img_files:
        st.error("\u274c No PDFs or images found. Upload files first!")
        st.stop()
    st.markdown("---")
    c1, c2, c3, c4 = st.columns(4)
    c1.markdown(f'<div class="stat-card"><div class="num">{len(pdf_files)}</div><div class="lbl">PDFs</div></div>', unsafe_allow_html=True)
    c2.markdown(f'<div class="stat-card"><div class="num">{len(img_files)}</div><div class="lbl">Images</div></div>', unsafe_allow_html=True)
    c3.markdown('<div class="stat-card"><div class="num">\u2014</div><div class="lbl">Stage</div></div>', unsafe_allow_html=True)
    c4.markdown('<div class="stat-card"><div class="num">\u23f3</div><div class="lbl">Status</div></div>', unsafe_allow_html=True)
    progress_bar = st.progress(0)
    status_text = st.empty()
    log_area = st.expander("\U0001f4cb Processing Log", expanded=True)
    total_steps = (1 if pdf_files else 0) + (1 if img_files and not pdf_files else 0) + 1
    step = 0
    with log_area:
        # Stage 1: PDF -> Markdown
        if pdf_files:
            step += 1
            progress_bar.progress(int(step * 100 // max(total_steps, 1)))
            status_text.info(f"\U0001f4c4 Stage {step}: Converting {len(pdf_files)} PDF(s)...")
            try:
                from pdf_processor import process_single_pdf, find_marker_command
                marker_cmd = find_marker_command()
                if marker_cmd is None:
                    status_text.error("\u274c marker_single not found")
                    st.stop()
                ok, fail = 0, 0
                for pf in pdf_files:
                    try:
                        if process_single_pdf(pf, marker_cmd):
                            ok += 1
                            st.success(f"\u2705 {pf.name}")
                        else:
                            fail += 1
                            st.warning(f"\u26a0\ufe0f {pf.name} failed")
                    except Exception as exc:
                        fail += 1
                        st.error(f"\u274c {pf.name}: {exc}")
                status_text.success(f"\u2705 PDF stage: {ok}/{len(pdf_files)} succeeded")
            except Exception as exc:
                status_text.error(f"\u274c PDF stage error: {exc}")

        # Stage 2: Markdown -> CSV
        step += 1
        progress_bar.progress(int(step * 100 // max(total_steps, 1)))
        md_files = sorted(OUTPUT_TEMP.rglob("*.md"))
        if md_files:
            status_text.info(f"\U0001f4dd Stage {step}: Converting {len(md_files)} Markdown file(s)...")
            try:
                from md_to_csv import main as md_main
                md_main()
                status_text.success("\u2705 CSV generated")
            except Exception as exc:
                status_text.error(f"\u274c CSV error: {exc}")
        else:
            status_text.warning("\u26a0\ufe0f No Markdown files found")

        # Stage 3: Images -> CSV (fallback)
        if img_files and not pdf_files:
            step += 1
            progress_bar.progress(int(step * 100 // max(total_steps, 1)))
            status_text.info(f"\U0001f5bc\ufe0f Stage {step}: Processing {len(img_files)} image(s)...")
            if not os.environ.get("GEMINI_API_KEY"):
                status_text.error("\u274c No Gemini API key - paste it in sidebar")
                st.stop()
            try:
                from image_processor import main as img_main
                img_main()
                status_text.success("\u2705 Images processed")
            except Exception as exc:
                status_text.error(f"\u274c Image error: {exc}")
        progress_bar.progress(100)

    # Results
    st.markdown("---")
    st.markdown('<div class="section-h">\U0001f4ca Results</div>', unsafe_allow_html=True)
    if FINAL_CSV.exists():
        csv_content = FINAL_CSV.read_text(encoding="utf-8")
        line_count = len(csv_content.strip().splitlines()) - 1
        st.markdown(
            f'<div class="download-area">'
            f'<p style="font-size:1.1rem;font-weight:600;color:#1e3c72;">'
            f'\U0001f389 {line_count} question(s) extracted!</p>'
            f'<p>File: <code>output/final_qbank.csv</code></p></div>',
            unsafe_allow_html=True,
        )
        st.download_button("\u2b07\ufe0f Download final_qbank.csv", csv_content, "final_qbank.csv", "text/csv", type="primary", use_container_width=True)
        with st.expander("\U0001f441\ufe0f Preview CSV (first 5 rows)"):
            import pandas as pd
            try:
                df = pd.read_csv(FINAL_CSV)
                st.dataframe(df.head(), use_container_width=True)
            except Exception:
                st.text(csv_content[:2000])
    img_count = len(list(OUTPUT_IMAGES.glob("*"))) if OUTPUT_IMAGES.exists() else 0
    if img_count > 0:
        st.info(f"\U0001f5bc\ufe0f **{img_count} image(s)** extracted to `output/images/` - move them to your QBank media directory")
