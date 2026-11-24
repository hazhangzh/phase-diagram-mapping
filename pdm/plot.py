"""Part 2: draw the x, y, z grid as a filled-contour colour map."""
from __future__ import annotations

from dataclasses import dataclass, field, fields
from decimal import ROUND_HALF_UP, Decimal
from pathlib import Path

import matplotlib.pyplot as plt
import numpy as np
from matplotlib import colormaps
from matplotlib.ticker import AutoMinorLocator, FixedLocator, FuncFormatter, MaxNLocator, MultipleLocator

from . import style as _style
from .io import XYZ, Label

OVER_COLOR = "#808080"    # grey cap: values above the colour range
UNDER_COLOR = "#000000"   # black cap: values below the colour range


@dataclass
class MapOptions:
    cmap: str = "viridis"
    levels: int = 100                 # number of colour levels
    z_scale: str = "linear"           # "linear" or "log" (map shows log10 of z)
    log_floor: float = 1.0            # log scale: z below this (e.g. <= 0) is drawn at the floor
    z_range: tuple | None = None      # manual (min, max) in z units (counts), also for log; None = data min..max
    z_round: float | None = None      # round the auto range out to a multiple of this
    x_range: tuple | None = None      # None = tight to the data
    y_range: tuple | None = None
    x_major: float | None = None      # major tick step; None = automatic
    y_major: float | None = None
    max_major_ticks: int = 9          # upper limit for automatic major ticks
    minor_per_major: int = 1          # minor ticks between two major ticks
    cbar_ticks: int = 9               # evenly spaced colour-bar ticks from min to max
    cbar_tick_mode: str = "exact"     # "exact" (min..max, sig figs) or "nice" (round numbers)
    cbar_sig_figs: int = 4
    cap_frac: float = 0.02            # length of each colour-bar cap, as a fraction of the bar
    rasterize_map: bool = False       # rasterise the map in PDF/SVG (text stays editable)

    @classmethod
    def from_dict(cls, d: dict | None) -> "MapOptions":
        names = {f.name for f in fields(cls)}
        kw = {k: (tuple(v) if isinstance(v, list) else v)
              for k, v in (d or {}).items() if k in names}
        return cls(**kw)


@dataclass
class MapFigure:
    fig: plt.Figure
    ax: plt.Axes
    cax: plt.Axes
    style: _style.Style
    extra: dict = field(default_factory=dict)


# ---------------------------------------------------------------- helpers

def format_sig(v: float, n: int = 4) -> str:
    """Format with n significant figures, keeping trailing zeros: 980 -> '980.0', 6280 -> '6280'."""
    if v == 0 or not np.isfinite(v):
        return "0" if v == 0 else str(v)
    d = Decimal(repr(float(v)))
    exp = d.adjusted()                     # power of ten of the leading digit
    q = Decimal(1).scaleb(exp - n + 1)     # quantum for n significant figures
    r = d.quantize(q, rounding=ROUND_HALF_UP)
    if r.adjusted() > exp:                 # rounding carried into a new digit (999.95 -> 1000)
        r = d.quantize(Decimal(1).scaleb(exp - n + 2), rounding=ROUND_HALF_UP)
    s = format(r, "f")
    return s[1:] if s.startswith("-0") and float(s) == 0 else s


def transform_z(z: np.ndarray, opts: MapOptions) -> np.ndarray:
    """The values that are colour-mapped: z itself, or log10(z) on the log scale."""
    if opts.z_scale == "linear":
        return z
    if opts.z_scale == "log":
        return np.log10(np.maximum(z, opts.log_floor))
    raise ValueError(f"unknown z_scale {opts.z_scale!r} (linear or log)")


def z_limits(z: np.ndarray, opts: MapOptions) -> tuple[float, float]:
    """Colour range for the (already transformed) values z."""
    if opts.z_range is not None:
        lo, hi = float(opts.z_range[0]), float(opts.z_range[1])
        if opts.z_scale == "log":
            lo, hi = np.log10(max(lo, opts.log_floor)), np.log10(max(hi, opts.log_floor))
        return lo, hi
    lo, hi = float(np.nanmin(z)), float(np.nanmax(z))
    if opts.z_round and opts.z_scale == "linear":
        r = float(opts.z_round)
        lo, hi = np.floor(lo / r) * r, np.ceil(hi / r) * r
    if hi <= lo:
        hi = lo + 1.0
    return lo, hi


def make_cmap(name: str):
    return colormaps[name].with_extremes(over=OVER_COLOR, under=UNDER_COLOR, bad="white")


# ---------------------------------------------------------------- figure

def make_figure(style: _style.Style | None = None) -> MapFigure:
    """Empty figure with a square map area and a colour bar on the right.

    The layout is fixed in inches, so the map stays square and the same size whatever the
    labels; saving with bbox_inches='tight' then trims the outer margins.
    """
    style = style or _style.Style()
    _style.apply(style)

    m, w, g = style.map_size, style.cbar_width, style.cbar_gap
    left, bottom, right, top = 1.6, 1.3, 1.6, 0.9      # margins (in), trimmed on save
    W, H = left + m + g + w + right, bottom + m + top
    fig = plt.figure(figsize=(W, H))
    ax = fig.add_axes([left / W, bottom / H, m / W, m / H])
    cax = fig.add_axes([(left + m + g) / W, bottom / H, w / W, m / H])
    return MapFigure(fig, ax, cax, style)


