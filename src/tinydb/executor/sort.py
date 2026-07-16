"""ORDER BY operator for tinydb.

Materialises the full upstream input, sorts it with Python's stable ``list.sort``,
then yields rows in order.  For a teaching database the input is assumed to
fit in memory.
"""


class Sort:
    """ORDER BY *column* [ASC|DESC]."""

    def __init__(self, source, column, order='ASC'):
        """
        Parameters
        ----------
        source : iterable of dict
            Upstream row source.
        column : str
            Column to sort by.
        order : {'ASC', 'DESC'}
            Sort direction (case-insensitive).
        """
        self.source = source
        self.column = column
        self.order = order.upper() if order else 'ASC'

    def __iter__(self):
        """Yield rows in sorted order."""
        rows = list(self.source)
        reverse = (self.order == 'DESC')
        # None sorts before any real value in Python 3; we keep that behavior
        # so rows whose sort column is NULL appear first.
        rows.sort(key=lambda row: row.get(self.column), reverse=reverse)
        yield from rows
