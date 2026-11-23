#!/usr/bin/env python3
"""Write examples/synthetic_PL.csv: a made-up gate-dependent PL map in the x, y, z table format.

It only imitates the look of a real measurement (a few exciton-like peaks that switch on or off
with gate voltage, on a flat background with noise) so the code can be tried without real data.
"""
from pathlib import Path

import numpy as np


def lorentz(x, x0, w):
    return 1.0 / (1.0 + ((x - x0) / (w / 2)) ** 2)


def sigmoid(v, v0, s):
    return 1.0 / (1.0 + np.exp(-(v - v0) / s))


def main():
    rng = np.random.default_rng(0)
    x = np.linspace(1.793, 1.615, 400)            # energy (eV), descending like the spectrometer
    y = np.round(np.arange(-1.0, 2.0001, 0.1), 2)  # gate voltage (V)
    rows = []
    for v in y:
        neg = 1 - sigmoid(v, 0.05, 0.05)          # peaks present at negative gate
        pos = sigmoid(v, 0.0, 0.15)               # peak growing at positive gate
        z = (1000
             + 700 * neg * lorentz(x, 1.665, 0.008)
             + 4800 * neg * lorentz(x, 1.689, 0.006) * np.exp(-((v + 0.2) / 0.5) ** 2)
             + 2200 * neg * lorentz(x, 1.703, 0.009)
             + 1800 * neg * lorentz(x, 1.709, 0.007)
             + 900 * pos * lorentz(x, 1.741 - 0.004 * v, 0.014) * np.exp(-((v - 0.4) / 1.2) ** 2)
             + 500 * pos * lorentz(x, 1.716, 0.010)
             + rng.normal(0, 12, x.size))
        rows += [(e, v, round(c)) for e, c in zip(x, z)]
    out = Path(__file__).with_name("synthetic_PL.csv")
    with open(out, "w") as fh:
        fh.write("Energy (eV),Gate Voltage (V),PL (counts)\n")
        fh.writelines(f"{e:.5f},{v:g},{c}\n" for e, v, c in rows)
    print(out)


if __name__ == "__main__":
    main()
