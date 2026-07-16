"""Query plan selection for tinydb.

Central decision point that picks the physical scan operator for a query.
Right now tinydb only supports full table scans; when B-tree indexes land
this module will be extended to choose index scans on selectivity grounds.
"""

from tinydb.executor.scan import SeqScan


class PlanSelector:
    """Pick the best scan strategy for a table."""

    def __init__(self, catalog, index_manager=None):
        """
        Parameters
        ----------
        catalog : Catalog
            Used to look up table metadata and the live Table object.
        index_manager : optional
            Future extension hook — when not None, self-contained index
            lookups can drive index-scan decisions.
        """
        self.catalog = catalog
        self.index_manager = index_manager

    def select_scan(self, table_name, where_clause):
        """Return a physical scan operator for *table_name*.

        Currently always returns a :class:`SeqScan`.  *where_clause* is
        reserved for future selectivity-based plan selection.
        """
        info = self.catalog.get_table(table_name)
        if info is None:
            raise ValueError(f"table {table_name!r} not found in catalog")

        # Prefer the live Table instance (it owns the allocated data pages).
        table = self.catalog.get_table_object(table_name)
        if table is None:
            # Fall back to constructing a bare Table from catalog metadata.
            from tinydb.storage.table import Table as _Table
            table = _Table(
                table_id=info.table_id,
                name=info.name,
                columns=info.columns,
                buffer_pool=self.catalog.buffer_pool,
            )
            table.root_page_id = info.root_page_id
        return SeqScan(table, self.catalog, self.catalog.buffer_pool)
