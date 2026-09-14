#!/usr/bin/env python3
"""
ui.py
=====
Reusable UI helpers for the QBank Automation pipeline.

Provides a consistent, colorful, well-organized CLI interface.
All output is console-encoding safe on Windows via colorama.
"""

from __future__ import annotations

import sys
import threading
import time
from typing import Iterable, Optional

# Ensure console can print Unicode regardless of locale
try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    sys.stderr.reconfigure(encoding="utf-8", errors="replace")
except Exception:
    pass

try:
    import colorama
    colorama.just_fix_windows_console()
    has_colorama = True
except Exception:
    has_colorama = False

# ANSI color codes
RESET = "\033[0m"
BOLD = "\033[1m"
DIM = "\033[2m"

BLACK = "\033[30m"
RED = "\033[31m"
GREEN = "\033[32m"
YELLOW = "\033[33m"
BLUE = "\033[34m"
MAGENTA = "\033[35m"
CYAN = "\033[36m"
WHITE = "\033[37m"
BRIGHT_BLACK = "\033[90m"
BRIGHT_RED = "\033[91m"
BRIGHT_GREEN = "\033[92m"
BRIGHT_YELLOW = "\033[93m"
BRIGHT_BLUE = "\033[94m"
BRIGHT_MAGENTA = "\033[95m"
BRIGHT_CYAN = "\033[96m"
BRIGHT_WHITE = "\033[97m"

BG_RED = "\033[41m"
BG_GREEN = "\033[42m"
BG_YELLOW = "\033[43m"
BG_BLUE = "\033[44m"
BG_MAGENTA = "\033[45m"
BG_CYAN = "\033[46m"
BG_WHITE = "\033[47m"

enable_color = not hasattr(sys.stdout, "isatty") or sys.stdout.isatty() or has_colorama

def banner(title: str, subtitle: str = "", width: int = 68) -> None:
    """Print a beautiful ASCII-art-style banner."""
    print()
    print(c("╔" + "═" * (width - 2) + "╗", CYAN, BOLD))
    pad = (width - 2 - len(title)) // 2
    tline = " " * pad + title + " " * (width - 2 - pad - len(title))
    print(c("║" + tline + "║", CYAN, BOLD))
    if subtitle:
        spad = (width - 2 - len(subtitle)) // 2
        sline = " " * spad + subtitle + " " * (width - 2 - spad - len(subtitle))
        print(c("║" + c(sline, DIM) + "║", CYAN, BOLD))
    print(c("╚" + "═" * (width - 2) + "╝", CYAN, BOLD))
    print()


def section(title: str, width: int = 66) -> None:
    """Print a section header with a horizontal rule."""
    print()
    print(c("┌── " + title, BRIGHT_CYAN, BOLD))
    print(c("│", DIM) + c("─" * (width - 2), DIM))
    print()


def info(msg: str) -> None:
    """Print an info message."""
    print(c("  ℹ ", BRIGHT_BLUE) + " " + msg)


def success(msg: str) -> None:
    """Print a success message."""
    print(c("  ✔ ", BRIGHT_GREEN, BOLD) + " " + msg)


def status(label: str, value: str) -> None:
    """Print a label / value status pair, aligned."""
    print(f"  {c(label.ljust(22), BRIGHT_BLACK)}: {value}")


def card(title: str, description: str = "") -> None:
    """Print a highlighted info card."""
    print()
    w = 68
    print(c("┌" + "─" * (w - 2) + "┐", BRIGHT_CYAN))
    pad = (w - 2 - len(title)) // 2
    print(c("│" + " " * pad + c(title, BRIGHT_WHITE, BOLD)
            + " " * (w - 2 - pad - len(title)) + "│", BRIGHT_CYAN))
    if description:
        for line in description.split("\n"):
            line = line[:w - 4]
            print(c("│ " + line.ljust(w - 4) + " │", BRIGHT_CYAN))
    print(c("└" + "─" * (w - 2) + "┘", BRIGHT_CYAN))
    print()


