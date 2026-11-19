"""
Airship Terminal UI & Styling Engine.
Zero-dependency, high-performance CLI renderer with ANSI styling,
Unicode box-drawing, dynamic tables, progress indicators, and badges.
"""

import os
import re
import sys
import shutil
from typing import List, Dict, Any, Optional, Tuple, Sequence

# Detect color capability
def _supports_color() -> bool:
    if os.environ.get("NO_COLOR") is not None:
        return False
    if os.environ.get("TERM") == "dumb":
        return False
    if not hasattr(sys.stdout, "isatty"):
        return False
    return sys.stdout.isatty()


USE_COLOR = _supports_color()

# ANSI Escape Sequences
class Ansi:
    RESET = "\033[0m"
    BOLD = "\033[1m"
    DIM = "\033[2m"
    ITALIC = "\033[3m"
    UNDERLINE = "\033[4m"

    # Standard colors
    BLACK = "\033[30m"
    RED = "\033[31m"
    GREEN = "\033[32m"
    YELLOW = "\033[33m"
    BLUE = "\033[34m"
    MAGENTA = "\033[35m"
    CYAN = "\033[36m"
    WHITE = "\033[37m"

    # Bright / 256 colors
    BRIGHT_BLACK = "\033[90m"  # Dark Gray
    BRIGHT_RED = "\033[91m"
    BRIGHT_GREEN = "\033[92m"
    BRIGHT_YELLOW = "\033[93m"
    BRIGHT_BLUE = "\033[94m"
    BRIGHT_MAGENTA = "\033[95m"
    BRIGHT_CYAN = "\033[96m"
    BRIGHT_WHITE = "\033[97m"

    # Custom 256 color palette
    BRAND_CYAN = "\033[38;5;45m"
    BRAND_SKY = "\033[38;5;39m"
    BRAND_PURPLE = "\033[38;5;141m"
    SUCCESS_EMERALD = "\033[38;5;48m"
    WARN_AMBER = "\033[38;5;214m"
    DANGER_CORAL = "\033[38;5;197m"
    MUTED_GRAY = "\033[38;5;244m"
    BORDER_GRAY = "\033[38;5;240m"


ANSI_REGEX = re.compile(r"\x1b\[[0-9;]*[a-zA-Z]")


def strip_ansi(text: str) -> str:
    """Return text with ANSI escape sequences removed."""
    return ANSI_REGEX.sub("", str(text))


def visible_len(text: str) -> int:
    """Return visible width of string ignoring ANSI escape sequences."""
    return len(strip_ansi(text))


def color(text: Any, code: str) -> str:
    """Wrap text in ANSI code if color is enabled."""
    s = str(text)
    if not USE_COLOR:
        return s
    return f"{code}{s}{Ansi.RESET}"


# Quick color helpers
def c_bold(text: Any) -> str:
    return color(text, Ansi.BOLD)


def c_dim(text: Any) -> str:
    return color(text, Ansi.DIM)


def c_cyan(text: Any, bold: bool = False) -> str:
    return color(text, (Ansi.BOLD + Ansi.BRAND_CYAN) if bold else Ansi.BRAND_CYAN)


def c_sky(text: Any, bold: bool = False) -> str:
    return color(text, (Ansi.BOLD + Ansi.BRAND_SKY) if bold else Ansi.BRAND_SKY)


def c_purple(text: Any, bold: bool = False) -> str:
    return color(text, (Ansi.BOLD + Ansi.BRAND_PURPLE) if bold else Ansi.BRAND_PURPLE)


def c_green(text: Any, bold: bool = False) -> str:
    return color(text, (Ansi.BOLD + Ansi.SUCCESS_EMERALD) if bold else Ansi.SUCCESS_EMERALD)


def c_yellow(text: Any, bold: bool = False) -> str:
    return color(text, (Ansi.BOLD + Ansi.WARN_AMBER) if bold else Ansi.WARN_AMBER)


def c_red(text: Any, bold: bool = False) -> str:
    return color(text, (Ansi.BOLD + Ansi.DANGER_CORAL) if bold else Ansi.DANGER_CORAL)


def c_gray(text: Any) -> str:
    return color(text, Ansi.MUTED_GRAY)


def c_border(text: Any) -> str:
    return color(text, Ansi.BORDER_GRAY)


