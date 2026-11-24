"""Read raw spectrometer text files and reduce each one to a single spectrum."""
from __future__ import annotations

import warnings
from pathlib import Path

import numpy as np
from numpy.lib.stride_tricks import sliding_window_view

H_C_EV_NM = 1239.841984   # h*c in eV*nm: E (eV) = 1239.84 / wavelength (nm)


def read_matrix(path) -> np.ndarray:
    """Read a header-less numeric text file (tab, comma or space separated; any line endings)
    into a 2-D array: one row per line, one column per value on the line."""
    with open(path, newline=None) as fh:
        lines = [ln for ln in fh.read().splitlines() if ln.strip()]
    if not lines:
        raise ValueError(f"{path}: empty file")
    rows = [ln.replace(",", " ").split() for ln in lines]
    ncol = len(rows[0])
    if any(len(r) != ncol for r in rows):
        raise ValueError(f"{path}: lines have different numbers of values")
    return np.array(rows, dtype=float)


def read_x(path) -> np.ndarray:
    """x points from a one-column file (e.g. xvector.txt), or the first column of a table."""
    a = read_matrix(path)
    return a[:, 0] if a.ndim == 2 else a


# ------------------------------------------------------------------ combine CCD rows

def _running_median(a, k):
    pad = np.pad(a, [(k, k)] + [(0, 0)] * (a.ndim - 1), mode="edge")
    return np.median(sliding_window_view(pad, 2 * k + 1, axis=0), axis=-1)


def _robust_sigma(r, floor=1.0):
    s0 = np.maximum(1.4826 * np.median(np.abs(r), axis=0, keepdims=True), max(floor, 0.5))
    keep = np.abs(r) < 5 * s0
    s = np.sqrt(np.sum(np.where(keep, r ** 2, 0), axis=0, keepdims=True)
                / np.maximum(np.sum(keep, axis=0, keepdims=True), 1))
    return np.maximum(s, floor)


def reject_cosmic_rays(a: np.ndarray, sigma: float, k: int = 3) -> tuple[np.ndarray, int]:
    """Mark cosmic-ray pixels as NaN.

    A cosmic ray is a sharp spike in one CCD row, `sigma` noise levels above a running median
    along the spectrum (2k+1 points). PL peaks are much wider and are not touched. The spike
    and its two spectral neighbours are set to NaN. Returns (array, number of spikes).
    """
    smooth = _running_median(a, k)
    r = a - smooth
    hit = r > sigma * _robust_sigma(r)
    bad = hit | np.roll(hit, 1, 0) | np.roll(hit, -1, 0)
    return np.where(bad, np.nan, a), int(hit.sum())


def combine_columns(a: np.ndarray, method="mean", cosmic_ray_sigma: float | None = None):
    """Reduce an (n_points x n_ccd_rows) matrix to one spectrum.

    method: "mean" | "sum" | "median" | an integer column index (0-based).
    cosmic_ray_sigma: if set, cosmic-ray pixels are left out first (see reject_cosmic_rays);
    "sum" is then the mean times the number of columns, so the scale stays the same.
    Returns (spectrum, number of cosmic-ray spikes removed).
    """
    a = np.asarray(a, dtype=float)
    if a.ndim == 1:
        a = a[:, None]
    if isinstance(method, int) and not isinstance(method, bool):
        return a[:, method], 0
    n_cr = 0
    raw = a
    if cosmic_ray_sigma:
        a, n_cr = reject_cosmic_rays(a, cosmic_ray_sigma)
    with warnings.catch_warnings():
        warnings.simplefilter("ignore", RuntimeWarning)
        if method == "mean":
            z = np.nanmean(a, axis=1)
        elif method == "sum":
            z = np.nanmean(a, axis=1) * a.shape[1]
        elif method == "median":
            z = np.nanmedian(a, axis=1)
        else:
            raise ValueError(f"unknown combine method {method!r} (mean, sum, median or a column index)")
    if np.isnan(z).any():   # every row rejected on a line (very unlikely): use the raw median
        z = np.where(np.isnan(z), np.median(raw, axis=1), z)
    return z, n_cr


# ------------------------------------------------------------------ raw formats

def read_spectrum(path, fmt: str, x_shared: np.ndarray | None, combine="mean",
                  cosmic_ray_sigma=None) -> tuple[np.ndarray, np.ndarray, int]:
    """Read one raw file. Returns (x, z, number of cosmic rays removed).

    fmt "z_only": the file has z values only (one line per x point, one or more CCD-row
                  columns); x comes from the shared x file.
    fmt "xz":     first column is x, the remaining column(s) are z.
    """
    a = read_matrix(path)
    if fmt == "z_only":
        if x_shared is None:
            raise ValueError("format z_only needs an x file (raw.x_file)")
        if len(a) != len(x_shared):
            raise ValueError(f"{Path(path).name}: {len(a)} lines but the x file has "
                             f"{len(x_shared)} points")
        x, zcols = x_shared, a
    elif fmt == "xz":
        if a.shape[1] < 2:
            raise ValueError(f"{Path(path).name}: format xz needs at least 2 columns")
        x, zcols = a[:, 0], a[:, 1:]
    else:
        raise ValueError(f"unknown raw format {fmt!r} (z_only or xz)")
    z, n_cr = combine_columns(zcols, combine, cosmic_ray_sigma)
    return x, z, n_cr


def convert_x(x: np.ndarray, conversion: str | None) -> np.ndarray:
    """Optional unit conversion of the x axis: None, "nm_to_eV" (or "eV_to_nm", same formula)."""
    if not conversion:
        return x
    if conversion in ("nm_to_eV", "eV_to_nm"):
        return H_C_EV_NM / x
    if conversion in ("nm_to_meV",):
        return 1000 * H_C_EV_NM / x
    raise ValueError(f"unknown x conversion {conversion!r}")
