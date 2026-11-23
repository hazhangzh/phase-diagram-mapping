"""Live colour map for Jupyter: add one spectrum at a time while the instrument measures.

    live = LiveMap(x, y_plan=(-1, 2, 0.1), labels={...})
    for v in voltages:
        spectrum = measure(v)          # 1-D array on the x points
        live.add(v, spectrum)          # redraws the map in place
    live.save("output/run1")           # figure files
    live.save_table("output/run1.csv") # x, y, z table (Part 1 contract)
"""
from __future__ import annotations

from pathlib import Path

import numpy as np

from . import plot as _plot
from .io import XYZ, Label
from .style import Style


class LiveMap:
    def __init__(self, x, y_plan=None, labels: dict | None = None,
                 opts: _plot.MapOptions | None = None, style: Style | None = None,
                 display: bool = True):
        """x: the shared x points. y_plan: (start, end, step) or a list of y values; it fixes
        the y-axis range so the map fills in as spectra arrive."""
        self.x = np.asarray(x, dtype=float)
        self._ys: list[float] = []
        self._zs: list[np.ndarray] = []
        self.labels = labels or {}
        self.opts = opts or _plot.MapOptions()
        if y_plan is not None and self.opts.y_range is None:
            if len(y_plan) == 3 and not isinstance(y_plan, np.ndarray):
                start, end, _ = y_plan
                lo, hi = sorted((float(start), float(end)))
            else:
                lo, hi = float(np.min(y_plan)), float(np.max(y_plan))
            self.opts.y_range = (lo, hi)
        self.mf = _plot.make_figure(style)
        self._handle = None
        self._display = display

    # --------------------------------------------------------------- data
    def add(self, y: float, z, redraw: bool = True) -> None:
        z = np.asarray(z, dtype=float)
        if z.shape != self.x.shape:
            raise ValueError(f"spectrum has {z.size} points, x has {self.x.size}")
        self._ys.append(float(y))
        self._zs.append(z)
        if redraw:
            self.redraw()

    @property
    def data(self) -> XYZ:
        order = np.argsort(self._ys)
        xo = np.argsort(self.x)
        z = np.vstack([self._zs[i] for i in order])[:, xo]
        return XYZ(self.x[xo], np.asarray(self._ys)[order], z,
                   {k: (Label.parse(v) if isinstance(v, str) else v)
                    for k, v in self.labels.items()})

    # --------------------------------------------------------------- drawing
    def redraw(self) -> None:
        if len(self._ys) < 2:          # a contour map needs at least two spectra
            return
        _plot.draw(self.mf, self.data, opts=self.opts)
        if not self._display:
            return
        try:
            from IPython.display import display
        except ImportError:
            self.mf.fig.canvas.draw_idle()
            return
        if self._handle is None:
            self._handle = display(self.mf.fig, display_id=True)
        else:
            self._handle.update(self.mf.fig)

    # --------------------------------------------------------------- output
    def save(self, basename, formats=("png", "pdf"), dpi=None):
        return _plot.save(self.mf, basename, formats, dpi)

    def save_table(self, path) -> Path:
        d = self.data
        X, Y = np.meshgrid(d.x, d.y)
        names = [_header(d.labels.get(k), k) for k in "xyz"]
        path = Path(path)
        path.parent.mkdir(parents=True, exist_ok=True)
        np.savetxt(path, np.column_stack([X.ravel(), Y.ravel(), d.z.ravel()]),
                   delimiter=",", header=",".join(names), comments="", fmt="%.10g")
        return path


def _header(lab, default):
    if lab is None:
        return default
    return f"{lab.name} ({lab.unit})" if lab.unit else lab.name
