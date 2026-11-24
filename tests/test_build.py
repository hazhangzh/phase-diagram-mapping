import sys
from pathlib import Path

import matplotlib

matplotlib.use("Agg")

import numpy as np
import pytest

from pdm import Label, read_xyz
from pdm.build import (BuildOptions, build_xyz, combine_columns, find_files, range_values,
                       read_range_file, write_table)
from pdm.build.readers import H_C_EV_NM

ROOT = Path(__file__).resolve().parent.parent
NM = np.linspace(700.0, 770.0, 50)


def spectrum(v):
    return 1000 + 500 * np.exp(-((NM - 735 - 2 * v) / 3) ** 2)


def make_run(folder: Path, volts, runs=1, ncol=3, crlf=True, step_order=None):
    """Raw files like the spectrometer's: <step>_<run>_<V>V.txt, ncol CCD-row columns, no x."""
    m = folder / "map"
    m.mkdir(parents=True)
    nl = "\r\n" if crlf else "\n"
    (folder / "xvector.txt").write_text(nl.join(f"{v:g}" for v in NM))
    for step, v in zip(step_order or range(1, len(volts) + 1), volts):
        for r in range(1, runs + 1):
            z = spectrum(v)[:, None] + r - 1 + np.zeros(ncol)
            lines = ["\t".join(f"{c:.0f}" for c in row) for row in z]
            (m / f"{step}_{r}_{v:.5f}V.txt").write_text(nl.join(lines) + nl)
    (m / "1_background.txt").write_text(nl.join("\t".join(["7"] * ncol) for _ in NM))
    (m / "target.txt").write_text("")
    (m / "3_1_0.00000V.txt:Zone.Identifier").write_text("[ZoneTransfer]")
    return m


def opts(folder, **kw):
    return BuildOptions(folder=str(folder / "map"), x_file=str(folder / "xvector.txt"),
                        labels={"x": "Energy (eV)", "y": "Gate Voltage (V)", "z": "PL (counts)"},
                        **kw)


def test_find_files_skips_others(tmp_path):
    make_run(tmp_path, [-1.0, 0.0, 1.0])
    files, skipped = find_files(tmp_path / "map")
    assert [f.step for f in files] == [1, 2, 3]
    assert [f.y for f in files] == [-1.0, 0.0, 1.0]
    assert sorted(skipped) == ["1_background.txt", "target.txt"]


def test_build_sorts_y_and_x(tmp_path):
    # Sweep measured from +1 V down to -1 V: step 1 is +1 V. Rows must come out ascending in y.
    make_run(tmp_path, [1.0, 0.5, 0.0, -0.5, -1.0])
    data, rep = build_xyz(opts(tmp_path, x_convert="nm_to_eV"), log=None)
    assert rep.n_steps == 5 and rep.n_columns == 3
    assert np.all(np.diff(data.y) > 0) and np.all(np.diff(data.x) > 0)
    np.testing.assert_allclose(data.x, np.sort(H_C_EV_NM / NM), rtol=1e-5)   # xvector has 6 sig. figs
    np.testing.assert_allclose(data.z[0], spectrum(-1.0)[::-1].round(), atol=0.5)
    assert data.labels["x"] == Label("Energy", "eV")


def test_table_roundtrip_and_plot(tmp_path):
    make_run(tmp_path, [-1.0, 0.0, 1.0])
    data, _ = build_xyz(opts(tmp_path), log=None)
    p = write_table(data, tmp_path / "out" / "t.csv")
    lines = p.read_text().splitlines()
    assert lines[0] == "Energy (eV),Gate Voltage (V),PL (counts)"
    assert len(lines) == 1 + 3 * len(NM)
    back = read_xyz(p)
    np.testing.assert_allclose(back.z, data.z, rtol=1e-5)
    from pdm import plot_map
    plot_map(back)


def test_repeats_and_background(tmp_path):
    make_run(tmp_path, [0.0, 1.0], runs=3)
    data, rep = build_xyz(opts(tmp_path, repeats="mean",
                               background=str(tmp_path / "map" / "1_background.txt")), log=None)
    assert set(rep.runs_per_step.values()) == {3}
    # runs are offset by 0, 1, 2 -> mean +1; background 7 subtracted
    np.testing.assert_allclose(data.z[0], spectrum(0.0).round() + 1 - 7)


def test_y_from_range_file(tmp_path):
    make_run(tmp_path, [9.0, 9.0, 9.0])          # y in names ignored
    rf = tmp_path / "y.txt"
    rf.write_text("start -1\nend 1\nstep 1\n")
    data, _ = build_xyz(opts(tmp_path, y_source="range", range_file=str(rf)), log=None)
    np.testing.assert_allclose(data.y, [-1, 0, 1])
    rf.write_text("-1 2 1")
    with pytest.raises(ValueError, match="4 y values but there are 3 steps"):
        build_xyz(opts(tmp_path, y_source="range", range_file=str(rf)), log=None)


def test_duplicate_y_is_an_error(tmp_path):
    make_run(tmp_path, [0.0, 1.0, 0.0])
    with pytest.raises(ValueError, match="same y"):
        build_xyz(opts(tmp_path), log=None)


def test_line_count_must_match_x(tmp_path):
    m = make_run(tmp_path, [0.0, 1.0])
    (tmp_path / "xvector.txt").write_text("\n".join(map(str, NM[:-1])))
    with pytest.raises(ValueError, match="lines but the x file has"):
        build_xyz(opts(tmp_path), log=None)


def test_combine_and_cosmic_rays():
    a = np.tile(np.linspace(100, 110, 40)[:, None], (1, 5))
    a[20, 2] += 5000                                       # cosmic ray in one CCD row
    z, n = combine_columns(a, "mean")
    assert n == 0 and z[20] > 1000
    z, n = combine_columns(a, "mean", cosmic_ray_sigma=6)
    assert n == 1 and z[20] == pytest.approx(a[20, 0])
    assert combine_columns(a, "sum")[0][0] == pytest.approx(500)
    assert combine_columns(a, 3)[0][20] == a[20, 3]


def test_range_helpers(tmp_path):
    np.testing.assert_allclose(range_values(5, -5, 2.5), [5, 2.5, 0, -2.5, -5])
    f = tmp_path / "r.txt"
    f.write_text("# gate sweep\nstart: -5\nstep: 0.02\nend: 5\n")
    assert read_range_file(f) == (-5, 5, 0.02)


def test_cli_build_and_plot(tmp_path):
    make_run(tmp_path, [-1.0, 0.0, 1.0])
    cfg = tmp_path / "build.yaml"
    cfg.write_text(
        "raw: {folder: map, x_file: xvector.txt}\n"
        "x: {convert: nm_to_eV}\n"
        "labels: {x: Energy (eV), y: Gate Voltage (V), z: PL (counts)}\n"
        "output: out/xyz.csv\n"
        f"plot: {ROOT / 'config' / 'plot.yaml'}\n")
    sys.path.insert(0, str(ROOT / "scripts"))
    import build_xyz as cli
    import plot_map
    orig = plot_map.main
    plot_map.main = lambda argv: orig(argv + ["--output", str(tmp_path / "out" / "map"),
                                              "--formats", "png", "--dpi", "50"])
    try:
        cli.main([str(cfg)])
    finally:
        plot_map.main = orig
    assert (tmp_path / "out" / "xyz.csv").exists()
    assert (tmp_path / "out" / "map.png").exists()
