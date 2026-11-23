"""Phase-diagram mapping, Part 2: x, y, z table -> 2D colour map."""
from .io import XYZ, Label, read_xyz, to_grid
from .plot import MapOptions, draw, make_figure, plot_map, save
from .style import Style, format_label

__all__ = ["XYZ", "Label", "read_xyz", "to_grid", "MapOptions", "draw", "make_figure",
           "plot_map", "save", "Style", "format_label", "LiveMap"]


def __getattr__(name):
    if name == "LiveMap":          # imported lazily: it needs IPython only in notebooks
        from .live import LiveMap
        return LiveMap
    raise AttributeError(name)