def progress_bar(
    current: int, total: int,
    label: str = "",
    width: int = 40,
    suffix: str = "",
) -> None:
    """Print a single-line progress bar."""
    if total <= 0:
        total = 1
    ratio = min(1.0, current / total)
    filled = int(width * ratio)
    bar = c("█" * filled, BRIGHT_GREEN) + c("░" * (width - filled), DIM)
    pct = c(f"{int(ratio * 100):3d}%", BRIGHT_YELLOW, BOLD)
    sys.stdout.write(f"\r  {label.ljust(20)} {bar} {pct} {suffix}")
    sys.stdout.flush()
    if current >= total:
        sys.stdout.write("\n")


def table(headers: list[str], rows: Iterable[Iterable], max_col_width: int = 34) -> None:
    """Print a clean aligned table. Headers are bold/cyan, rows aligned."""
    rows = list(rows)
    if not rows:
        print(c("  (no data)", DIM))
        return

    # Compute column widths
    widths = [len(h) for h in headers]

    # Format / truncate cells
    str_rows = []
    for r in rows:
        str_r = []
        for i, cell in enumerate(r):
            s = str(cell) if cell is not None else ""
            s = s.replace("\n", "  ")
            if len(s) > max_col_width:
                s = s[:max_col_width - 3] + "..."
            str_r.append(s)
            if i < len(widths):
                widths[i] = max(widths[i], len(s))
        str_rows.append(str_r)

    fmt = "  │ " + " │ ".join("{:<" + str(w) + "}" for w in widths) + " │"
    top = "  ┌" + "┬".join("─" * (w + 2) for w in widths) + "┐"
    mid = "  ├" + "┼".join("─" * (w + 2) for w in widths) + "┤"
    bot = "  └" + "┴".join("─" * (w + 2) for w in widths) + "┘"

    print(c(top, BRIGHT_CYAN))
    print(fmt.format(*[c(str(h), BRIGHT_CYAN, BOLD) for h in headers]))
    print(c(mid, BRIGHT_CYAN))
    for r in str_rows:
        print(fmt.format(*r))
    print(c(bot, BRIGHT_CYAN))
    print()


class Spinner:
    """Simple thread-based animated spinner for long operations."""

    def __init__(self, message: str = ""):
        self.message = message
        self._stop = False
        self._thread: Optional[threading.Thread] = None
        self._frames = ["⠋", "⠙", "⠹", "⠸", "⠼", "⠴", "⠦", "⠧", "⠇", "⠏"]

    def start(self) -> "Spinner":
        self._stop = False
        self._thread = threading.Thread(target=self._run, daemon=True)
        self._thread.start()
        return self

    def _run(self) -> None:
        i = 0
        while not self._stop:
            frame = self._frames[i % len(self._frames)]
            sys.stdout.write(f"\r  {c(frame, BRIGHT_CYAN)} {self.message}")
            sys.stdout.flush()
            time.sleep(0.1)
            i += 1

    def stop(self, msg: str = "") -> None:
        self._stop = True
        if self._thread:
            self._thread.join(timeout=0.5)
        if msg:
            sys.stdout.write("\r  " + c("✔", BRIGHT_GREEN, BOLD) + " " + msg + "\n")
        else:
            sys.stdout.write("\r" + " " * (len(self.message) + 4) + "\r")
        sys.stdout.flush()
def warning(msg: str) -> None:
    """Print a warning message."""
    print(c("  ⚠ ", BRIGHT_YELLOW, BOLD) + " " + c(msg, BRIGHT_YELLOW))


def error(msg: str) -> None:
    """Print an error message."""
    print(c("  ✖ ", BRIGHT_RED, BOLD) + " " + c(msg, BRIGHT_RED))


def step(num: int, total: int, msg: str) -> None:
    """Print 'Step N/M: ...'"""
    print(c(f"\n  ▌ STEP {num}/{total} ", BG_CYAN, BLACK, BOLD) + " " + c(msg, WHITE, BOLD))

def _colorize(text: str, *codes: str) -> str:
    """Wrap text in ANSI codes if color is enabled."""
    if enable_color:
        return "".join(codes) + text + RESET
    return text


def c(text: str, *codes: str) -> str:
    """Colorize *text* with *codes* (returns raw string, no printing)."""
    return _colorize(text, *codes)