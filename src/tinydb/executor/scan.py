"""Sequential table scan for tinydb.

Yields a row dict (``{column: value, ...}``) for every live record in the
table.  Tombstoned (deleted) records in the slotted pages are skipped.

This is the only physical scan operator — future ``IndexScan`` implementations
will be selected by :class:`~tinydb.executor.plan.PlanSelector`.
"""


class SeqScan:
    """Full table scan: walk every data page, every slot, skip tombstones."""

    def __init__(self, table, catalog, buffer_pool):
        """
        Parameters
        ----------
        table : tinydb.storage.table.Table
            The table to scan.
        catalog : Catalog
            Unused (kept for operator-signature compatibility with PlanSelector).
        buffer_pool : BufferPool
            Unused (table already owns a reference).
        """
        self.table = table
        self.catalog = catalog
        self.buffer_pool = buffer_pool

    def __iter__(self):
        """Yield a ``dict`` (column-name → value) per live row."""
        for row in self.table.scan():
            yield row.to_dict()
