"""Schema catalog for tinydb.

Manages table and column metadata, persisted to the catalog page (page 0).
Metadata is serialized with pickle for simplicity.

In-memory layout:
    tables:  dict[str, TableInfo]         # table_name -> TableInfo
    columns: dict[int, list[ColumnDef]]   # table_id   -> columns
"""

import pickle
from dataclasses import dataclass, field
from typing import List, Optional

from tinydb.types import ColumnDef


# Page 0 is always the catalog page.
CATALOG_PAGE_ID = 0


@dataclass
class TableInfo:
    """Runtime information about a table."""
    table_id: int
    name: str
    root_page_id: Optional[int] = None
    columns: List[ColumnDef] = field(default_factory=list)
    page_ids: List[int] = field(default_factory=list)


class Catalog:
    """Manages table/column metadata, persisted to the catalog page."""

    def __init__(self, buffer_pool):
        self.buffer_pool = buffer_pool
        self.tables: dict = {}      # name -> TableInfo
        self.columns: dict = {}     # table_id -> List[ColumnDef]
        self._table_objects: dict = {}  # name -> storage.Table (live instances)
        self._next_table_id: int = 1
        self._load()

    # ------------------------------------------------------------------
    # (De)serialization
    # ------------------------------------------------------------------

    def _load(self):
        """Load metadata from the catalog page into memory."""
        page = self.buffer_pool.get_page(CATALOG_PAGE_ID)
        page.flags = page.flags  # keep whatever flags were on disk
        data = page.get_record(0) if page.slot_count > 0 else b''
        if not data:
            # fresh database
            self.tables = {}
            self.columns = {}
            self._next_table_id = 1
            # Reserve page 0 (catalog) so the file manager never hands it
            # out as a data page.
            self._reserve_catalog_page()
            return

        blob = pickle.loads(data)
        self.tables = blob['tables']
        self.columns = blob['columns']
        self._next_table_id = blob['next_table_id']

    def _reserve_catalog_page(self):
        """Ensure the file manager will never allocate page 0 as data.

        Page 0 is permanently the catalog page.  On a fresh database the
        file manager's next-id cursor is 0; bump it to 1 so the first
        data-page allocation starts at page 1.
        """
        fm = self.buffer_pool.file_manager
        if fm._next_page_id < 1:
            fm._next_page_id = 1

    def _save(self):
        """Write the in-memory metadata back to the catalog page."""
        blob = {
            'tables': self.tables,
            'columns': self.columns,
            'next_table_id': self._next_table_id,
        }
        data = pickle.dumps(blob)

        page = self.buffer_pool.get_page(CATALOG_PAGE_ID)
        # Ensure catalog flag
        from tinydb.storage.page import Page as _Page
        page.flags = _Page.CATALOG

        # Overwrite slot 0 if it exists, otherwise insert
        if page.slot_count > 0:
            # Replace existing record in-place by resetting the page slot.
            # Since slotted pages don't support true in-place replace of a
            # larger record, we drop all slots and rewrite one.
            self._rewrite_page(page, data)
        else:
            page.insert_record(data)

        self.buffer_pool.mark_dirty(CATALOG_PAGE_ID)

    @staticmethod
    def _rewrite_page(page, data: bytes):
        """Replace page contents with a single record holding *data*."""
        # Re-initialize the page buffer so it has exactly one slot.
        page.buf = bytearray(page.PAGE_SIZE)
        page.slot_count = 0
        page.free_space = page.PAGE_SIZE - page.HEADER_SIZE
        page._write_header()
        page.insert_record(data)

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def create_table(self, name: str, columns: list) -> int:
        """Create a table and return its table_id.

        Raises:
            ValueError if a table with the given name already exists.
        """
        if name in self.tables:
            raise ValueError(f"table '{name}' already exists")

        table_id = self._next_table_id
        self._next_table_id += 1

        info = TableInfo(table_id=table_id, name=name, columns=columns)
        self.tables[name] = info
        self.columns[table_id] = list(columns)
        self._save()
        return table_id

    def update_table_info(self, name: str, info: TableInfo):
        """Persist updated TableInfo (e.g. after data pages are allocated)."""
        self.tables[name] = info
        self._save()

    def register_table_object(self, name: str, table_obj):
        """Register a live :class:`~tinydb.storage.table.Table` instance.

        The executor's PlanSelector uses this to find the in-memory Table
        (with its allocated data pages) for a given table name.
        """
        self._table_objects[name] = table_obj

    def get_table_object(self, name: str):
        """Return the live Table instance for *name*, or None."""
        return self._table_objects.get(name)

    def drop_table(self, name: str):
        """Drop a table by name.

        Raises:
            ValueError if the table does not exist.
        """
        if name not in self.tables:
            raise ValueError(f"table '{name}' does not exist")

        info = self.tables.pop(name)
        self.columns.pop(info.table_id, None)
        self._save()

    def get_table(self, name: str) -> Optional[TableInfo]:
        """Return TableInfo for *name*, or None if not found."""
        return self.tables.get(name)

    def get_columns(self, table_id: int) -> list:
        """Return the column list for *table_id*, or [] if unknown."""
        return self.columns.get(table_id, [])

    def table_exists(self, name: str) -> bool:
        """Return True if a table named *name* exists."""
        return name in self.tables

    def get_next_table_id(self) -> int:
        """Return the next available table_id (without consuming it)."""
        return self._next_table_id
