"""Tests for CLI enhancements."""

import os
import tempfile
import pytest

import tinydb
from tinydb.cli import handle_meta_command, _highlight_sql, _dump_db, VERSION


@pytest.fixture
def db():
    """Create a temporary database with test tables."""
    with tempfile.NamedTemporaryFile(suffix=".tdb", delete=False) as f:
        path = f.name
    try:
        with tinydb.open(path) as db:
            db.execute("CREATE TABLE users (id INT PRIMARY KEY, name TEXT)")
            db.execute("INSERT INTO users VALUES (1, 'Alice')")
            db.execute("INSERT INTO users VALUES (2, 'Bob')")
            yield db
    finally:
        if os.path.exists(path):
            os.unlink(path)
        if os.path.exists(path + ".wal"):
            os.unlink(path + ".wal")


class TestExplain:
    """Test EXPLAIN functionality."""

    def test_explain_select(self, db):
        result = db.execute("EXPLAIN SELECT * FROM users WHERE id = 1")
        assert "plan" in result
        plan = result["plan"]
        assert any(n["type"] == "SeqScan" for n in plan)
        assert any(n["type"] == "Filter" for n in plan)

    def test_explain_join(self, db):
        db.execute("CREATE TABLE orders (id INT, user_id INT)")
        result = db.execute(
            "EXPLAIN SELECT * FROM users JOIN orders ON users.id = orders.user_id"
        )
        plan = result["plan"]
        assert any(n["type"] == "SeqScan" for n in plan)
        assert any(n["type"] == "NestedLoopJoin" for n in plan)

    def test_explain_preserves_table_name(self, db):
        result = db.execute("EXPLAIN SELECT * FROM users")
        plan = result["plan"]
        scan = [n for n in plan if n["type"] == "SeqScan"][0]
        assert scan["table"] == "users"


class TestMetaCommands:
    """Test meta commands."""

    def test_version(self, db, capsys):
        handle_meta_command(db, ".version")
        captured = capsys.readouterr()
        assert VERSION in captured.out

    def test_tables(self, db, capsys):
        handle_meta_command(db, ".tables")
        captured = capsys.readouterr()
        assert "users" in captured.out

    def test_schema(self, db, capsys):
        handle_meta_command(db, ".schema")
        captured = capsys.readouterr()
        assert "CREATE TABLE users" in captured.out
        assert "id INT" in captured.out
        assert "name TEXT" in captured.out

    def test_mode_set(self, db, capsys):
        _, mode = handle_meta_command(db, ".mode csv")
        assert mode == "csv"
        _, mode = handle_meta_command(db, ".mode table")
        assert mode == "table"

    def test_mode_show(self, db, capsys):
        handle_meta_command(db, ".mode")
        captured = capsys.readouterr()
        assert "table" in captured.out or "csv" in captured.out

    def test_explain_meta(self, db, capsys):
        handle_meta_command(db, ".explain SELECT * FROM users")
        captured = capsys.readouterr()
        assert "SeqScan" in captured.out

    def test_help(self, db, capsys):
        handle_meta_command(db, ".help")
        captured = capsys.readouterr()
        assert ".tables" in captured.out
        assert ".explain" in captured.out
        assert ".dump" in captured.out
        assert ".version" in captured.out


class TestSyntaxHighlighting:
    """Test SQL syntax highlighting."""

    def test_keyword_highlight(self):
        result = _highlight_sql("SELECT * FROM users")
        assert "\033[1;34m" in result  # keyword color present
        assert "SELECT" in result
        assert "FROM" in result

    def test_string_highlight(self):
        result = _highlight_sql("WHERE name = 'Alice'")
        assert "\033[0;32m" in result  # string color present
        assert "'Alice'" in result

    def test_number_highlight(self):
        result = _highlight_sql("WHERE age > 25")
        assert "\033[0;33m" in result  # number color present
        assert "25" in result

    def test_mixed_highlight(self):
        result = _highlight_sql("SELECT * FROM users WHERE id = 1 AND name = 'Alice'")
        # Should not raise any errors
        assert len(result) > 0


class TestDump:
    """Test .dump functionality."""

    def test_dump_all(self, db, capsys):
        _dump_db(db)
        captured = capsys.readouterr()
        assert "CREATE TABLE users" in captured.out
        assert "INSERT INTO users" in captured.out
        assert "'Alice'" in captured.out
        assert "'Bob'" in captured.out

    def test_dump_specific_table(self, db, capsys):
        _dump_db(db, "users")
        captured = capsys.readouterr()
        assert "CREATE TABLE users" in captured.out
        assert "INSERT INTO users" in captured.out

    def test_dump_nonexistent_table(self, db, capsys):
        _dump_db(db, "nonexistent")
        captured = capsys.readouterr()
        assert "does not exist" in captured.out


class TestCSVMode:
    """Test CSV output mode."""

    def test_csv_output(self, db, capsys):
        from tinydb.cli import _display_rows_csv
        rows = db.execute("SELECT * FROM users")
        _display_rows_csv(rows)
        captured = capsys.readouterr()
        assert "id,name" in captured.out
        assert "1,Alice" in captured.out
