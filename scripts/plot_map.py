#!/usr/bin/env python3
"""Plot an x, y, z table as a colour map.

    python scripts/plot_map.py config/plot.yaml
    python scripts/plot_map.py config/plot.yaml --input other.csv --output output/other
    python scripts/plot_map.py data.csv                 # defaults, labels from the CSV header
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot  # noqa: E402

import yaml  # noqa: E402

from pdm import Label, MapOptions, Style, plot_map, read_xyz, save  # noqa: E402


def resolve(p, base: Path) -> Path:
    p = Path(p).expanduser()
    return p if p.is_absolute() else (base / p).resolve()


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawTextHelpFormatter)
    ap.add_argument("source", help="plot.yaml config, or an x,y,z table to plot with defaults")
    ap.add_argument("--input", help="x,y,z table (overrides the config)")
    ap.add_argument("--output", help="output name without extension (overrides the config)")
    ap.add_argument("--formats", nargs="+", help="e.g. png pdf")
    ap.add_argument("--dpi", type=int)
    ap.add_argument("--scales", nargs="+", choices=["linear", "log"],
                    help="colour scales to draw, e.g. linear log (overrides the config)")
    args = ap.parse_args(argv)

    src = Path(args.source)
    if src.suffix.lower() in (".yaml", ".yml"):
        cfg = yaml.safe_load(src.read_text()) or {}
        base = src.resolve().parent
    else:
        cfg, base = {"input": str(src.resolve())}, Path.cwd()

    inp = Path(args.input).resolve() if args.input else resolve(cfg["input"], base)
    if args.output:
        out = Path(args.output).resolve()
    elif "output" in cfg:
        out = resolve(cfg["output"], base)
    else:
        out = inp.with_suffix("")
    formats = args.formats or cfg.get("formats", ["png", "tiff", "pdf", "svg"])

    style_cfg = dict(cfg.get("style") or {})
    font = dict(style_cfg.get("font") or {})
    if "dirs" in font:
        font["dirs"] = [str(resolve(d, base)) for d in font["dirs"]]
        style_cfg["font"] = font
    style = Style.from_dict(style_cfg)
    if args.dpi or cfg.get("dpi"):
        style.dpi = args.dpi or cfg["dpi"]

    labels = {k: Label(v.get("name", ""), v.get("unit", "")) if isinstance(v, dict) else v
              for k, v in (cfg.get("labels") or {}).items()}

    scales = args.scales or cfg.get("scales") or [(cfg.get("map") or {}).get("z_scale", "linear")]
    if isinstance(scales, str):
        scales = [scales]

    data = read_xyz(inp)
    for scale in scales:
        opts = MapOptions.from_dict({**(cfg.get("map") or {}), "z_scale": scale})
        mf = plot_map(data, labels, opts, style)
        name = out if scale == "linear" else out.with_name(f"{out.name}_{scale}")
        for p in save(mf, name, formats):
            print(p)
        vmin, vmax = mf.extra["vmin"], mf.extra["vmax"]
        unit = " (log10)" if scale == "log" else ""
        print(f"{scale}: grid {len(data.y)} x {len(data.x)}, colour range {vmin:g} .. {vmax:g}{unit}")
        matplotlib.pyplot.close(mf.fig)


if __name__ == "__main__":
    main()
