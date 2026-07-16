"""Integration tests for tinydb Table over a real buffer pool + file manager."""

import os
import tempfile
import pytest

from tinydb.types import DataType, ColumnDef
from tinydb.storage.page import Page
from tinydb.storage.file_manager import FileManager
from tinydb.storage.buffer_pool import BufferPool
from tinydb.storage.table import Table, Row


@pytest.fixture
def table():
    tmp = tempfile.NamedTemporaryFile(delete=False, suffix=".db")
    tmp.close()
    fm = FileManager(tmp.name)
    bp = BufferPool(fm, capacity=10)
    columns = [
        ColumnDef("id", DataType.INT, is_pk=True),
        ColumnDef("name", DataType.TEXT),
        ColumnDef("age", DataType.INT),
    ]
    t = Table(table_id=1, name="users", columns=columns, buffer_pool=bp)
    yield t, bp, fm, tmp.name
    if not fm._file.closed:
        bp.close()
    os.unlink(tmp.name)


class TestTableInsert:
    def test_insert_returns_record_id(self, table):
        t, *_ = table
        rid = t.insert([1, "Alice", 30])
        assert isinstance(rid, int)

    def test_insert_first_record_root_page_is_set(self, table):
        t, *_ = table
        t.insert([1, "Alice", 30])
        assert t.root_page_id == 0
        assert t._page_ids == [0]

    def test_insert_multiple_stays_in_one_page(self, table):
        t, *_ = table
        rids = []
        for i in range(5):
            rids.append(t.insert([i, f"user{i}", 20 + i]))
        assert len(t._page_ids) == 1
        assert len(set(rids)) == 5


class TestTableScan:
    def test_scan_yields_all_rows(self, table):
        t, *_ = table
        t.insert([1, "Alice", 30])
        t.insert([2, "Bob", 25])
        rows = list(t.scan())
        assert len(rows) == 2
        assert rows[0]["name"] == "Alice"
        assert rows[1]["name"] == "Bob"

    def test_scan_skips_deleted(self, table):
        t, *_ = table
        rid0 = t.insert([1, "Alice", 30])
        rid1 = t.insert([2, "Bob", 25])
        # delete via page tombstone
        page = t.buffer_pool.get_page(rid1 >> 16)
        page.delete_record(rid1 & 0xFFFF)
        rows = list(t.scan())
        assert len(rows) == 1
        assert rows[0]["name"] == "Alice"


class TestTableGet:
    def test_get_by_record_id(self, table):
        t, *_ = table
        rid = t.insert([42, "Carol", 28])
        values = t.get(rid)
        assert values == [42, "Carol", 28]

    def test_get_deleted_returns_none(self, table):
        t, *_ = table
        rid = t.insert([1, "Alice", 30])
        page = t.buffer_pool.get_page(rid >> 16)
        page.delete_record(rid & 0xFFFF)
        assert t.get(rid) is None


class TestRecordIdEncoding:
    def test_record_id_decodes_page_and_slot(self, table):
        t, *_ = table
        rid = t.insert([1, "Alice", 30])
        assert (rid >> 16) == 0   # page_id
        assert (rid & 0xFFFF) == 0  # slot_id


class TestRow:
    def test_row_to_dict(self, table):
        t, *_ = table
        rid = t.insert([1, "Alice", 30])
        row = t.scan().__next__()
        # re-fetch
        rows = list(t.scan())
        d = rows[0].to_dict()
        assert d == {"id": 1, "name": "Alice", "age": 30}

    def test_row_getitem(self, table):
        t, *_ = table
        t.insert([1, "Alice", 30])
        row = list(t.scan())[0]
        assert row["name"] == "Alice"
        assert row[0] == 1
