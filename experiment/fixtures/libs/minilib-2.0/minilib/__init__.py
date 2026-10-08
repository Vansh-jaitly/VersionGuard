"""minilib 2.0: a tiny made-up library used only to self-check VersionGuard.

Changes since 1.0 (each mirrors a kind of change real libraries make):
  * moving_average() was renamed to rolling_mean(), and `window` to `size`.
  * scale(): the argument `factor` was renamed to `by`.
  * Table.append() was removed; use concat([table, Table([row])]).
  * normalize() now z-scores by default; pass mode="minmax" for the old result.
It is NOT part of the experiment's data.
"""

__version__ = "2.0"
__all__ = ["Table", "clip", "concat", "mean", "normalize", "rolling_mean", "scale"]


def mean(values):
    """Return the arithmetic mean of a list of numbers."""
    return sum(values) / len(values)


def rolling_mean(values, size):
    """Return the mean of `values` over a sliding window of `size` items.

    Replaces moving_average() from 1.x. The result has len(values) - size + 1 items.
    """
    return [sum(values[i : i + size]) / size for i in range(len(values) - size + 1)]


def scale(values, by=1.0):
    """Multiply every value by `by`. (The argument was called `factor` in 1.x.)"""
    return [value * by for value in values]


def clip(values, low, high):
    """Limit every value to the range [low, high]."""
    return [min(max(value, low), high) for value in values]


def normalize(values, mode="zscore"):
    """Normalise values.

    mode="zscore" (default since 2.0) subtracts the mean and divides by the
    population standard deviation. mode="minmax" rescales linearly to 0..1,
    which was the only behaviour in 1.x.
    """
    if mode == "minmax":
        low, high = min(values), max(values)
        return [(value - low) / (high - low) for value in values]
    if mode != "zscore":
        raise ValueError("mode must be 'zscore' or 'minmax'")
    centre = sum(values) / len(values)
    spread = (sum((value - centre) ** 2 for value in values) / len(values)) ** 0.5
    return [(value - centre) / spread for value in values]


class Table:
    """A list of rows."""

    def __init__(self, rows=None):
        self.rows = list(rows or [])

    def count(self):
        """Return the number of rows."""
        return len(self.rows)


def concat(tables):
    """Join several Table objects into one, keeping row order.

    Replaces Table.append() from 1.x: concat([table, Table([row])]).
    """
    rows = []
    for table in tables:
        rows.extend(table.rows)
    return Table(rows)
