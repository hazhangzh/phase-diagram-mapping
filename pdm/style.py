"""Fonts, sizes and label formatting for the colour map."""
from __future__ import annotations

import warnings
from dataclasses import dataclass, field
from pathlib import Path

import matplotlib as mpl
from matplotlib import font_manager as fm

PROJECT_ROOT = Path(__file__).resolve().parent.parent

# Searched in order for the font files. Put Helvetica (or any font) files in fonts/.
DEFAULT_FONT_DIRS = [PROJECT_ROOT / "fonts", Path("/mnt/c/Windows/Fonts")]


@dataclass
class Style:
    font_family: str = "Arial"
    font_dirs: list = field(default_factory=lambda: list(DEFAULT_FONT_DIRS))
    title_size: float = 22        # axis and colour-bar titles (pt)
    tick_size: float = 18         # axis tick labels (pt)
    cbar_tick_size: float = 14    # colour-bar tick labels (pt)
    map_size: float = 4.5         # side of the square map area (inches)
    cbar_width: float = 0.30      # colour-bar width (inches)
    cbar_gap: float = 0.75        # gap between map and colour bar (inches)
    line_width: float = 1.0       # frame and tick line width (pt)
    major_tick_len: float = 6.0
    minor_tick_len: float = 3.5
    dpi: int = 600

    @classmethod
    def from_dict(cls, d: dict | None) -> "Style":
        d = dict(d or {})
        font = d.pop("font", {}) or {}
        sizes = font.get("size", {}) or {}
        kw = {k: v for k, v in d.items() if k in cls.__dataclass_fields__}
        if "family" in font:
            kw["font_family"] = font["family"]
        if "dirs" in font:
            kw["font_dirs"] = [Path(p) for p in font["dirs"]]
        for key, attr in (("title", "title_size"), ("tick", "tick_size"),
                          ("cbar_tick", "cbar_tick_size")):
            if key in sizes:
                kw[attr] = sizes[key]
        return cls(**kw)


def register_font(family: str, dirs) -> bool:
    """Register every font file of `family` found in `dirs` with matplotlib.

    Returns True if the family is usable (already installed or found in dirs).
    """
    found = False
    for d in dirs:
        d = Path(d)
        if not d.is_dir():
            continue
        for p in d.iterdir():
            if p.suffix.lower() not in (".ttf", ".otf", ".ttc"):
                continue
            try:
                if fm.get_font(str(p)).family_name.lower() == family.lower():
                    fm.fontManager.addfont(str(p))
                    found = True
            except Exception:
                continue
        if found:
            break
    if not found:
        try:
            fm.findfont(fm.FontProperties(family=family), fallback_to_default=False)
            found = True
        except ValueError:
            pass
    return found


def apply(style: Style) -> None:
    """Set matplotlib rcParams for the map. Call before creating the figure."""
    family = style.font_family
    if not register_font(family, style.font_dirs):
        warnings.warn(f"Font '{family}' not found in {[str(d) for d in style.font_dirs]} "
                      "or the system; falling back to DejaVu Sans.")
        family = "DejaVu Sans"
    mpl.rcParams.update({
        "font.family": family,
        "font.size": style.tick_size,
        # Mathtext (super/subscripts, Greek, italic units) drawn from the same font files.
        "mathtext.fontset": "custom",
        "mathtext.rm": family,
        "mathtext.it": f"{family}:italic",
        "mathtext.bf": f"{family}:bold",
        "mathtext.sf": family,
        "mathtext.cal": family,
        "mathtext.tt": family,
        "axes.linewidth": style.line_width,
        "axes.unicode_minus": False,     # plain hyphen-minus, as in the reference figure
        "xtick.direction": "out", "ytick.direction": "out",
        "xtick.major.size": style.major_tick_len, "ytick.major.size": style.major_tick_len,
        "xtick.minor.size": style.minor_tick_len, "ytick.minor.size": style.minor_tick_len,
        "xtick.major.width": style.line_width, "ytick.major.width": style.line_width,
        "xtick.minor.width": style.line_width, "ytick.minor.width": style.line_width,
        # Editable text in vector output.
        "pdf.fonttype": 42, "ps.fonttype": 42, "svg.fonttype": "none",
        "savefig.dpi": style.dpi,
    })


def _math_escape(s: str) -> str:
    return s.replace(" ", r"\ ")


def format_label(name: str, unit: str = "") -> str:
    """'Energy', 'eV' -> 'Energy ($\\mathit{eV}$)': the unit in italic, brackets upright.

    The unit is mathtext, so 'cm^{-1}', '\\mu m' and 'a_{0}' work. A unit that already
    contains '$' is used exactly as written.
    """
    if not unit:
        return name
    if "$" in unit:
        return f"{name} ({unit})"
    return f"{name} ($\\mathit{{{_math_escape(unit)}}}$)"
