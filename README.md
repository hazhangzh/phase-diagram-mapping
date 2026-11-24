# phase-diagram-mapping

Turns a set of spectra measured against a second parameter (gate voltage, field, …) into a
2D colour map in the style of an Origin contour plot.

```
raw files ──[Part 1: pdm.build]──► x, y, z table ──[Part 2: pdm.plot]──► colour map
```

The 3-column **x, y, z table** is the fixed contract between the two parts. Part 1 (raw
spectrometer files → table) depends on how a project stores its data; Part 2 is shared.

## Setup

```bash
git clone git@github.com:hazhangzh/phase-diagram-mapping.git
cd phase-diagram-mapping
python3 -m venv .venv
.venv/bin/pip install -r requirements.txt
```

If `python3 -m venv` fails because `ensurepip` is missing (Debian/Ubuntu without
`python3-venv`), run `python3 -m venv --without-pip .venv` and then
`pip --python .venv/bin/python install -r requirements.txt`.

## Part 1: raw files → x, y, z table

```bash
.venv/bin/python scripts/build_xyz.py config/my_run.build.local.yaml          # table, then the map
.venv/bin/python scripts/build_xyz.py config/my_run.build.local.yaml --no-plot
```

Copy [config/build.yaml](config/build.yaml) to a `*.local.yaml` file (git-ignored) and set the
paths. The expected raw layout:

```
<run>/
├── xvector.txt              x points, one per line (e.g. wavelength in nm)
└── map/
    ├── 1_1_-5.00004V.txt    <step index>_<run index>_<y value>V.txt
    ├── 2_1_-4.98004V.txt    one line per x point; each line may hold several values
    ├── ...                  (one per CCD row), tab/space/comma separated, no header
    └── 1_background.txt     other names are skipped and listed
```

- **x**: from `xvector.txt`; the number of lines in every raw file must match. `x.convert:
  nm_to_eV` turns wavelength into photon energy (E = 1239.84 / λ).
- **y**: from the file names (`y.source: filename`), or from a start/end/step file
  (`y.source: range`), matched to the files in order of step index; the counts must agree.
- **z**: the CCD-row columns of each line are combined (`raw.combine`: `mean` by default,
  `sum`, `median` or one column). Optional: `cosmic_ray_sigma` removes cosmic-ray spikes first,
  `background` subtracts a raw file (combined the same way), `repeats` combines several runs at
  one step. The background must be a dark spectrum (laser off); check it before use.
- **Output**: CSV (or `.xlsx`) with a `Name (unit)` header, sorted by y and then x (both
  ascending), one row per point. Two steps with the same y are an error (e.g. a forward and
  backward sweep must be split first).
- Raw data only: no smoothing, no background or cosmic-ray removal unless you turn it on.

Another raw format (e.g. two columns x, z per file) is `raw.format: xz`; a new format goes in
[pdm/build/readers.py](pdm/build/readers.py).

## Part 2: plot from the command line

```bash
.venv/bin/python scripts/plot_map.py config/plot.yaml
```

This plots the synthetic example [examples/synthetic_PL.csv](examples/synthetic_PL.csv) to
`output/synthetic_PL.{png,tiff,pdf,svg}`: PNG/TIFF at 600 dpi, and PDF/SVG with editable text
(TrueType fonts in the PDF, `<text>` elements in the SVG).

For your own data, copy `config/plot.yaml` to e.g. `config/my_run.local.yaml` (git-ignored),
change `input` and `output`, and run it. Or override on the command line:

```bash
.venv/bin/python scripts/plot_map.py config/plot.yaml --input my_table.csv --output output/my_run
.venv/bin/python scripts/plot_map.py my_table.csv --formats png    # defaults, labels from the header
```

All settings are in [config/plot.yaml](config/plot.yaml), with a comment on each one.

## Data and privacy

Measurement data is **not** stored in this repository: everything in `examples/` except the
synthetic example is git-ignored. The synthetic table is made by
[examples/make_synthetic.py](examples/make_synthetic.py) and only imitates a gate-dependent PL map.

## Input: the x, y, z table

- Three columns: x, y, z. One row per point, in any order. `.csv`, `.txt`/`.dat` (tab or
  space separated) or `.xlsx`.
