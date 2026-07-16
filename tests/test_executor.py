"""Tests for tinydb query executor (scan, filter, sort, limit, aggregate).

These tests build real tables using the storage layer (FileManager +
BufferPool + Table), then run the executor operators over them.
"""

import os
import tempfile
import pytest

from tinydb.types import DataType, ColumnDef
from tinydb.storage.file_manager import FileManager
from tinydb.storage.buffer_pool import BufferPool
from tinydb.storage.table import Table
from tinydb.catalog import Catalog
from tinydb.executor.scan import SeqScan
from tinydb.executor.filter import Filter
from tinydb.executor.sort import Sort
from tinydb.executor.limit import Limit
from tinydb.executor.aggregate import Aggregate
from tinydb.executor.plan import PlanSelector
from tinydb.ast_nodes import (
    BinaryExpr, ColumnRef, Literal, AggregateExpr,
)


# =========================================================================
# Helpers
# =========================================================================

def make_columns():
    return [
        ColumnDef("id", DataType.INT, is_pk=True, nullable=False),
        ColumnDef("name", DataType.TEXT),
        ColumnDef("age", DataType.INT),
        ColumnDef("dept", DataType.TEXT),
        ColumnDef("salary", DataType.FLOAT),
    ]


@pytest.fixture
def db():
    """Create a fresh temp db with one fully-populated 'employees' table."""
    tmp = tempfile.NamedTemporaryFile(delete=False, suffix=".db")
    tmp.close()
    fm = FileManager(tmp.name)
    bp = BufferPool(fm, capacity=50)
    cat = Catalog(bp)
    cols = make_columns()
    tid = cat.create_table("employees", cols)
    table = Table(table_id=tid, name="employees", columns=cols, buffer_pool=bp)

    rows = [
        (1, "Alice",   30, "eng", 90000.0),
        (2, "Bob",     25, "eng", 80000.0),
        (3, "Charlie", 35, "sales", 70000.0),
        (4, "Diana",   28, "sales", 75000.0),
        (5, "Eve",     32, "eng", 95000.0),
    ]
    for r in rows:
        table.insert(list(r))
    cat.register_table_object("employees", table)

    yield {"fm": fm, "bp": bp, "cat": cat, "table": table,
            "columns": cols, "path": tmp.name}
    if not fm._file.closed:
        bp.close()
    os.unlink(tmp.name)


def _seqscan(table):
    """Helper: run SeqScan and return the list of row dicts."""
    return list(SeqScan(table, None, None))


# =========================================================================
# SeqScan
# =========================================================================

class TestSeqScan:
    def test_returns_all_rows(self, db):
        rows = _seqscan(db["table"])
        assert len(rows) == 5

    def test_row_is_dict_with_column_names(self, db):
        rows = _seqscan(db["table"])
        assert rows[0] == {"id": 1, "name": "Alice", "age": 30,
                           "dept": "eng", "salary": 90000.0}

    def test_skip_deleted_records(self, db):
        table = db["table"]
        # First data page is page 1 (page 0 is the catalog).  Delete slot 0.
        first_data_page_id = table._page_ids[0]
        page = db["bp"].get_page(first_data_page_id)
        page.delete_record(0)
        rows = _seqscan(table)
        assert len(rows) == 4
        assert all(r["name"] != "Alice" for r in rows)


# =========================================================================
# Filter (WHERE clause)
# =========================================================================

class TestFilter:
    def _filter(self, table, cond):
        src = SeqScan(table, None, None)
        return list(Filter(src, cond))

    def test_equality(self, db):
        cond = BinaryExpr(ColumnRef("dept"), "=", Literal("eng"))
        rows = self._filter(db["table"], cond)
        assert len(rows) == 3
        assert all(r["dept"] == "eng" for r in rows)

    def test_not_equal(self, db):
        cond = BinaryExpr(ColumnRef("dept"), "!=", Literal("eng"))
        rows = self._filter(db["table"], cond)
        assert len(rows) == 2
        assert all(r["dept"] != "eng" for r in rows)

    def test_not_equal_diamond(self, db):
        cond = BinaryExpr(ColumnRef("dept"), "<>", Literal("eng"))
        rows = self._filter(db["table"], cond)
        assert len(rows) == 2

    def test_less_than(self, db):
        cond = BinaryExpr(ColumnRef("age"), "<", Literal(30))
        rows = self._filter(db["table"], cond)
        assert len(rows) == 2  # Bob (25), Diana (28)

    def test_greater_than(self, db):
        cond = BinaryExpr(ColumnRef("age"), ">", Literal(30))
        rows = self._filter(db["table"], cond)
        assert len(rows) == 2  # Charlie (35), Eve (32)

    def test_less_equal(self, db):
        cond = BinaryExpr(ColumnRef("age"), "<=", Literal(30))
        rows = self._filter(db["table"], cond)
        assert len(rows) == 3  # Alice (30), Bob (25), Diana (28)

    def test_greater_equal(self, db):
        cond = BinaryExpr(ColumnRef("age"), ">=", Literal(30))
        rows = self._filter(db["table"], cond)
        assert len(rows) == 3  # Alice (30), Charlie (35), Eve (32)

    def test_and(self, db):
        cond = BinaryExpr(
            BinaryExpr(ColumnRef("dept"), "=", Literal("eng")),
            "AND",
            BinaryExpr(ColumnRef("age"), ">", Literal(28)),
        )
        rows = self._filter(db["table"], cond)
        assert len(rows) == 2  # Alice (30), Eve (32)

    def test_or(self, db):
        cond = BinaryExpr(
            BinaryExpr(ColumnRef("name"), "=", Literal("Alice")),
            "OR",
            BinaryExpr(ColumnRef("name"), "=", Literal("Bob")),
        )
        rows = self._filter(db["table"], cond)
        assert len(rows) == 2

    def test_null_comparison_returns_false(self, db):
        # Insert a NULL age row
        db["table"].insert([6, "Zara", None, "eng", 50000.0])
        cond = BinaryExpr(ColumnRef("age"), ">", Literal(20))
        rows = self._filter(db["table"], cond)
        # Zara's age is NULL → filter must skip her
        assert all(r.get("age") is not None for r in rows)

    def test_no_match(self, db):
        cond = BinaryExpr(ColumnRef("age"), ">", Literal(999))
        rows = self._filter(db["table"], cond)
        assert rows == []


