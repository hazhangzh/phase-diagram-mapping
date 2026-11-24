"""Find the raw files and give each one its y value.

File names look like  <step>_<run>_<y><unit>.txt , e.g. 12_1_-4.77961V.txt :
step = index of the step, run = index of the repeated run at that step, y = value at that step
(here the applied gate voltage). The pattern is a regular expression with named groups
`step`, `run` (optional) and `y` (optional when y comes from a start/end/step file).
"""
from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path

import numpy as np

DEFAULT_PATTERN = r"^(?P<step>\d+)_(?P<run>\d+)_(?P<y>[-+]?\d*\.?\d+(?:[eE][-+]?\d+)?)V\.txt$"


@dataclass
class RawFile:
    path: Path
    step: int
    run: int
    y: float | None


def find_files(folder, pattern: str = DEFAULT_PATTERN) -> tuple[list[RawFile], list[str]]:
    """Files in `folder` matching `pattern`, sorted by step then run.

    Returns (matched files, names of other files that were skipped, e.g. background.txt).
    """
    folder = Path(folder)
    if not folder.is_dir():
        raise FileNotFoundError(f"raw-data folder not found: {folder}")
    rx = re.compile(pattern)
    found, skipped = [], []
    for p in sorted(folder.iterdir()):
        if not p.is_file():
            continue
        m = rx.match(p.name)
        if not m:
            if not p.name.endswith(":Zone.Identifier"):   # Windows download tags: ignore silently
                skipped.append(p.name)
            continue
        g = m.groupdict()
        found.append(RawFile(p, int(g["step"]), int(g.get("run") or 1),
                             float(g["y"]) if g.get("y") is not None else None))
    found.sort(key=lambda f: (f.step, f.run))
    return found, skipped


def read_range_file(path) -> tuple[float, float, float]:
    """Read start, end, step from a small text file.

    Accepts either three numbers (on one line or several), or `key value` / `key: value` lines
    with keys start, end, step (any order; other lines and # comments are ignored).
    """
    text = Path(path).read_text()
    keyed = {}
    for ln in text.splitlines():
        ln = ln.split("#", 1)[0].strip()
        m = re.match(r"^(start|end|step)\s*[:=]?\s*([-+]?\d*\.?\d+(?:[eE][-+]?\d+)?)", ln, re.I)
        if m:
            keyed[m.group(1).lower()] = float(m.group(2))
    if len(keyed) == 3:
        return keyed["start"], keyed["end"], keyed["step"]
    nums = [float(v) for v in re.findall(r"[-+]?\d*\.?\d+(?:[eE][-+]?\d+)?",
                                         re.sub(r"#.*", "", text))]
    if len(nums) < 3:
        raise ValueError(f"{path}: need start, end and step")
    return nums[0], nums[1], nums[2]


def range_values(start: float, end: float, step: float) -> np.ndarray:
    """start, start+step, ..., end (inclusive). The sign of step is taken from start -> end."""
    step = abs(step) * (1 if end >= start else -1)
    n = int(round((end - start) / step)) + 1
    return start + step * np.arange(n)


def assign_y(files: list[RawFile], source: str = "filename", range_file=None) -> dict[int, float]:
    """y value for each step index.

    source "filename": the y in each file name (repeated runs at one step share the step's
                       first y; the mean of their y values is used).
    source "range":    start/end/step file; the k-th step (sorted by step index) gets the
                       k-th value. The number of values must equal the number of steps.
    """
    steps = sorted({f.step for f in files})
    if source == "filename":
        ys = {}
        for s in steps:
            vals = [f.y for f in files if f.step == s]
            if any(v is None for v in vals):
                raise ValueError("file-name pattern has no (?P<y>...) group; use y.source: range")
            ys[s] = float(np.mean(vals))
        return ys
    if source == "range":
        if range_file is None:
            raise ValueError("y.source: range needs y.range_file")
        vals = range_values(*read_range_file(range_file))
        if len(vals) != len(steps):
            raise ValueError(f"{range_file}: gives {len(vals)} y values but there are "
                             f"{len(steps)} steps ({steps[0]}..{steps[-1]})")
        return dict(zip(steps, vals.tolist()))
    raise ValueError(f"unknown y source {source!r} (filename or range)")