def draw(mf: MapFigure, data: XYZ, labels: dict | None = None,
         opts: MapOptions | None = None) -> MapFigure:
    """Draw (or redraw) the colour map into an existing MapFigure."""
    opts = opts or MapOptions()
    st = mf.style
    ax, cax = mf.ax, mf.cax
    ax.clear()
    cax.clear()

    labels = {**(data.labels or {}), **(labels or {})}
    x, y = np.asarray(data.x), np.asarray(data.y)
    z = transform_z(np.asarray(data.z, dtype=float), opts)
    vmin, vmax = z_limits(z, opts)
    bounds = np.linspace(vmin, vmax, opts.levels + 1)
    cmap = make_cmap(opts.cmap)

    # ---- map: filled contour, no lines, straight from the regular grid
    cs = ax.contourf(x, y, z, levels=bounds, cmap=cmap, extend="both")
    cs.set_edgecolor("face")      # hide hairline seams between levels in PDF viewers
    cs.set_linewidth(0.15)
    if opts.rasterize_map:
        cs.set_rasterized(True)

    ax.set_xlim(*(opts.x_range or (x.min(), x.max())))
    ax.set_ylim(*(opts.y_range or (y.min(), y.max())))
    ax.set_box_aspect(1)

    for axis, step in ((ax.xaxis, opts.x_major), (ax.yaxis, opts.y_major)):
        axis.set_major_locator(MultipleLocator(step) if step else
                               MaxNLocator(nbins=opts.max_major_ticks, steps=[1, 2, 5, 10]))
        if opts.minor_per_major > 0:
            axis.set_minor_locator(AutoMinorLocator(opts.minor_per_major + 1))
    ax.tick_params(which="both", direction="out", top=False, right=False,
                   labelsize=st.tick_size)
    for s in ax.spines.values():
        s.set_linewidth(st.line_width)

    def title(key, default):
        lab = labels.get(key) or Label(default)
        if isinstance(lab, str):
            lab = Label.parse(lab)
        return _style.format_label(lab.name, lab.unit)

    ax.set_xlabel(title("x", "x"), fontsize=st.title_size, labelpad=8)
    ax.set_ylabel(title("y", "y"), fontsize=st.title_size, labelpad=8)

    # ---- colour bar: grey cap on top, black cap at the bottom, title above.
    # Matplotlib shrinks the bar inside cax so that bar + caps span the map height.
    f = opts.cap_frac
    cb = mf.fig.colorbar(cs, cax=cax, extend="both", extendfrac=f, extendrect=True,
                         drawedges=False)
    cb.outline.set_linewidth(st.line_width)
    if opts.cbar_tick_mode == "nice":
        cb.locator = MaxNLocator(nbins=opts.cbar_ticks - 1)
        cb.formatter = FuncFormatter(lambda v, _: f"{v:g}")
    else:
        ticks = np.linspace(vmin, vmax, opts.cbar_ticks)
        cb.locator = FixedLocator(ticks)
        cb.formatter = FuncFormatter(lambda v, _: format_sig(v, opts.cbar_sig_figs))
    cb.update_ticks()
    cb.minorticks_off()
    cax.tick_params(which="both", direction="out", labelsize=st.cbar_tick_size,
                    length=st.major_tick_len, width=st.line_width)
    if opts.z_scale == "log":
        # labels["z_log"] if given, else "Log(<z name>)", e.g. Log(PL)
        zl = labels.get("z_log")
        if zl is None:
            zn = labels.get("z") or Label("z")
            zn = Label.parse(zn) if isinstance(zn, str) else zn
            zl = Label(f"Log({zn.name})")
        ztitle = zl if isinstance(zl, str) else _style.format_label(zl.name, zl.unit)
    else:
        ztitle = title("z", "z")
    cax.set_title(ztitle, fontsize=st.title_size, pad=10)

    mf.extra.update(contour=cs, colorbar=cb, vmin=vmin, vmax=vmax)
    return mf


def plot_map(data: XYZ, labels: dict | None = None, opts: MapOptions | None = None,
             style: _style.Style | None = None) -> MapFigure:
    """One call: figure + colour map. Returns a MapFigure (fig, ax, cax)."""
    return draw(make_figure(style), data, labels, opts)


def save(mf: MapFigure, basename, formats=("png", "tiff", "pdf", "svg"),
         dpi: int | None = None) -> list[Path]:
    """Save as basename.<fmt> for every format. Raster formats use `dpi` (default 600)."""
    basename = Path(basename)
    basename.parent.mkdir(parents=True, exist_ok=True)
    dpi = dpi or mf.style.dpi
    out = []
    for fmt in formats:
        fmt = fmt.lower().lstrip(".")
        p = basename.with_suffix(f".{fmt}")
        kw = {"dpi": dpi, "bbox_inches": "tight", "pad_inches": 0.15}
        if fmt in ("tif", "tiff"):
            kw["pil_kwargs"] = {"compression": "tiff_lzw"}
        mf.fig.savefig(p, format="tiff" if fmt == "tif" else fmt, **kw)
        out.append(p)
    return out
