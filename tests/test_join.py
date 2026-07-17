"""Tests for multi-table JOIN queries."""

import os
import tempfile
import pytest

import tinydb


@pytest.fixture
def db():
    """Create a temporary database with test tables."""
    with tempfile.NamedTemporaryFile(suffix=".tdb", delete=False) as f:
        path = f.name
    try:
        with tinydb.open(path) as db:
            db.execute("CREATE TABLE users (id INT PRIMARY KEY, name TEXT)")
            db.execute("CREATE TABLE orders (id INT PRIMARY KEY, user_id INT, amount FLOAT)")

            db.execute("INSERT INTO users VALUES (1, 'Alice')")
            db.execute("INSERT INTO users VALUES (2, 'Bob')")
            db.execute("INSERT INTO users VALUES (3, 'Charlie')")

            db.execute("INSERT INTO orders VALUES (1, 1, 50.0)")
            db.execute("INSERT INTO orders VALUES (2, 1, 75.0)")
            db.execute("INSERT INTO orders VALUES (3, 2, 30.0)")
            yield db
    finally:
        if os.path.exists(path):
            os.unlink(path)
        if os.path.exists(path + ".wal"):
            os.unlink(path + ".wal")


class TestInnerJoin:
    """Test INNER JOIN functionality."""

    def test_basic_inner_join(self, db):
        result = db.execute(
            "SELECT * FROM users INNER JOIN orders ON users.id = orders.user_id"
        )
        assert len(result) == 3  # Alice(2 orders) + Bob(1 order)

    def test_inner_join_omit_inner(self, db):
        result = db.execute(
            "SELECT * FROM users JOIN orders ON users.id = orders.user_id"
        )
        assert len(result) == 3

    def test_inner_join_no_match(self, db):
        # Charlie has no orders
        result = db.execute(
            "SELECT * FROM users INNER JOIN orders ON users.id = orders.user_id WHERE users.name = 'Charlie'"
        )
        assert len(result) == 0

    def test_inner_join_with_where(self, db):
        result = db.execute(
            "SELECT * FROM users JOIN orders ON users.id = orders.user_id WHERE orders.amount > 40"
        )
        assert len(result) == 2  # Alice's two orders (50 and 75)

    def test_inner_join_column_names(self, db):
        result = db.execute(
            "SELECT * FROM users JOIN orders ON users.id = orders.user_id"
        )
        assert len(result) > 0
        keys = set(result[0].keys())
        assert "users.id" in keys
        assert "users.name" in keys
        assert "orders.id" in keys
        assert "orders.user_id" in keys
        assert "orders.amount" in keys


class TestLeftJoin:
    """Test LEFT JOIN functionality."""

    def test_left_join_preserves_all_left_rows(self, db):
        result = db.execute(
            "SELECT * FROM users LEFT JOIN orders ON users.id = orders.user_id"
        )
        # All 3 users should appear
        assert len(result) == 4  # Alice(2) + Bob(1) + Charlie(1 with NULLs)

    def test_left_join_null_fill(self, db):
        result = db.execute(
            "SELECT * FROM users LEFT JOIN orders ON users.id = orders.user_id"
        )
        # Find Charlie's row (no orders)
        charlie_rows = [r for r in result if r.get("users.name") == "Charlie"]
        assert len(charlie_rows) == 1
        assert charlie_rows[0].get("orders.id") is None
        assert charlie_rows[0].get("orders.amount") is None


class TestCrossJoin:
    """Test CROSS JOIN functionality."""

    def test_cross_join_cartesian_product(self, db):
        result = db.execute(
            "SELECT * FROM users CROSS JOIN orders"
        )
        # 3 users * 3 orders = 9
        assert len(result) == 9

    def test_cross_join_no_on_clause(self, db):
        # CROSS JOIN should work without ON
        result = db.execute("SELECT * FROM users CROSS JOIN orders")
        assert len(result) == 9


class TestTableAlias:
    """Test table alias support."""

    def test_alias_in_join(self, db):
        result = db.execute(
            "SELECT * FROM users AS u JOIN orders AS o ON u.id = o.user_id"
        )
        assert len(result) == 3
        keys = set(result[0].keys())
        assert "u.id" in keys
        assert "o.amount" in keys

    def test_alias_in_where(self, db):
        result = db.execute(
            "SELECT * FROM users AS u JOIN orders AS o ON u.id = o.user_id WHERE u.name = 'Alice'"
        )
        assert len(result) == 2


class TestQualifiedColumnName:
    """Test qualified column name references."""

    def test_qualified_in_where(self, db):
        result = db.execute(
            "SELECT * FROM users JOIN orders ON users.id = orders.user_id WHERE users.name = 'Alice'"
        )
        assert len(result) == 2

    def test_qualified_in_select(self, db):
        result = db.execute(
            "SELECT users.name, orders.amount FROM users JOIN orders ON users.id = orders.user_id"
        )
        assert len(result) == 3
        for row in result:
            assert "users.name" in row
            assert "orders.amount" in row


class TestMultiTableJoin:
    """Test 3+ table chain JOIN."""

    def test_three_table_join(self, db):
        db.execute("CREATE TABLE products (id INT PRIMARY KEY, name TEXT, order_id INT)")
        db.execute("INSERT INTO products VALUES (1, 'Widget', 1)")
        db.execute("INSERT INTO products VALUES (2, 'Gadget', 2)")

        result = db.execute(
            "SELECT * FROM users JOIN orders ON users.id = orders.user_id "
            "JOIN products ON orders.id = products.order_id"
        )
        assert len(result) == 2  # Alice's 2 orders each have 1 product


class TestJoinWithAggregation:
    """Test JOIN combined with aggregates."""

    def test_join_with_group_by_count(self, db):
        result = db.execute(
            "SELECT users.name, COUNT(orders.id) FROM users LEFT JOIN orders ON users.id = orders.user_id GROUP BY users.name"
        )
        assert len(result) == 3
        # Find each user's count
        counts = {r.get("users.name"): r.get("count") for r in result}
        assert counts["Alice"] == 2
        assert counts["Bob"] == 1
        assert counts["Charlie"] == 0


class TestExplain:
    """Test EXPLAIN functionality."""

    def test_explain_select(self, db):
        result = db.execute("EXPLAIN SELECT * FROM users WHERE id = 1")
        assert "plan" in result
        plan = result["plan"]
        assert any(n["type"] == "SeqScan" for n in plan)
        assert any(n["type"] == "Filter" for n in plan)

    def test_explain_join(self, db):
        result = db.execute(
            "EXPLAIN SELECT * FROM users JOIN orders ON users.id = orders.user_id"
        )
        plan = result["plan"]
        assert any(n["type"] == "SeqScan" for n in plan)
        assert any(n["type"] == "NestedLoopJoin" for n in plan)

    def test_explain_preserves_table(self, db):
        result = db.execute("EXPLAIN SELECT * FROM users")
        plan = result["plan"]
        scan = [n for n in plan if n["type"] == "SeqScan"][0]
        assert scan["table"] == "users"
