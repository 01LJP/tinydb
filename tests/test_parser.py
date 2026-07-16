"""Tests for tinydb SQL parser (recursive descent)."""

import pytest

from tinydb.lexer import Lexer
from tinydb.parser import Parser
from tinydb.ast_nodes import (
    Select, Insert, Update, Delete,
    CreateTable, DropTable, CreateIndex,
    Begin, Commit, Rollback,
    BinaryExpr, ColumnRef, Literal,
)
from tinydb.types import ParseError


def parse(sql: str):
    """Helper: lex + parse a SQL string into an AST."""
    return Parser(Lexer().tokenize(sql)).parse()


# =========================================================================
# SELECT tests
# =========================================================================

class TestSelect:
    def test_select_star(self):
        ast = parse("SELECT * FROM users")
        assert isinstance(ast, Select)
        assert ast.columns == ['*']
        assert ast.table == 'users'
        assert ast.where is None
        assert ast.order_by is None
        assert ast.limit is None
        assert ast.offset is None

    def test_select_columns(self):
        ast = parse("SELECT id, name FROM users")
        assert ast.columns == ['id', 'name']
        assert ast.table == 'users'

    def test_select_where(self):
        ast = parse("SELECT * FROM users WHERE id = 1")
        assert isinstance(ast.where, BinaryExpr)
        assert ast.where.op == '='
        assert isinstance(ast.where.left, ColumnRef)
        assert ast.where.left.name == 'id'
        assert isinstance(ast.where.right, Literal)
        assert ast.where.right.value == 1

    def test_select_order_by_asc(self):
        ast = parse("SELECT * FROM users ORDER BY name ASC")
        assert ast.order_by == ('name', 'ASC')

    def test_select_order_by_desc(self):
        ast = parse("SELECT * FROM users ORDER BY age DESC")
        assert ast.order_by == ('age', 'DESC')

    def test_select_limit(self):
        ast = parse("SELECT * FROM users LIMIT 10")
        assert ast.limit == 10

    def test_select_offset(self):
        ast = parse("SELECT * FROM users LIMIT 10 OFFSET 5")
        assert ast.limit == 10
        assert ast.offset == 5

    def test_select_where_and(self):
        ast = parse("SELECT * FROM t WHERE a = 1 AND b = 2")
        # AND should be top-level (left-associative: (a=1) AND (b=2))
        assert isinstance(ast.where, BinaryExpr)
        assert ast.where.op == 'AND'

    def test_select_where_or(self):
        ast = parse("SELECT * FROM t WHERE a = 1 OR b = 2")
        assert isinstance(ast.where, BinaryExpr)
        assert ast.where.op == 'OR'

    def test_select_where_gt(self):
        ast = parse("SELECT * FROM t WHERE age > 18")
        assert ast.where.op == '>'
        assert ast.where.right.value == 18

    def test_select_where_string_compare(self):
        ast = parse("SELECT * FROM t WHERE name = 'Alice'")
        assert ast.where.right.value == 'Alice'

    def test_select_full(self):
        ast = parse("SELECT id, name FROM users WHERE age > 18 ORDER BY name ASC LIMIT 5 OFFSET 10")
        assert ast.columns == ['id', 'name']
        assert ast.where.op == '>'
        assert ast.order_by == ('name', 'ASC')
        assert ast.limit == 5
        assert ast.offset == 10


# =========================================================================
# INSERT tests
# =========================================================================

class TestInsert:
    def test_insert_values(self):
        ast = parse("INSERT INTO users VALUES (1, 'Alice', 30)")
        assert isinstance(ast, Insert)
        assert ast.table == 'users'
        assert ast.columns is None
        assert ast.values == [[1, 'Alice', 30]]

    def test_insert_with_columns(self):
        ast = parse("INSERT INTO users (id, name) VALUES (1, 'Alice')")
        assert ast.columns == ['id', 'name']
        assert ast.values == [[1, 'Alice']]

    def test_insert_multiple_rows(self):
        ast = parse("INSERT INTO users VALUES (1, 'A'), (2, 'B')")
        assert len(ast.values) == 2
        assert ast.values[0] == [1, 'A']
        assert ast.values[1] == [2, 'B']


# =========================================================================
# UPDATE tests
# =========================================================================

class TestUpdate:
    def test_update_set(self):
        ast = parse("UPDATE users SET name = 'Bob'")
        assert isinstance(ast, Update)
        assert ast.table == 'users'
        assert ast.set_list == [('name', 'Bob')]
        assert ast.where is None

    def test_update_set_where(self):
        ast = parse("UPDATE users SET name = 'Bob' WHERE id = 1")
        assert ast.set_list == [('name', 'Bob')]
        assert isinstance(ast.where, BinaryExpr)

    def test_update_multiple_sets(self):
        ast = parse("UPDATE users SET name = 'Bob', age = 30 WHERE id = 1")
        assert ast.set_list == [('name', 'Bob'), ('age', 30)]


