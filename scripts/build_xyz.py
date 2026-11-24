#!/usr/bin/env python3
"""Part 1: raw spectra -> sorted x, y, z table (and optionally the colour map).

    python scripts/build_xyz.py config/build.yaml
    python scripts/build_xyz.py config/build.yaml --plot config/plot.yaml
    python scripts/build_xyz.py config/build.yaml --no-plot
"""
from __future__ import annotations

import argparse
import sys
import time
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent))
sys.path.insert(0, str(HERE))

import yaml  # noqa: E402

from pdm.build import BuildOptions, build_xyz, write_table  # noqa: E402


def resolve(p, base: Path):
    if p is None:
        return None
    p = Path(p).expanduser()
    return str(p if p.is_absolute() else (base / p).resolve())


def options_from_config(cfg: dict, base: Path) -> BuildOptions:
    raw, y, x = cfg.get("raw") or {}, cfg.get("y") or {}, cfg.get("x") or {}
    d = {
        "folder": resolve(raw["folder"], base),
        "format": raw.get("format", "z_only"),
        "x_file": resolve(raw.get("x_file"), base),
        "combine": raw.get("combine", "mean"),
        "cosmic_ray_sigma": raw.get("cosmic_ray_sigma"),
        "repeats": raw.get("repeats", "mean"),
        "background": resolve(raw.get("background"), base),
        "y_source": y.get("source", "filename"),
        "range_file": resolve(y.get("range_file"), base),
        "x_convert": x.get("convert"),
    }
    if raw.get("pattern"):
        d["pattern"] = raw["pattern"]
    if cfg.get("labels"):
        d["labels"] = cfg["labels"]
    return BuildOptions.from_dict(d)


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawTextHelpFormatter)
    ap.add_argument("config", help="build.yaml")
    ap.add_argument("--output", help="table file (.csv/.xlsx), overrides the config")
    ap.add_argument("--plot", help="plot config; draws the map from the new table")
    ap.add_argument("--no-plot", action="store_true", help="only write the table")
    args = ap.parse_args(argv)

    cfg_path = Path(args.config).resolve()
    cfg = yaml.safe_load(cfg_path.read_text()) or {}
    base = cfg_path.parent
    opts = options_from_config(cfg, base)

    t0 = time.time()
    data, rep = build_xyz(opts)
    out = Path(args.output).resolve() if args.output else Path(resolve(cfg.get("output", "xyz_table.csv"), base))
    write_table(data, out)
    print(rep.summary())
    print(f"x: {data.x.size} points, {data.x[0]:.6g} .. {data.x[-1]:.6g}; "
          f"y: {data.y.size} values, {data.y[0]:.6g} .. {data.y[-1]:.6g}; "
          f"z: {data.z.min():.6g} .. {data.z.max():.6g}")
    print(f"table: {out}  ({time.time() - t0:.1f} s)")

    plot_cfg = args.plot or (None if args.no_plot else resolve(cfg.get("plot"), base))
    if plot_cfg and not args.no_plot:
        import plot_map
        plot_map.main([plot_cfg, "--input", str(out)])


if __name__ == "__main__":
    main()