- An optional header row such as `Energy (eV),Gate Voltage (V),PL (counts)` gives the default
  titles: `Name (unit)` is split into name and unit.
- Every y value must have the same x points (a regular grid). Any line endings work
  (`\n`, `\r\n`, or old-Mac `\r`).

## What the map looks like

| Item | Setting |
|---|---|
| Map | Filled contour, no lines, from the grid without interpolation; 100 viridis levels |
| Colour range | data min to max, or `z_range: [min, max]`; above → grey cap, below → black cap |
| Colour bar | right side, title on top, 9 evenly spaced labels from the exact data min to max with 4 significant figures (`991.0`, `1651`, …) |
| Axes | frame on all sides, outward major ticks plus one minor tick on the left and bottom, tight to the data |
| Titles | `Name (unit)`, unit in italic; mathtext allowed (`$V_\mathrm{g}$`, `cm^{-1}`, `\mu{}m`) |
| Fonts | Arial for now; 22 pt titles, 18 pt tick labels, 14 pt colour-bar labels |
| Shape | square 6 × 6 in map area |

If ever needed, `z_round: 20` rounds the colour range out to multiples of 20, as Origin does.

### Log scale

`scales: [linear, log]` in the plot config (or `--scales linear log`) draws both maps: the
linear one as `<output>.*` and the log one as `<output>_log.*`. The log map colours
log10(z); the colour-bar title is `Log(<z name>)`, e.g. Log(PL), or `labels.z_log`. Values
below `log_floor` (default 1, e.g. counts ≤ 0 after background subtraction) are drawn at the
floor. `z_range` is still given in counts. Raw counts carry the detector offset (~1100), which
squeezes the log map; subtract a dark spectrum to make it informative.

### Fonts

Fonts are looked up in `fonts/` first, then `/mnt/c/Windows/Fonts` (WSL), then the system.
Font files are not in the repository (licensing). To switch to Helvetica, copy its regular,
italic and bold files into `fonts/` and set `style.font.family: Helvetica` in the config.
Italic units and math symbols use the same files. If the font is missing, DejaVu Sans is used
with a warning.

## Python / Jupyter

```python
from pdm import read_xyz, plot_map, save, MapOptions, Label

data = read_xyz("examples/synthetic_PL.csv")
mf = plot_map(data, labels={"y": Label(r"$V_\mathrm{g}$", "V")}, opts=MapOptions())
save(mf, "output/my_map", formats=["png", "pdf"])
```

Live mode adds one spectrum at a time while a measurement runs. The map redraws in the notebook:

```python
from pdm import LiveMap
live = LiveMap(x, y_plan=(-1, 2, 0.1), labels={"x": "Energy (eV)", "y": "Gate Voltage (V)", "z": "PL (counts)"})
for v in voltages:
    live.add(v, measure_spectrum(v))
live.save("output/run1")
live.save_table("output/run1.csv")    # x, y, z table
```

See [notebooks/example.ipynb](notebooks/example.ipynb).

## Layout

```
config/build.yaml         Part 1 settings (template)
config/plot.yaml          Part 2 plot settings (template, points at the synthetic example)
config/*.local.yaml       your own configs (git-ignored)
pdm/build/readers.py      raw text files → one spectrum each (CCD rows combined, x conversion)
pdm/build/y_sources.py    find files by name pattern, y from names or a start/end/step file
pdm/build/base.py         build_xyz (sorted grid) and write_table
scripts/build_xyz.py      Part 1 command line (optionally plots the result)
pdm/io.py                 read table → regular grid (XYZ), header → labels
pdm/style.py              fonts, sizes, rcParams, italic-unit labels
pdm/plot.py               make_figure / draw / plot_map / save
pdm/live.py               LiveMap for Jupyter
scripts/plot_map.py       Part 2 command line
examples/                 synthetic example table and its generator
fonts/                    font files you supply (git-ignored)
notebooks/example.ipynb   plotting and live mode
tests/                    .venv/bin/python -m pytest
```

## Still open

- Helvetica font files (then change `font.family`).
- Large maps (hundreds of spectra) give big PDF/SVG files; `rasterize_map: true` keeps them
  small with the text still editable.