def badge(label: str, style: str = "cyan") -> str:
    """Return a stylized badge: [ LABEL ]."""
    color_map = {
        "cyan": (Ansi.BRAND_CYAN, Ansi.BOLD),
        "sky": (Ansi.BRAND_SKY, Ansi.BOLD),
        "green": (Ansi.SUCCESS_EMERALD, Ansi.BOLD),
        "yellow": (Ansi.WARN_AMBER, Ansi.BOLD),
        "red": (Ansi.DANGER_CORAL, Ansi.BOLD),
        "purple": (Ansi.BRAND_PURPLE, Ansi.BOLD),
        "gray": (Ansi.MUTED_GRAY, ""),
    }
    col, weight = color_map.get(style, (Ansi.BRAND_CYAN, Ansi.BOLD))
    if not USE_COLOR:
        return f"[{label}]"
    bracket = f"{Ansi.MUTED_GRAY}"
    return f"{bracket}[{Ansi.RESET}{col}{weight} {label} {Ansi.RESET}{bracket}]{Ansi.RESET}"


def badge_pass() -> str:
    return badge("PASS", style="green")


def badge_fail() -> str:
    return badge("FAIL", style="red")


def badge_info(text: str) -> str:
    return badge(text, style="cyan")


def badge_warn(text: str) -> str:
    return badge(text, style="yellow")


def format_score(score: float, is_reward: bool = False) -> str:
    """Format floating point score with color scale."""
    if is_reward:
        txt = f"{score:+.4f}" if score != 0.0 else " 0.0000"
        if score > 0.5:
            return c_green(txt, bold=True)
        elif score > 0.0:
            return c_green(txt)
        elif score == 0.0:
            return c_gray(txt)
        elif score > -0.5:
            return c_yellow(txt)
        else:
            return c_red(txt, bold=True)
    else:
        txt = f"{score:.3f}"
        if score >= 0.90:
            return c_green(txt, bold=True)
        elif score >= 0.50:
            return c_yellow(txt)
        elif score > 0.0:
            return c_red(txt)
        else:
            return c_gray(txt)


# Terminal width utility
def get_term_width(default: int = 80, max_w: int = 100) -> int:
    try:
        w = shutil.get_terminal_size((default, 24)).columns
        return min(w, max_w)
    except Exception:
        return default


def divider(title: str = "", width: Optional[int] = None, char: str = "─", color_code: str = Ansi.BORDER_GRAY) -> str:
    """Render a clean horizontal divider."""
    w = width or get_term_width()
    if not title:
        line = char * w
        return color(line, color_code)
    t = f" {title.strip()} "
    t_len = visible_len(t)
    if t_len >= w - 4:
        return color(f"── {title} ", color_code)
    left_len = 4
    right_len = max(0, w - left_len - t_len)
    left_part = char * left_len
    right_part = char * right_len
    return f"{color(left_part, color_code)}{c_bold(t)}{color(right_part, color_code)}"


