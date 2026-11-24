"""Part 1: raw files -> sorted x, y, z table."""
from __future__ import annotations

from dataclasses import dataclass, field, fields
from pathlib import Path

import numpy as np

from ..io import XYZ, Label
from . import readers, y_sources


@dataclass
class BuildOptions:
    folder: str                                  # folder with the raw files
    pattern: str = y_sources.DEFAULT_PATTERN     # file-name regex: (?P<step>) (?P<run>) (?P<y>)
    format: str = "z_only"                       # z_only (x from x_file) | xz (first column x)
    x_file: str | None = None                    # e.g. xvector.txt
    combine: object = "mean"                     # CCD-row columns -> one z: mean|sum|median|index
    cosmic_ray_sigma: float | None = None        # e.g. 6 to drop cosmic-ray spikes; None = raw
    repeats: str = "mean"                        # several runs at one step: mean|sum|first|last
    background: str | None = None                # raw file to subtract from every spectrum
    y_source: str = "filename"                   # filename | range
    range_file: str | None = None                # start/end/step file when y_source = range
    x_convert: str | None = None                 # None | nm_to_eV | nm_to_meV
    labels: dict = field(default_factory=lambda: {"x": "x", "y": "y", "z": "z"})

    @classmethod
    def from_dict(cls, d: dict) -> "BuildOptions":
        names = {f.name for f in fields(cls)}
        unknown = set(d) - names
        if unknown:
            raise ValueError(f"unknown build options: {sorted(unknown)}")
        return cls(**d)


@dataclass
class BuildReport:
    n_files: int = 0
    n_steps: int = 0
    runs_per_step: dict = field(default_factory=dict)
    skipped: list = field(default_factory=list)
    cosmic_rays: int = 0
    n_columns: int = 0

    def summary(self) -> str:
        runs = sorted(set(self.runs_per_step.values()))
        s = [f"{self.n_files} raw files, {self.n_steps} steps, "
             f"{'/'.join(map(str, runs))} run(s) per step, {self.n_columns} column(s) per file"]
        if self.cosmic_rays:
            s.append(f"{self.cosmic_rays} cosmic-ray spikes removed")
        if self.skipped:
            s.append(f"skipped (name does not match the pattern): {', '.join(self.skipped)}")
        return "\n".join(s)


def _combine_repeats(zs: list[np.ndarray], how: str) -> np.ndarray:
    if how == "mean":
        return np.mean(zs, axis=0)
    if how == "sum":
        return np.sum(zs, axis=0)
    if how == "first":
        return zs[0]
    if how == "last":
        return zs[-1]
    raise ValueError(f"unknown repeats option {how!r} (mean, sum, first, last)")


def build_xyz(opts: BuildOptions, log=print) -> tuple[XYZ, BuildReport]:
    """Read every raw file and return the grid sorted by y, then x (both ascending)."""
    files, skipped = y_sources.find_files(opts.folder, opts.pattern)
    if not files:
        raise FileNotFoundError(f"no files in {opts.folder} match the pattern {opts.pattern!r}")
    rep = BuildReport(n_files=len(files), skipped=skipped)

    x_shared = readers.read_x(opts.x_file) if opts.x_file else None
    ys = y_sources.assign_y(files, opts.y_source, opts.range_file)

    def read(path):
        return readers.read_spectrum(path, opts.format, x_shared, opts.combine,
                                     opts.cosmic_ray_sigma)

    bg = None
    if opts.background:
        _, bg, _ = read(opts.background)

    x_ref = None
    rows: dict[int, np.ndarray] = {}
    by_step: dict[int, list] = {}
    for f in files:
        by_step.setdefault(f.step, []).append(f)
    for step, group in by_step.items():
        zs = []
        for f in group:
            x, z, n_cr = read(f.path)
            rep.cosmic_rays += n_cr
            if x_ref is None:
                x_ref = x
                rep.n_columns = readers.read_matrix(f.path).shape[1]
            elif len(x) != len(x_ref) or not np.allclose(x, x_ref, rtol=1e-7, atol=0):
                raise ValueError(f"{f.path.name}: x points differ from the first file")
            zs.append(z - bg if bg is not None else z)
        rows[step] = _combine_repeats(zs, opts.repeats)
        rep.runs_per_step[step] = len(group)
    rep.n_steps = len(rows)

    steps = list(rows)
    y = np.array([ys[s] for s in steps])
    dup = [v for v in np.unique(y) if np.sum(y == v) > 1]
    if dup:
        clash = [s for s in steps if ys[s] == dup[0]]
        raise ValueError(f"steps {clash} have the same y = {dup[0]:g}; a colour map needs one "
                         "spectrum per y (e.g. a forward and backward sweep must be split)")

    x = readers.convert_x(np.asarray(x_ref, dtype=float), opts.x_convert)
    z = np.vstack([rows[s] for s in steps])

    # Sort: y ascending (rows), x ascending (columns).
    yo, xo = np.argsort(y, kind="stable"), np.argsort(x, kind="stable")
    labels = {k: Label.parse(v) if isinstance(v, str) else v for k, v in opts.labels.items()}
    return XYZ(x[xo], y[yo], z[yo][:, xo], labels), rep


def write_table(data: XYZ, path, fmt=("%.7g", "%.6g", "%.6g")) -> Path:
    """Write the x, y, z table: header 'Name (unit)', one row per point, y-major order.
    .csv (or .txt) as text; .xlsx through openpyxl."""
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    X, Y = np.meshgrid(data.x, data.y)
    table = np.column_stack([X.ravel(), Y.ravel(), data.z.ravel()])
    header = []
    for k in "xyz":
        lab = data.labels.get(k) or Label(k)
        header.append(f"{lab.name} ({lab.unit})" if lab.unit else lab.name)

    if path.suffix.lower() == ".xlsx":
        from openpyxl import Workbook
        wb = Workbook(write_only=True)
        ws = wb.create_sheet("xyz")
        ws.append(header)
        for r in table.tolist():
            ws.append(r)
        wb.save(path)
    else:
        np.savetxt(path, table, delimiter=",", header=",".join(header), comments="", fmt=list(fmt))
    return path
