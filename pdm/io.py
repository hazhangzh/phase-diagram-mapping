"""Read an x, y, z table (the contract between Part 1 and Part 2) and turn it into a grid."""
from __future__ import annotations

import csv
import re
from dataclasses import dataclass, field
from pathlib import Path

import numpy as np


@dataclass
class Label:
    """An axis or colour-bar title: a name and an optional unit.

    Both may contain matplotlib mathtext, e.g. name="$V_\\mathrm{g}$", unit="cm^{-1}".
    The unit is drawn in italic (see pdm.style.format_label).
    """
    name: str
    unit: str = ""

    @classmethod
    def parse(cls, text: str) -> "Label":
        """Split a header such as 'Energy (eV)' into name='Energy', unit='eV'."""
        m = re.match(r"^\s*(.*?)\s*\(([^()]*)\)\s*$", text)
        return cls(m.group(1), m.group(2)) if m else cls(text.strip(), "")


@dataclass
class XYZ:
    """A regular grid: z[i, j] is the value at y[i], x[j]. x and y are ascending."""
    x: np.ndarray
    y: np.ndarray
    z: np.ndarray
    labels: dict = field(default_factory=dict)   # keys "x", "y", "z" -> Label


def read_table(path) -> tuple[np.ndarray, list[str]]:
    """Read a 3-column table. Returns (N x 3 array, header names or [])."""
    path = Path(path)
    suffix = path.suffix.lower()
    if suffix in (".xlsx", ".xlsm"):
        from openpyxl import load_workbook
        ws = load_workbook(path, read_only=True, data_only=True).active
        rows = [r[:3] for r in ws.iter_rows(values_only=True) if r and r[0] is not None]
        header = []
        if rows and isinstance(rows[0][0], str):
            header, rows = [str(v) for v in rows[0]], rows[1:]
        return np.asarray(rows, dtype=float), header

    # Text: newline=None handles \n, \r\n and old-Mac \r line endings alike.
    with open(path, newline=None, encoding="utf-8-sig") as fh:
        text = fh.read()
    lines = [ln for ln in text.splitlines() if ln.strip()]
    delim = "," if "," in lines[0] else ("\t" if "\t" in lines[0] else None)

    def split(ln):
        return next(csv.reader([ln], delimiter=delim)) if delim else ln.split()

    header = []
    try:
        float(split(lines[0])[0])
    except ValueError:
        header, lines = [h.strip() for h in split(lines[0])], lines[1:]
    data = np.array([[float(v) for v in split(ln)[:3]] for ln in lines])
    if data.ndim != 2 or data.shape[1] != 3:
        raise ValueError(f"{path}: expected 3 columns (x, y, z), got shape {data.shape}")
    return data, header


def to_grid(data: np.ndarray, rtol: float = 1e-6) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    """Arrange x, y, z rows into a regular grid.

    Rows are grouped by y. Every y must have the same set of x points (the spectra share
    one x axis); small float differences between spectra are tolerated.
    """
    x_all, y_all, z_all = data.T
    scale = max(np.ptp(y_all), np.abs(y_all).max(), 1.0)
    y_key = np.round(y_all / (scale * 1e-9)).astype(np.int64)
    keys, inverse = np.unique(y_key, return_inverse=True)

    x_ref = None
    y = np.empty(len(keys))
    rows = []
    for i in range(len(keys)):
        sel = inverse == i
        xs, zs = x_all[sel], z_all[sel]
        order = np.argsort(xs)
        xs, zs = xs[order], zs[order]
        if x_ref is None:
            x_ref = xs
        elif len(xs) != len(x_ref) or not np.allclose(xs, x_ref, rtol=rtol, atol=0):
            raise ValueError(
                f"y = {y_all[sel][0]:g}: x points differ from the first spectrum "
                f"({len(xs)} vs {len(x_ref)} points). Part 2 needs a regular grid.")
        y[i] = y_all[sel].mean()
        rows.append(zs)
    return x_ref, y, np.vstack(rows)


def read_xyz(path) -> XYZ:
    """Read an x, y, z table file into a gridded XYZ, with labels from the header."""
    data, header = read_table(path)
    x, y, z = to_grid(data)
    labels = {k: Label.parse(h) for k, h in zip("xyz", header)} if len(header) >= 3 else {}
    return XYZ(x, y, z, labels)
