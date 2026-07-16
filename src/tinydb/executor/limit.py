"""LIMIT / OFFSET operator for tinydb.

Thin wrapper around :func:`itertools.islice` so we never materialise the
rows we skip over.
"""

import itertools


class Limit:
    """Apply LIMIT and OFFSET to a source."""

    def __init__(self, source, limit, offset=0):
        """
        Parameters
        ----------
        source : iterable of dict
            Upstream row source.
        limit : int or None
            Maximum number of rows to yield.  ``0`` or ``None`` means *no*
            limit (yield everything after *offset*).
        offset : int
            Number of rows to skip before yielding.
        """
        self.source = source
        self.limit = limit
        self.offset = max(0, int(offset or 0))

    def __iter__(self):
        """Yield up to ``limit* rows, starting after ``offset`` rows."""
        if not self.limit:
            # Zero / None → no upper bound
            stop = None
        else:
            stop = self.offset + self.limit
        yield from itertools.islice(self.source, self.offset, stop)
