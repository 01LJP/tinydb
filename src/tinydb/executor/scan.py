"""Sequential table scan for tinydb.

Yields a row dict (``{column: value, ...}``) for every live record in the
table.  Tombstoned (deleted) records in the slotted pages are skipped.

This is the only physical scan operator — future ``IndexScan`` implementations
will be selected by :class:`~tinydb.executor.plan.PlanSelector`.
"""


class SeqScan:
    """Full table scan: walk every data page, every slot, skip tombstones."""

    def __init__(self, table, catalog, buffer_pool, prefix_columns=False, table_alias=None):
        """
        Parameters
        ----------
        table : tinydb.storage.table.Table
            The table to scan.
        catalog : Catalog
            Unused (kept for operator-signature compatibility with PlanSelector).
        buffer_pool : BufferPool
            Unused (table already owns a reference).
        prefix_columns : bool
            If True, prefix column names with table name (e.g. 'users.id').
        table_alias : str or None
            Alias to use for column prefix instead of table name.
        """
        self.table = table
        self.catalog = catalog
        self.buffer_pool = buffer_pool
        self.prefix_columns = prefix_columns
        self.table_alias = table_alias

    def __iter__(self):
        """Yield a ``dict`` (column-name → value) per live row."""
        for row in self.table.scan():
            d = row.to_dict()
            if self.prefix_columns:
                prefix = self.table_alias or self.table.name
                d = {f"{prefix}.{k}": v for k, v in d.items()}
            yield d
