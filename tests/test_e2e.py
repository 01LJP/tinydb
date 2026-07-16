"""End-to-end integration tests for tinydb.

Covers: full workflow (create-insert-query-index-transaction-persist-restart),
transaction commit/rollback, constraint violations, and aggregate functions.
"""

import os
import tempfile
import pytest

import tinydb


# =========================================================================
# Helpers
# =========================================================================

def _temp_path():
    """Return a fresh temporary file path (file itself is not created)."""
    f = tempfile.NamedTemporaryFile(suffix=".db", delete=False)
    path = f.name
    f.close()
    os.unlink(path)
    return path


def _cleanup(path):
    """Remove the db file and its WAL if they exist."""
    if os.path.exists(path):
        os.unlink(path)
    wal = path + ".wal"
    if os.path.exists(wal):
        os.unlink(wal)


# =========================================================================
# Full workflow
# =========================================================================

class TestFullWorkflow:
    """Create → Insert → Query → Index → Transaction → Persist → Restart."""

    def test_create_insert_select(self):
        path = _temp_path()
        try:
            with tinydb.open(path) as db:
                db.execute("CREATE TABLE users (id INT PRIMARY KEY, name TEXT, age INT)")
                db.execute("INSERT INTO users VALUES (1, 'Alice', 30)")
                db.execute("INSERT INTO users VALUES (2, 'Bob', 25)")
                result = db.execute("SELECT * FROM users WHERE age > 26")
                assert len(result) == 1
                assert result[0]["name"] == "Alice"
        finally:
            _cleanup(path)

    def test_persistence_across_restart(self):
        path = _temp_path()
        try:
            with tinydb.open(path) as db:
                db.execute("CREATE TABLE users (id INT PRIMARY KEY, name TEXT, age INT)")
                db.execute("INSERT INTO users VALUES (1, 'Alice', 30)")
                db.execute("INSERT INTO users VALUES (2, 'Bob', 25)")
                result = db.execute("SELECT * FROM users")
                assert len(result) == 2

            # Restart: reopen the same file.
            with tinydb.open(path) as db:
                result = db.execute("SELECT * FROM users")
                assert len(result) == 2
                names = {r["name"] for r in result}
                assert names == {"Alice", "Bob"}
        finally:
            _cleanup(path)

    def test_create_index(self):
        path = _temp_path()
        try:
            with tinydb.open(path) as db:
                db.execute("CREATE TABLE items (id INT PRIMARY KEY, name TEXT, price FLOAT)")
                db.execute("INSERT INTO items VALUES (1, 'apple', 1.5)")
                db.execute("INSERT INTO items VALUES (2, 'banana', 0.75)")
                # CREATE INDEX should succeed and return status ok
                result = db.execute("CREATE INDEX ON items (name)")
                assert result == {"status": "ok"}
        finally:
            _cleanup(path)

    def test_drop_table(self):
        path = _temp_path()
        try:
            with tinydb.open(path) as db:
                db.execute("CREATE TABLE tmp (id INT PRIMARY KEY)")
                db.execute("INSERT INTO tmp VALUES (1)")
                db.execute("DROP TABLE tmp")
                with pytest.raises(Exception):
                    db.execute("SELECT * FROM tmp")
        finally:
            _cleanup(path)

    def test_update_and_delete(self):
        path = _temp_path()
        try:
            with tinydb.open(path) as db:
                db.execute("CREATE TABLE t (id INT PRIMARY KEY, val TEXT)")
                db.execute("INSERT INTO t VALUES (1, 'a')")
                db.execute("INSERT INTO t VALUES (2, 'b')")
                db.execute("INSERT INTO t VALUES (3, 'c')")

                # UPDATE
                result = db.execute("UPDATE t SET val = 'x' WHERE id = 2")
                assert result == {"affected_rows": 1}
                rows = db.execute("SELECT val FROM t WHERE id = 2")
                assert rows[0]["val"] == "x"

                # DELETE
                result = db.execute("DELETE FROM t WHERE id = 3")
                assert result == {"affected_rows": 1}
                rows = db.execute("SELECT * FROM t")
                assert len(rows) == 2
        finally:
            _cleanup(path)

    def test_order_by_limit_offset(self):
        path = _temp_path()
        try:
            with tinydb.open(path) as db:
                db.execute("CREATE TABLE n (id INT PRIMARY KEY, v INT)")
                for i in range(1, 6):
                    db.execute(f"INSERT INTO n VALUES ({i}, {i * 10})")
                rows = db.execute("SELECT * FROM n ORDER BY v DESC LIMIT 2 OFFSET 1")
                assert len(rows) == 2
                assert rows[0]["v"] == 40
                assert rows[1]["v"] == 30
        finally:
            _cleanup(path)


# =========================================================================
# Transaction tests
# =========================================================================

class TestTransactionRollback:
    def test_rollback_undoes_insert(self):
        path = _temp_path()
        try:
            with tinydb.open(path) as db:
                db.execute("CREATE TABLE t (id INT PRIMARY KEY, val TEXT)")
                db.execute("INSERT INTO t VALUES (1, 'a')")

                db.execute("BEGIN")
                db.execute("INSERT INTO t VALUES (2, 'b')")
                db.execute("ROLLBACK")

                rows = db.execute("SELECT * FROM t")
                assert len(rows) == 1
                assert rows[0]["id"] == 1
        finally:
            _cleanup(path)

    def test_rollback_undoes_update(self):
        path = _temp_path()
        try:
            with tinydb.open(path) as db:
                db.execute("CREATE TABLE t (id INT PRIMARY KEY, val TEXT)")
                db.execute("INSERT INTO t VALUES (1, 'original')")

                db.execute("BEGIN")
                db.execute("UPDATE t SET val = 'changed' WHERE id = 1")
                db.execute("ROLLBACK")

                rows = db.execute("SELECT val FROM t WHERE id = 1")
                assert rows[0]["val"] == "original"
        finally:
            _cleanup(path)


