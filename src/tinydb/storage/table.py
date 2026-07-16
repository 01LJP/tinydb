"""Table data-page management for tinydb.

A Table owns a set of data pages.  Records are inserted into the first page
with enough free space; when all existing pages are full a new page is
allocated via the buffer pool's file manager.

Record ids encode both the page and slot::

    record_id = (page_id << 16) | slot_id
"""

from tinydb.storage.page import Page, serialize_record, deserialize_record


class Row:
    """A single deserialized table row."""

    __slots__ = ("columns", "values", "record_id")

    def __init__(self, columns, values, record_id: int):
        self.columns = columns
        self.values = values
        self.record_id = record_id

    def to_dict(self) -> dict:
        """Return a ``{column_name: value}`` mapping."""
        return {col.name: val for col, val in zip(self.columns, self.values)}

    def __getitem__(self, key):
        if isinstance(key, int):
            return self.values[key]
        for col, val in zip(self.columns, self.values):
            if col.name == key:
                return val
        raise KeyError(key)

    def __repr__(self):
        return f"Row({self.to_dict()})"

    def __eq__(self, other):
        if isinstance(other, Row):
            return self.values == other.values
        return NotImplemented


class Table:
    """Manages the data pages of a single table."""

    def __init__(self, table_id: int, name: str, columns, buffer_pool):
        self.table_id = table_id
        self.name = name
        self.columns = columns
        self.buffer_pool = buffer_pool
        self.root_page_id: int = None   # first data page
        self._page_ids: list = []       # all data pages (in allocation order)

    # ------------------------------------------------------------------
    # Page management
    # ------------------------------------------------------------------

    def _allocate_page(self):
        """Allocate a fresh data page and register it with this table.

        Returns ``(page_id, page)``.
        """
        fm = self.buffer_pool.file_manager
        page_id = fm.allocate_page()
        page = self.buffer_pool.get_page(page_id)
        page.flags = Page.TABLE_DATA
        self._page_ids.append(page_id)
        if self.root_page_id is None:
            self.root_page_id = page_id
        self.buffer_pool.mark_dirty(page_id)
        return page_id, page

    # ------------------------------------------------------------------
    # DML
    # ------------------------------------------------------------------

    def insert(self, values) -> int:
        """Insert a record and return its record_id.

        The *values* list must align with ``self.columns``.
        """
        data = serialize_record(self.columns, values)
        data_len = len(data)

        # Find the first page with enough free space.
        target_page = None
        target_page_id = None
        for pid in self._page_ids:
            page = self.buffer_pool.get_page(pid)
            if page.has_space(data_len):
                target_page = page
                target_page_id = pid
                break

        if target_page is None:
            target_page_id, target_page = self._allocate_page()

        slot_id = target_page.insert_record(data)
        self.buffer_pool.mark_dirty(target_page_id)
        return (target_page_id << 16) | slot_id

    def scan(self):
        """Yield a :class:`Row` for every live record in the table."""
        for pid in self._page_ids:
            page = self.buffer_pool.get_page(pid)
            for slot_id in range(page.slot_count):
                data = page.get_record(slot_id)
                if not data:
                    continue  # deleted (tombstoned) record
                values = deserialize_record(self.columns, data)
                yield Row(self.columns, values, (pid << 16) | slot_id)

    def get(self, record_id: int):
        """Return the value list for *record_id*, or ``None`` if deleted."""
        page_id = record_id >> 16
        slot_id = record_id & 0xFFFF
        page = self.buffer_pool.get_page(page_id)
        data = page.get_record(slot_id)
        if not data:
            return None
        return deserialize_record(self.columns, data)
