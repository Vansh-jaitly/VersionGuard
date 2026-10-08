"""minilib 1.0: a tiny made-up library used only to self-check VersionGuard.

It exists in two versions (see ../../minilib-2.0) that differ the way real
libraries do: a renamed function, a renamed argument, a removed method, and a
changed default. It is NOT part of the experiment's data.
"""

__version__ = "1.0"
__all__ = ["Table", "clip", "mean", "moving_average", "normalize", "scale"]


def mean(values):
    """Return the arithmetic mean of a list of numbers."""
    return sum(values) / len(values)


def moving_average(values, window):
    """Return the moving average of `values` over a sliding `window`.

    The result has len(values) - window + 1 items.
    """
    return [sum(values[i : i + window]) / window for i in range(len(values) - window + 1)]


def scale(values, factor=1.0):
    """Multiply every value by `factor`."""
    return [value * factor for value in values]


def clip(values, low, high):
    """Limit every value to the range [low, high]."""
    return [min(max(value, low), high) for value in values]


def normalize(values):
    """Rescale values linearly to the range 0..1 (min-max normalisation)."""
    low, high = min(values), max(values)
    return [(value - low) / (high - low) for value in values]


class Table:
    """A list of rows."""

    def __init__(self, rows=None):
        self.rows = list(rows or [])

    def append(self, row):
        """Return a new Table with `row` added at the end."""
        return Table(self.rows + [row])

    def count(self):
        """Return the number of rows."""
        return len(self.rows)