def print_banner():
    """Print the official Airship ASCII banner with styling."""
    raw_banner = [
        "    ___    ____ ____  _____ __  __________ ",
        "   /   |  /  _// __ \\/ ___// / / /  _/ __ \\",
        "  / /| |  / / / /_/ /\\__ \\/ /_/ // // /_/ /",
        " / ___ |_/ / / _, _/___/ / __  // // ____/ ",
        "/_/  |_/___//_/ |_|/____/_/ /_/___//_/     ",
    ]
    colors = [
        Ansi.BRAND_CYAN,
        Ansi.BRAND_SKY,
        Ansi.BRAND_PURPLE,
        Ansi.BRAND_PURPLE,
        Ansi.BRAND_SKY,
    ]
    w = get_term_width()
    print()
    for line, col in zip(raw_banner, colors):
        padding = max(0, (w - len(line)) // 2)
        print(" " * padding + color(line, col + Ansi.BOLD))
    
    sub = "FINANCIAL STATEMENT AUDITOR RL ENVIRONMENT"
    sub_pad = max(0, (w - len(sub) - 4) // 2)
    print(" " * sub_pad + c_dim("──[ ") + c_cyan(sub, bold=True) + c_dim(" ]──"))
    
    meta = f"Gymnasium API  •  Bit-Exact Deterministic  •  100-Step Budget"
    meta_pad = max(0, (w - len(meta)) // 2)
    print(" " * meta_pad + c_gray(meta))
    print()


def render_panel(
    content: str,
    title: str = "",
    subtitle: str = "",
    width: Optional[int] = None,
    border_color: str = Ansi.BORDER_GRAY,
    title_color: str = Ansi.BRAND_CYAN,
    padding: int = 1,
) -> str:
    """Render content inside a sleek rounded box."""
    raw_lines = content.strip("\n").split("\n")
    max_line_len = max((visible_len(l.rstrip()) for l in raw_lines), default=20)
    title_len = visible_len(title) + 4 if title else 0
    sub_len = visible_len(subtitle) + 4 if subtitle else 0
    needed_inner = max(max_line_len, title_len, sub_len)

    term_w = get_term_width(default=80, max_w=105)
    if width is not None:
        w = width
    else:
        w = min(term_w, needed_inner + 2 + (padding * 2))

    inner_w = max(10, w - 2 - (padding * 2))
    
    formatted_lines: List[str] = []
    for line in raw_lines:
        line_clean = line.rstrip()
        vis = visible_len(line_clean)
        if vis <= inner_w:
            formatted_lines.append(line_clean + " " * (inner_w - vis))
        else:
            formatted_lines.append(line_clean[:inner_w])

    pad_spaces = " " * padding
    border_col = border_color if USE_COLOR else ""
    reset_col = Ansi.RESET if USE_COLOR else ""

    top_border = "╭"
    if title:
        title_styled = f" {title.strip()} "
        t_len = visible_len(title_styled)
        if t_len < inner_w:
            left_w = 2
            right_w = max(0, (w - 2) - left_w - t_len)
            top_border += "─" * left_w + (title_color + Ansi.BOLD if USE_COLOR else "") + title_styled + reset_col + border_col + "─" * right_w
        else:
            top_border += "─" * (w - 2)
    else:
        top_border += "─" * (w - 2)
    top_border += "╮"

    bottom_border = "╰"
    if subtitle:
        sub_styled = f" {subtitle.strip()} "
        s_len = visible_len(sub_styled)
        if s_len < inner_w:
            right_w = 3
            left_w = max(0, (w - 2) - right_w - s_len)
            bottom_border += "─" * left_w + (Ansi.MUTED_GRAY if USE_COLOR else "") + sub_styled + reset_col + border_col + "─" * right_w
        else:
            bottom_border += "─" * (w - 2)
    else:
        bottom_border += "─" * (w - 2)
    bottom_border += "╯"

    res = [f"{border_col}{top_border}{reset_col}"]
    for l in formatted_lines:
        res.append(f"{border_col}│{reset_col}{pad_spaces}{l}{pad_spaces}{border_col}│{reset_col}")
    res.append(f"{border_col}{bottom_border}{reset_col}")

    return "\n".join(res)


def print_panel(
    content: str,
    title: str = "",
    subtitle: str = "",
    width: Optional[int] = None,
    border_color: str = Ansi.BORDER_GRAY,
    title_color: str = Ansi.BRAND_CYAN,
    padding: int = 1,
):
    print(render_panel(content, title, subtitle, width, border_color, title_color, padding))


def render_table(
    headers: Sequence[str],
    rows: Sequence[Sequence[Any]],
    alignments: Optional[Sequence[str]] = None,
    border_color: str = Ansi.BORDER_GRAY,
    header_color: str = Ansi.BRAND_CYAN,
    title: str = "",
) -> str:
    """Render a clean Unicode table with aligned columns."""
    if not headers:
        return ""

    n_cols = len(headers)
    aligns = list(alignments) if alignments else ["<"] * n_cols
    while len(aligns) < n_cols:
        aligns.append("<")

    # Calculate column widths
    col_widths = [visible_len(h) for h in headers]
    for row in rows:
        for idx, cell in enumerate(row):
            if idx < n_cols:
                col_widths[idx] = max(col_widths[idx], visible_len(str(cell)))

    # Extra padding per column
    col_widths = [w + 2 for w in col_widths]

    def format_cell(val: Any, width: int, align: str) -> str:
        s = str(val)
        vlen = visible_len(s)
        pad = max(0, width - vlen)
        if align == ">":
            return " " * (pad - 1) + s + " "
        elif align == "^":
            left_pad = pad // 2
            right_pad = pad - left_pad
            return " " * left_pad + s + " " * right_pad
        else:
            return " " + s + " " * (pad - 1)

    b_col = border_color if USE_COLOR else ""
    h_col = (header_color + Ansi.BOLD) if USE_COLOR else ""
    rst = Ansi.RESET if USE_COLOR else ""

    # Box characters
    top = f"{b_col}┌" + "┬".join("─" * w for w in col_widths) + f"┐{rst}"
    hdr_div = f"{b_col}├" + "┼".join("─" * w for w in col_widths) + f"┤{rst}"
    bottom = f"{b_col}└" + "┴".join("─" * w for w in col_widths) + f"┘{rst}"

    header_cells = [format_cell(h, col_widths[i], aligns[i]) for i, h in enumerate(headers)]
    header_row = f"{b_col}│{rst}" + f"{b_col}│{rst}".join(f"{h_col}{hc}{rst}" for hc in header_cells) + f"{b_col}│{rst}"

    lines = []
    if title:
        lines.append(c_bold(f"  ● {title}"))
    lines.append(top)
    lines.append(header_row)
    lines.append(hdr_div)

    for row in rows:
        cells = []
        for i in range(n_cols):
            cell_val = row[i] if i < len(row) else ""
            cells.append(format_cell(cell_val, col_widths[i], aligns[i]))
        row_str = f"{b_col}│{rst}" + f"{b_col}│{rst}".join(cells) + f"{b_col}│{rst}"
        lines.append(row_str)

    lines.append(bottom)
    return "\n".join(lines)


def print_table(
    headers: Sequence[str],
    rows: Sequence[Sequence[Any]],
    alignments: Optional[Sequence[str]] = None,
    border_color: str = Ansi.BORDER_GRAY,
    header_color: str = Ansi.BRAND_CYAN,
    title: str = "",
):
    print(render_table(headers, rows, alignments, border_color, header_color, title))


def render_progress_bar(current: int, total: int, width: int = 24, label: str = "") -> str:
    """Render a sleek block progress bar."""
    if total <= 0:
        pct = 1.0
    else:
        pct = min(1.0, max(0.0, current / total))
    filled_len = int(width * pct)
    empty_len = width - filled_len
    bar = f"{Ansi.SUCCESS_EMERALD}{'━' * filled_len}{Ansi.RESET}{Ansi.MUTED_GRAY}{'╺' if empty_len > 0 and filled_len > 0 else ' '}{'─' * max(0, empty_len - 1)}{Ansi.RESET}"
    percent_str = f"{int(pct * 100):>3}%"
    count_str = f"[{current}/{total}]"
    return f"{c_cyan(count_str)} {bar} {c_bold(percent_str)} {c_gray(label)}"


def print_step_header(step_num: int, title: str, action_type: str = ""):
    """Print a visually distinct header for episode steps."""
    tag = badge(f"STEP {step_num}", style="purple" if step_num == 0 else "sky")
    action_styled = f" ❯ {c_bold(action_type)}" if action_type else ""
    print(f"\n{tag} {c_bold(title)}{action_styled}")
    print(divider(width=68))


def print_key_value(pairs: Sequence[Tuple[str, Any]], label_width: int = 24):
    """Print aligned key-value attributes."""
    for key, val in pairs:
        k = f"{key:<{label_width}}"
        print(f"  {c_gray(k)} {c_cyan('→')}  {c_bold(str(val))}")


def print_score_card(metrics: Dict[str, Any], reward: float, terminated: bool, truncated: bool):
    """Render a high-impact audit evaluation score card."""
    tp = metrics.get("tp", 0)
    fp = metrics.get("fp", 0)
    fn = metrics.get("fn", 0)
    p = metrics.get("precision", 0.0)
    r = metrics.get("recall", 0.0)
    f1 = metrics.get("f1", 0.0)

    # Status tag
    if terminated and f1 >= 0.99:
        verdict = f"{Ansi.SUCCESS_EMERALD}{Ansi.BOLD}AUDIT SUCCESSFUL (PERFECT MATCH){Ansi.RESET}"
    elif terminated:
        verdict = f"{Ansi.WARN_AMBER}{Ansi.BOLD}AUDIT COMPLETED (PARTIAL FINDINGS){Ansi.RESET}"
    else:
        verdict = f"{Ansi.DANGER_CORAL}{Ansi.BOLD}AUDIT TRUNCATED (BUDGET EXHAUSTED){Ansi.RESET}"

    card_content = (
        f"Verdict              : {verdict}\n"
        f"True Positives (TP)  : {c_green(tp, bold=True)}\n"
        f"False Positives (FP) : {c_red(fp, bold=True) if fp > 0 else c_gray(fp)}\n"
        f"False Negatives (FN) : {c_red(fn, bold=True) if fn > 0 else c_gray(fn)}\n"
        f"{c_border('─' * 46)}\n"
        f"Precision (P)        : {format_score(p)}\n"
        f"Recall (R)           : {format_score(r)}\n"
        f"F1-Score             : {format_score(f1)}\n"
        f"Terminal Reward (R)  : {format_score(reward, is_reward=True)}\n"
        f"Episode Status       : terminated={terminated}, truncated={truncated}"
    )

    border = Ansi.SUCCESS_EMERALD if f1 >= 0.99 else (Ansi.WARN_AMBER if f1 >= 0.3 else Ansi.DANGER_CORAL)
    print_panel(
        card_content,
        title="AUDIT EVALUATION & SCORING VERDICT",
        subtitle=f"Reward: {reward:+.4f}",
        border_color=border,
        title_color=Ansi.BRAND_CYAN,
        width=70,
    )
