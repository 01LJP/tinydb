"""Tests for tinydb schema catalog."""

import os
import tempfile
import pytest

from tinydb.types import DataType, ColumnDef
from tinydb.catalog import Catalog
from tinydb.storage.file_manager import FileManager
from tinydb.storage.buffer_pool import BufferPool


@pytest.fixture
def catalog():
    """Create a Catalog backed by a temporary database file."""
    tmp = tempfile.NamedTemporaryFile(delete=False, suffix=".db")
    tmp.close()
    fm = FileManager(tmp.name)
    bp = BufferPool(fm, capacity=10)
    cat = Catalog(bp)
    yield cat, bp, fm, tmp.name
    if not fm._file.closed:
        bp.close()
    os.unlink(tmp.name)


def make_columns():
    return [
        ColumnDef("id", DataType.INT, is_pk=True, nullable=False),
        ColumnDef("name", DataType.TEXT),
        ColumnDef("age", DataType.INT),
    ]


# =========================================================================
# Table lifecycle
# =========================================================================

class TestCreateTable:
    def test_create_table_returns_id(self, catalog):
        cat, *_ = catalog
        tid = cat.create_table("users", make_columns())
        assert isinstance(tid, int)
        assert tid >= 1

    def test_create_table_stores_name(self, catalog):
        cat, *_ = catalog
        cat.create_table("users", make_columns())
        assert cat.table_exists("users")

    def test_create_multiple_tables_unique_ids(self, catalog):
        cat, *_ = catalog
        id1 = cat.create_table("t1", make_columns())
        id2 = cat.create_table("t2", make_columns())
        assert id1 != id2

    def test_create_same_table_twice_raises(self, catalog):
        cat, *_ = catalog
        cat.create_table("users", make_columns())
        with pytest.raises(Exception):
            cat.create_table("users", make_columns())


# =========================================================================
# Get table info
# =========================================================================

class TestGetTable:
    def test_get_table(self, catalog):
        cat, *_ = catalog
        tid = cat.create_table("users", make_columns())
        info = cat.get_table("users")
        assert info is not None
        assert info.table_id == tid
        assert info.name == "users"

    def test_get_table_not_found_returns_none(self, catalog):
        cat, *_ = catalog
        assert cat.get_table("nonexistent") is None

    def test_get_columns(self, catalog):
        cat, *_ = catalog
        cols = make_columns()
        tid = cat.create_table("users", cols)
        result = cat.get_columns(tid)
        assert len(result) == 3
        assert result[0].name == "id"
        assert result[0].data_type == DataType.INT
        assert result[1].name == "name"
        assert result[2].name == "age"

    def test_get_columns_unknown_table(self, catalog):
        cat, *_ = catalog
        assert cat.get_columns(999) == []


# =========================================================================
# Table existence / drop
# =========================================================================

class TestTableExistence:
    def test_table_exists_false_initially(self, catalog):
        cat, *_ = catalog
        assert cat.table_exists("users") is False

    def test_table_exists_true_after_create(self, catalog):
        cat, *_ = catalog
        cat.create_table("users", make_columns())
        assert cat.table_exists("users") is True

    def test_drop_table(self, catalog):
        cat, *_ = catalog
        cat.create_table("users", make_columns())
        cat.drop_table("users")
        assert cat.table_exists("users") is False

    def test_drop_table_columns_removed(self, catalog):
        cat, *_ = catalog
        tid = cat.create_table("users", make_columns())
        cat.drop_table("users")
        assert cat.get_columns(tid) == []

    def test_drop_nonexistent_table_raises(self, catalog):
        cat, *_ = catalog
        with pytest.raises(Exception):
            cat.drop_table("nope")


# =========================================================================
# Table IDs
# =========================================================================

class TestTableIds:
    def test_next_table_id_increments(self, catalog):
        cat, *_, name = catalog
        first = cat.get_next_table_id()
        cat.create_table("t1", make_columns())
        second = cat.get_next_table_id()
        assert second > first

    def test_create_uses_next_table_id(self, catalog):
        cat, *_ = catalog
        n = cat.get_next_table_id()
        tid = cat.create_table("t", make_columns())
        assert tid == n


# =========================================================================
# Persistence: reload from disk
# =========================================================================

class TestPersistence:
    def test_catalog_persists_after_reload(self, catalog):
        cat, bp, fm, name = catalog
        cat.create_table("users", make_columns())
        cat.create_table("orders", [
            ColumnDef("oid", DataType.INT, is_pk=True),
            ColumnDef("total", DataType.FLOAT),
        ])
        # flush and close
        bp.close()
        # reopen
        fm2 = FileManager(name)
        bp2 = BufferPool(fm2, capacity=10)
        cat2 = Catalog(bp2)
        assert cat2.table_exists("users")
        assert cat2.table_exists("orders")
        info = cat2.get_table("orders")
        assert info.name == "orders"
        cols = cat2.get_columns(info.table_id)
        assert cols[1].name == "total"
        assert cols[1].data_type == DataType.FLOAT
        bp2.close()