class TestTransactionCommit:
    def test_commit_persists_insert(self):
        path = _temp_path()
        try:
            with tinydb.open(path) as db:
                db.execute("CREATE TABLE t (id INT PRIMARY KEY, val TEXT)")
                db.execute("BEGIN")
                db.execute("INSERT INTO t VALUES (1, 'committed')")
                db.execute("COMMIT")

                rows = db.execute("SELECT * FROM t")
                assert len(rows) == 1
                assert rows[0]["val"] == "committed"
        finally:
            _cleanup(path)

    def test_commit_persists_across_restart(self):
        path = _temp_path()
        try:
            with tinydb.open(path) as db:
                db.execute("CREATE TABLE t (id INT PRIMARY KEY, val TEXT)")
                db.execute("BEGIN")
                db.execute("INSERT INTO t VALUES (1, 'durability')")
                db.execute("COMMIT")

            with tinydb.open(path) as db:
                rows = db.execute("SELECT * FROM t")
                assert len(rows) == 1
                assert rows[0]["val"] == "durability"
        finally:
            _cleanup(path)


# =========================================================================
# Constraint tests
# =========================================================================

class TestConstraints:
    def test_primary_key_uniqueness(self):
        path = _temp_path()
        try:
            with tinydb.open(path) as db:
                db.execute("CREATE TABLE t (id INT PRIMARY KEY, val TEXT)")
                db.execute("INSERT INTO t VALUES (1, 'a')")
                with pytest.raises(Exception):
                    db.execute("INSERT INTO t VALUES (1, 'b')")
        finally:
            _cleanup(path)

    def test_not_null_rejects_null(self):
        path = _temp_path()
        try:
            with tinydb.open(path) as db:
                db.execute("CREATE TABLE t (id INT PRIMARY KEY, name TEXT NOT NULL)")
                with pytest.raises(Exception):
                    db.execute("INSERT INTO t VALUES (1, NULL)")
                # Valid insert should still work
                db.execute("INSERT INTO t VALUES (1, 'Alice')")
                rows = db.execute("SELECT * FROM t")
                assert len(rows) == 1
        finally:
            _cleanup(path)

    def test_unique_constraint(self):
        path = _temp_path()
        try:
            with tinydb.open(path) as db:
                db.execute("CREATE TABLE t (id INT PRIMARY KEY, email TEXT UNIQUE)")
                db.execute("INSERT INTO t VALUES (1, 'a@b.c')")
                with pytest.raises(Exception):
                    db.execute("INSERT INTO t VALUES (2, 'a@b.c')")
                # Different email should work
                db.execute("INSERT INTO t VALUES (2, 'd@e.f')")
                rows = db.execute("SELECT * FROM t")
                assert len(rows) == 2
        finally:
            _cleanup(path)


# =========================================================================
# Aggregate tests
# =========================================================================

class TestAggregates:
    def test_count_star(self):
        path = _temp_path()
        try:
            with tinydb.open(path) as db:
                db.execute("CREATE TABLE t (id INT PRIMARY KEY, v INT)")
                db.execute("INSERT INTO t VALUES (1, 10)")
                db.execute("INSERT INTO t VALUES (2, 20)")
                db.execute("INSERT INTO t VALUES (3, 30)")
                result = db.execute("SELECT COUNT(*) FROM t")
                assert result == [{"count": 3}]
        finally:
            _cleanup(path)

    def test_sum(self):
        path = _temp_path()
        try:
            with tinydb.open(path) as db:
                db.execute("CREATE TABLE t (id INT PRIMARY KEY, v INT)")
                db.execute("INSERT INTO t VALUES (1, 10)")
                db.execute("INSERT INTO t VALUES (2, 20)")
                db.execute("INSERT INTO t VALUES (3, 30)")
                result = db.execute("SELECT SUM(v) FROM t")
                assert result == [{"sum": 60}]
        finally:
            _cleanup(path)

    def test_avg(self):
        path = _temp_path()
        try:
            with tinydb.open(path) as db:
                db.execute("CREATE TABLE t (id INT PRIMARY KEY, v INT)")
                db.execute("INSERT INTO t VALUES (1, 10)")
                db.execute("INSERT INTO t VALUES (2, 20)")
                db.execute("INSERT INTO t VALUES (3, 30)")
                result = db.execute("SELECT AVG(v) FROM t")
                assert len(result) == 1
                assert result[0]["avg"] == pytest.approx(20.0)
        finally:
            _cleanup(path)

    def test_group_by(self):
        path = _temp_path()
        try:
            with tinydb.open(path) as db:
                db.execute("CREATE TABLE t (id INT PRIMARY KEY, dept TEXT, salary FLOAT)")
                db.execute("INSERT INTO t VALUES (1, 'eng', 100)")
                db.execute("INSERT INTO t VALUES (2, 'eng', 200)")
                db.execute("INSERT INTO t VALUES (3, 'sales', 50)")
                result = db.execute(
                    "SELECT dept, COUNT(*), AVG(salary) FROM t GROUP BY dept ORDER BY dept"
                )
                assert len(result) == 2
                by_dept = {r["dept"]: r for r in result}
                assert by_dept["eng"]["count"] == 2
                assert by_dept["eng"]["avg"] == pytest.approx(150.0)
                assert by_dept["sales"]["count"] == 1
                assert by_dept["sales"]["avg"] == pytest.approx(50.0)
        finally:
            _cleanup(path)
