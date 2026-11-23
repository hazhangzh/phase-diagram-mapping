from pathlib import Path

import matplotlib

matplotlib.use("Agg")

import numpy as np
import pytest

from pdm import Label, LiveMap, MapOptions, format_label, plot_map, read_xyz, save, to_grid
from pdm.plot import format_sig, z_limits

ROOT = Path(__file__).resolve().parent.parent
SAMPLE = ROOT / "examples" / "gate-dep_PL.csv"        # real data, kept local (not in git)
SYNTH = ROOT / "examples" / "synthetic_PL.csv"


def test_read_synthetic():
    d = read_xyz(SYNTH)
    assert d.z.shape == (31, 400)
    assert np.all(np.diff(d.x) > 0) and np.all(np.diff(d.y) > 0)
    assert d.labels["y"] == Label("Gate Voltage", "V")


def test_cr_line_endings(tmp_path):
    p = tmp_path / "cr.csv"
    p.write_bytes(b"E (eV),V (V),PL (counts)\r1.6,0,10\r1.7,0,11\r1.6,1,12\r1.7,1,13\r")
    d = read_xyz(p)
    assert d.z.tolist() == [[10, 11], [12, 13]]


@pytest.mark.skipif(not SAMPLE.exists(), reason="real sample data is not in the repository")
def test_read_sample_with_cr_line_endings():
    d = read_xyz(SAMPLE)
    assert d.z.shape == (31, 2048)
    assert np.all(np.diff(d.x) > 0) and np.all(np.diff(d.y) > 0)
    assert d.y[0] == pytest.approx(-1) and d.y[-1] == pytest.approx(2)
    assert d.labels["x"] == Label("Energy", "eV")
    assert d.labels["z"] == Label("PL", "counts")
    assert d.z.min() == 991 and d.z.max() == 6271


def test_to_grid_rejects_irregular():
    data = np.array([[1, 0, 5], [2, 0, 6], [1, 1, 7]], float)
    with pytest.raises(ValueError):
        to_grid(data)


@pytest.mark.parametrize("v,s", [(980, "980.0"), (6280, "6280"), (1642.5, "1643"),
                                 (2967.5, "2968"), (0.012345, "0.01235"), (999.96, "1000")])
def test_format_sig(v, s):
    assert format_sig(v, 4) == s


def test_z_limits():
    z = np.array([991.0, 6271.0])
    assert z_limits(z, MapOptions()) == (991, 6271)
    assert z_limits(z, MapOptions(z_round=20)) == (980, 6280)
    assert z_limits(z, MapOptions(z_range=(1000, 5000))) == (1000, 5000)


def test_format_label():
    assert format_label("Energy", "eV") == r"Energy ($\mathit{eV}$)"
    assert format_label("Shift", "cm^{-1}") == r"Shift ($\mathit{cm^{-1}}$)"
    assert format_label("Count") == "Count"


def test_plot_and_save(tmp_path):
    mf = plot_map(read_xyz(SYNTH), opts=MapOptions(z_range=(980, 6280)))
    labels = [t.get_text() for t in mf.cax.get_yticklabels()]
    assert labels[0] == "980.0" and labels[-1] == "6280" and len(labels) == 9
    pos = mf.ax.get_position()
    w, h = mf.fig.get_size_inches()
    assert pos.width * w == pytest.approx(pos.height * h)        # square map
    out = save(mf, tmp_path / "m", formats=("png", "pdf", "svg"), dpi=72)
    assert all(p.stat().st_size > 0 for p in out)


def test_live_map(tmp_path):
    x = np.linspace(1.6, 1.8, 50)
    live = LiveMap(x, y_plan=(-1, 1, 0.5), labels={"x": "Energy (eV)", "y": "V (V)",
                                                     "z": "PL (counts)"}, display=False)
    for v in (-1, -0.5, 0):
        live.add(v, np.exp(-((x - 1.7) / 0.01) ** 2) * (v + 2))
    assert live.mf.ax.get_ylim() == (-1, 1)
    p = live.save_table(tmp_path / "t.csv")
    back = read_xyz(p)
    assert back.z.shape == (3, 50) and back.labels["y"] == Label("V", "V")