# =========================================================================
# DELETE tests
# =========================================================================

class TestDelete:
    def test_delete_all(self):
        ast = parse("DELETE FROM users")
        assert isinstance(ast, Delete)
        assert ast.table == 'users'
        assert ast.where is None

    def test_delete_where(self):
        ast = parse("DELETE FROM users WHERE id = 1")
        assert isinstance(ast.where, BinaryExpr)
        assert ast.where.left.name == 'id'


# =========================================================================
# CREATE TABLE tests
# =========================================================================

class TestCreateTable:
    def test_create_table_simple(self):
        ast = parse("CREATE TABLE users (id INT, name TEXT)")
        assert isinstance(ast, CreateTable)
        assert ast.table == 'users'
        assert len(ast.columns) == 2
        assert ast.columns[0].name == 'id'
        assert ast.columns[0].data_type == 'INT'
        assert ast.columns[1].name == 'name'
        assert ast.columns[1].data_type == 'TEXT'

    def test_create_table_pk(self):
        ast = parse("CREATE TABLE users (id INT PRIMARY KEY, name TEXT)")
        assert ast.columns[0].is_pk is True
        assert ast.columns[0].nullable is False

    def test_create_table_unique(self):
        ast = parse("CREATE TABLE t (email TEXT UNIQUE)")
        assert ast.columns[0].is_unique is True

    def test_create_table_not_null(self):
        ast = parse("CREATE TABLE t (name TEXT NOT NULL)")
        assert ast.columns[0].nullable is False

    def test_create_table_all_types(self):
        ast = parse("CREATE TABLE t (a INT, b FLOAT, c TEXT, d BOOL)")
        types = [c.data_type for c in ast.columns]
        assert types == ['INT', 'FLOAT', 'TEXT', 'BOOL']


# =========================================================================
# DROP TABLE tests
# =========================================================================

class TestDropTable:
    def test_drop_table(self):
        ast = parse("DROP TABLE users")
        assert isinstance(ast, DropTable)
        assert ast.table == 'users'


# =========================================================================
# CREATE INDEX tests
# =========================================================================

class TestCreateIndex:
    def test_create_index(self):
        ast = parse("CREATE INDEX ON users (name)")
        assert isinstance(ast, CreateIndex)
        assert ast.table == 'users'
        assert ast.column == 'name'


# =========================================================================
# Transaction command tests
# =========================================================================

class TestTransactionCommands:
    def test_begin(self):
        ast = parse("BEGIN")
        assert isinstance(ast, Begin)

    def test_commit(self):
        ast = parse("COMMIT")
        assert isinstance(ast, Commit)

    def test_rollback(self):
        ast = parse("ROLLBACK")
        assert isinstance(ast, Rollback)


# =========================================================================
# Expression edge cases
# =========================================================================

class TestExpressions:
    def test_and_or_nesting(self):
        ast = parse("SELECT * FROM t WHERE a = 1 AND b = 2 OR c = 3")
        # left-associative AND binds tighter in our grammar (condition -> expr (AND|OR expr)*)
        # so top-level is OR with left = (a=1 AND b=2), right = c=3
        assert isinstance(ast.where, BinaryExpr)

    def test_not_equals_bang(self):
        ast = parse("SELECT * FROM t WHERE id != 1")
        assert ast.where.op == '!='

    def test_not_equals_angle(self):
        ast = parse("SELECT * FROM t WHERE id <> 1")
        assert ast.where.op == '<>'

    def test_less_equal(self):
        ast = parse("SELECT * FROM t WHERE age <= 30")
        assert ast.where.op == '<='

    def test_greater_equal(self):
        ast = parse("SELECT * FROM t WHERE age >= 18")
        assert ast.where.op == '>='

    def test_null_literal(self):
        ast = parse("SELECT * FROM t WHERE name = NULL")
        assert isinstance(ast.where.right, Literal)
        assert ast.where.right.value is None


# =========================================================================
# Error handling
# =========================================================================

class TestParserErrors:
    def test_empty_input_raises(self):
        with pytest.raises(ParseError):
            parse("")

    def test_unknown_statement_raises(self):
        with pytest.raises(ParseError):
            parse("FOOBAR")

    def test_select_missing_from_raises(self):
        with pytest.raises(ParseError):
            parse("SELECT * users")

    def test_unexpected_end_raises(self):
        with pytest.raises(ParseError):
            parse("SELECT * FROM")

    def test_create_table_missing_paren_raises(self):
        with pytest.raises(ParseError):
            parse("CREATE TABLE t id INT")
