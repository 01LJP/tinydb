"""Regression tests for critical bugs C1, C3 and the parser guard I1.

These tests are written in TDD style: each test codifies the *expected*
behavior (i.e. a correct database) so that the existing buggy implementation
fails, and the fix makes them pass.
"""

import os
import tempfile

import pytest

import tinydb
from tinydb.lexer import Lexer
from tinydb.parser import Parser
from tinydb.types import ParseError


# =========================================================================
# Helpers
# =========================================================================

def _temp_path():
    f = tempfile.NamedTemporaryFile(suffix=".db", delete=False)
    path = f.name
    f.close()
    os.unlink(path)
    return path


def _cleanup(path):
    if os.path.exists(path):
        os.unlink(path)
    wal = path + ".wal"
    if os.path.exists(wal):
        os.unlink(wal)


# =========================================================================
# C1: UPDATE that grows a short value must NOT corrupt other records.
# =========================================================================

class TestC1RecordOverflow:
    """UPDATE short -> long must not overflow the page slot."""

    def test_short_to_long_does_not_corrupt_other_rows(self):
        """After extending val from 1 char to 600 chars no other row is lost."""
        path = _temp_path()
        try:
            with tinydb.open(path) as db:
                db.execute("CREATE TABLE t (id INT PRIMARY KEY, val TEXT)")
                db.execute("INSERT INTO t VALUES (1, 'a')")
                db.execute("INSERT INTO t VALUES (2, 'b')")
                db.execute("INSERT INTO t VALUES (3, 'c')")

                # Grow row 1's val far beyond the original 1-byte payload.
                long_val = "X" * 600
                result = db.execute(
                    f"UPDATE t SET val = '{long_val}' WHERE id = 1"
                )
                assert result == {"affected_rows": 1}

                rows = {r["id"]: r["val"] for r in db.execute("SELECT * FROM t")}
                assert len(rows) == 3, f"expected 3 rows, got {len(rows)}: {rows}"
                assert rows[1] == long_val
                assert rows[2] == "b"
                assert rows[3] == "c"
        finally:
            _cleanup(path)

    def test_short_to_long_preserves_data_after_many_updates(self):
        """Repeated grow-shrink cycles must not corrupt the table."""
        path = _temp_path()
        try:
            with tinydb.open(path) as db:
                db.execute("CREATE TABLE t (id INT PRIMARY KEY, val TEXT)")
                for i in range(1, 6):
                    db.execute(f"INSERT INTO t VALUES ({i}, '{i}')")

                # Grow every row to a long string.
                for i in range(1, 6):
                    db.execute(
                        f"UPDATE t SET val = '{'Z' * 300}' WHERE id = {i}"
                    )

                rows = {r["id"]: r["val"] for r in db.execute("SELECT * FROM t")}
                assert len(rows) == 5
                for i in range(1, 6):
                    assert rows[i] == "Z" * 300, f"row {i} corrupted"
        finally:
            _cleanup(path)


# =========================================================================
# C3: UPDATE must keep the B-tree index in sync.
# =========================================================================

class TestC3IndexSync:
    """UPDATE must update the index so the new value is findable."""

    def test_update_indexed_column_value(self):
        """After UPDATE, an index lookup on the new value returns the row."""
        path = _temp_path()
        try:
            with tinydb.open(path) as db:
                db.execute("CREATE TABLE t (id INT PRIMARY KEY, name TEXT)")
                db.execute("INSERT INTO t VALUES (1, 'Alice')")
                db.execute("INSERT INTO t VALUES (2, 'Bob')")
                db.execute("CREATE INDEX ON t (name)")

                # Sanity check: Alice is findable via the index.
                bt = db.index_manager.get_index("t", "name")
                assert bt.search("Alice") != -1

                # Update Alice -> Carol.
                db.execute("UPDATE t SET name = 'Carol' WHERE id = 1")

                # Old value must no longer be in the index.
                assert bt.search("Alice") == -1
                # New value must be in the index.
                assert bt.search("Carol") != -1
        finally:
            _cleanup(path)

    def test_update_non_indexed_column_leaves_index_intact(self):
        """Updating a non-indexed column must not disturb the index."""
        path = _temp_path()
        try:
            with tinydb.open(path) as db:
                db.execute("CREATE TABLE t (id INT PRIMARY KEY, name TEXT, age INT)")
                db.execute("INSERT INTO t VALUES (1, 'Alice', 30)")
                db.execute("CREATE INDEX ON t (name)")

                db.execute("UPDATE t SET age = 31 WHERE id = 1")

                bt = db.index_manager.get_index("t", "name")
                assert bt.search("Alice") != -1
                assert db.execute("SELECT age FROM t WHERE id = 1")[0]["age"] == 31
        finally:
            _cleanup(path)


# =========================================================================
# I1: Parser UPDATE SET must reject any operator other than '='.
# =========================================================================

class TestI1ParserSetOperator:
    """UPDATE SET col <op> value must only accept '='."""

    def test_reject_plus_operator(self):
        # Correct SET parses fine.
        Parser(Lexer().tokenize("UPDATE t SET val = 1")).parse()
        # Any other OP is rejected.
        with pytest.raises(ParseError):
            Parser(Lexer().tokenize("UPDATE t SET val + 1")).parse()

    def test_reject_minus_operator(self):
        with pytest.raises(ParseError):
            Parser(Lexer().tokenize("UPDATE t SET val - 1")).parse()

    def test_accept_equals_operator(self):
        # Should parse without error.
        ast = Parser(Lexer().tokenize("UPDATE t SET val = 5")).parse()
        assert ast.set_list == [("val", 5)]
