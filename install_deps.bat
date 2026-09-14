@echo off
REM ============================================================
REM QBank Automation - Dependency Installer
REM ============================================================
cd /d "%~dp0"
echo.
echo Installing QBank Automation dependencies...
echo This may take several minutes (downloading ML models).
echo.

echo [1/5] Installing pandas, pillow, google-generativeai...
python -m pip install pandas pillow google-generativeai
if errorlevel 1 echo WARNING: Some packages may need manual install.

echo [2/5] Installing marker-pdf (no deps to avoid pillow conflict)...
python -m pip install --no-deps marker-pdf

echo [3/5] Installing lighter marker dependencies...
python -m pip install markdown2 markdownify pdftext scikit-learn

echo [4/5] Installing surya-ocr (no deps)...
python -m pip install --no-deps surya-ocr
python -m pip install opencv-python-headless platformdirs docstring-parser wcwidth

echo [5/5] Installing remaining marker deps...
python -m pip install --no-deps anthropic filetype ftfy psutil rapidfuzz

echo.
echo ============================================================
echo Dependency installation complete!
echo Run: python run_all.py
echo ============================================================
pause