# =========================================================================
# Sort (ORDER BY)
# =========================================================================

class TestSort:
    def _sort(self, table, col, order="ASC"):
        src = SeqScan(table, None, None)
        return list(Sort(src, col, order))

    def test_sort_asc(self, db):
        rows = self._sort(db["table"], "age", "ASC")
        ages = [r["age"] for r in rows]
        assert ages == [25, 28, 30, 32, 35]

    def test_sort_desc(self, db):
        rows = self._sort(db["table"], "age", "DESC")
        ages = [r["age"] for r in rows]
        assert ages == [35, 32, 30, 28, 25]

    def test_sort_default_asc(self, db):
        src = SeqScan(db["table"], None, None)
        rows = list(Sort(src, "name"))
        names = [r["name"] for r in rows]
        assert names == ["Alice", "Bob", "Charlie", "Diana", "Eve"]

    def test_sort_by_salary(self, db):
        rows = self._sort(db["table"], "salary", "DESC")
        assert rows[0]["name"] == "Eve"
        assert rows[-1]["name"] == "Charlie"


# =========================================================================
# Limit / Offset
# =========================================================================

class TestLimit:
    def _limit(self, table, limit, offset=0):
        src = SeqScan(table, None, None)
        return list(Limit(src, limit, offset))

    def test_limit_only(self, db):
        rows = self._limit(db["table"], 2)
        assert len(rows) == 2

    def test_limit_zero_returns_all(self, db):
        rows = self._limit(db["table"], 0)
        assert len(rows) == 5

    def test_offset_only(self, db):
        rows = self._limit(db["table"], 0, offset=3)
        assert len(rows) == 2

    def test_limit_and_offset(self, db):
        rows = self._limit(db["table"], 2, offset=1)
        assert len(rows) == 2
        # First row after offset should be the 2nd row from the scan
        ids = [r["id"] for r in rows]
        assert ids == [2, 3]

    def test_offset_beyond_returns_empty(self, db):
        rows = self._limit(db["table"], 10, offset=100)
        assert rows == []


# =========================================================================
# Aggregate
# =========================================================================

class TestAggregate:
    def _agg(self, table, select_columns, group_by=None):
        src = SeqScan(table, None, None)
        return Aggregate(src, select_columns, group_by).execute()

    def test_count_star(self, db):
        cols = [AggregateExpr(func="COUNT", column="*")]
        result = self._agg(db["table"], cols)
        assert result == [{"count": 5}]

    def test_count_column(self, db):
        cols = [AggregateExpr(func="COUNT", column="age")]
        result = self._agg(db["table"], cols)
        assert result == [{"count": 5}]

    def test_sum(self, db):
        cols = [AggregateExpr(func="SUM", column="age")]
        result = self._agg(db["table"], cols)
        assert result == [{"sum": 150}]    # 30+25+35+28+32

    def test_avg(self, db):
        cols = [AggregateExpr(func="AVG", column="salary")]
        result = self._agg(db["table"], cols)
        avg = (90000 + 80000 + 70000 + 75000 + 95000) / 5
        assert len(result) == 1
        assert result[0]["avg"] == pytest.approx(avg)

    def test_count_with_nulls(self, db):
        db["table"].insert([6, "Zara", None, "eng", 50000.0])
        cols = [AggregateExpr(func="COUNT", column="age")]
        result = self._agg(db["table"], cols)
        # Zara's age is NULL → COUNT(age) excludes it
        assert result == [{"count": 5}]

    def test_group_by_count(self, db):
        cols = ["dept", AggregateExpr(func="COUNT", column="*")]
        result = self._agg(db["table"], cols, group_by="dept")
        by_dept = {r["dept"]: r["count"] for r in result}
        assert by_dept == {"eng": 3, "sales": 2}

    def test_group_by_avg(self, db):
        cols = ["dept", AggregateExpr(func="AVG", column="salary")]
        result = self._agg(db["table"], cols, group_by="dept")
        by_dept = {r["dept"]: r["avg"] for r in result}
        assert by_dept["eng"] == pytest.approx((90000 + 80000 + 95000) / 3)
        assert by_dept["sales"] == pytest.approx((70000 + 75000) / 2)


# =========================================================================
# Plan selector
# =========================================================================

class TestPlanSelector:
    def test_select_scan_returns_seqscan(self, db):
        ps = PlanSelector(db["cat"])
        scan = ps.select_scan("employees", None)
        rows = list(scan)
        assert len(rows) == 5
