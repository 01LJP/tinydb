"""Recursive-descent SQL parser for tinydb.

Consumes a token stream from the lexer and produces an AST node.
Raises ParseError on syntax errors, including line/column information.
"""

from typing import List, Optional

from tinydb.lexer import Token
from tinydb.types import ParseError
from tinydb.ast_nodes import (
    Select, Insert, Update, Delete,
    CreateTable, DropTable, CreateIndex,
    Begin, Commit, Rollback,
    BinaryExpr, ColumnRef, Literal,
    ColumnDefAST,
)


class Parser:
    """Recursive-descent parser that turns tokens into an AST."""

    def __init__(self, tokens: List[Token]):
        self.tokens = tokens
        self.pos = 0

    # ------------------------------------------------------------------
    # Public entry point
    # ------------------------------------------------------------------

    def parse(self):
        """Parse the token stream and return a top-level AST node."""
        if not self.tokens:
            raise ParseError("empty input")
        stmt = self._parse_statement()
        self._expect_eof()
        return stmt

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    def _peek(self) -> Optional[Token]:
        if self.pos < len(self.tokens):
            return self.tokens[self.pos]
        return None

    def _advance(self) -> Token:
        token = self.tokens[self.pos]
        self.pos += 1
        return token

    def _expect(self, token_type: str) -> Token:
        token = self._peek()
        if token is None:
            raise ParseError(
                f"unexpected end of input, expected {token_type}"
            )
        if token.type != token_type:
            raise ParseError(
                f"unexpected token {token.value!r}",
                context=f"line {token.line}, column {token.column}",
            )
        return self._advance()

    def _match(self, *types: str) -> Optional[Token]:
        token = self._peek()
        if token is not None and token.type in types:
            return self._advance()
        return None

    def _expect_eof(self):
        token = self._peek()
        if token is not None:
            raise ParseError(
                f"unexpected token {token.value!r} after end of statement",
                context=f"line {token.line}, column {token.column}",
            )

    def _error(self, msg: str) -> ParseError:
        token = self._peek()
        if token is not None:
            return ParseError(
                msg, context=f"line {token.line}, column {token.column}"
            )
        return ParseError(msg)

    # ------------------------------------------------------------------
    # statement := ddl | dml | txn_cmd
    # ------------------------------------------------------------------

    def _parse_statement(self):
        token = self._peek()
        if token is None:
            raise ParseError("empty input")

        keyword = token.type
        if keyword in ('CREATE', 'DROP'):
            return self._parse_ddl()
        if keyword in ('SELECT', 'INSERT', 'UPDATE', 'DELETE'):
            return self._parse_dml()
        if keyword in ('BEGIN', 'COMMIT', 'ROLLBACK'):
            return self._parse_txn()
        raise self._error(f"unexpected keyword {token.value!r}")

    # ------------------------------------------------------------------
    # DDL: CREATE TABLE / DROP TABLE / CREATE INDEX
    # ------------------------------------------------------------------

    def _parse_ddl(self):
        token = self._peek()
        if token is None:
            raise self._error("incomplete DDL statement")

        if token.type == 'CREATE':
            self._advance()
            sub = self._peek()
            if sub is None:
                raise self._error("incomplete CREATE statement")
            if sub.type == 'TABLE':
                return self._parse_create_table()
            if sub.type == 'INDEX':
                return self._parse_create_index()
            raise self._error(f"unexpected token {sub.value!r} after CREATE")

        if token.type == 'DROP':
            return self._parse_drop_table()

        raise self._error(f"unexpected token {token.value!r} in DDL")

    def _parse_create_table(self):
        self._expect('TABLE')
        name_token = self._expect('IDENT')
        table_name = name_token.value

        self._expect('LPAREN')
        columns = self._parse_column_defs()
        self._expect('RPAREN')

        return CreateTable(table=table_name, columns=columns)

    def _parse_column_defs(self) -> list:
        """Parse comma-separated column definitions."""
        columns = []
        # first column
        columns.append(self._parse_column_def())
        while self._match('COMMA'):
            columns.append(self._parse_column_def())
        return columns

    def _parse_column_def(self) -> ColumnDefAST:
        name_token = self._expect('IDENT')
        col_name = name_token.value

        type_token = self._peek()
        if type_token is None or type_token.type not in ('INT', 'FLOAT', 'TEXT', 'BOOL'):
            raise self._error(f"expected data type for column {col_name!r}")
        self._advance()
        data_type = type_token.value

        # constraints
        nullable = True
        is_unique = False
        is_pk = False
        while True:
            t = self._peek()
            if t is None:
                break
            if t.type == 'PRIMARY':
                self._advance()
                self._expect('KEY')
                is_pk = True
                nullable = False
            elif t.type == 'UNIQUE':
                self._advance()
                is_unique = True
            elif t.type == 'NOT':
                self._advance()
                self._expect('NULL')
                nullable = False
            elif t.type == 'NULL':
                self._advance()
                nullable = True
            else:
                break

        return ColumnDefAST(
            name=col_name,
            data_type=data_type,
            nullable=nullable,
            is_unique=is_unique,
            is_pk=is_pk,
        )

    def _parse_drop_table(self):
        # Handles both DROP TABLE and CREATE-less DROP
        if self._peek().type == 'DROP':
            self._advance()
        self._expect('TABLE')
        name_token = self._expect('IDENT')
        return DropTable(table=name_token.value)

    def _parse_create_index(self):
        self._expect('INDEX')
        self._expect('ON')
        name_token = self._expect('IDENT')
        self._expect('LPAREN')
        col_token = self._expect('IDENT')
        self._expect('RPAREN')
        return CreateIndex(table=name_token.value, column=col_token.value)

    # ------------------------------------------------------------------
    # DML: INSERT / SELECT / UPDATE / DELETE
    # ------------------------------------------------------------------

    def _parse_dml(self):
        keyword = self._peek().type
        if keyword == 'SELECT':
            return self._parse_select()
        if keyword == 'INSERT':
            return self._parse_insert()
        if keyword == 'UPDATE':
            return self._parse_update()
        if keyword == 'DELETE':
            return self._parse_delete()
        raise self._error(f"unexpected DML keyword {keyword}")

    def _parse_select(self):
        self._expect('SELECT')
        columns = self._parse_select_list()
        self._expect('FROM')
        table_token = self._expect('IDENT')
        table = table_token.value

        where = None
        if self._match('WHERE'):
            where = self._parse_where()

        order_by = None
        if self._match('ORDER'):
            self._expect('BY')
            order_by = self._parse_order_by()

        limit = None
        offset = None
        if self._match('LIMIT'):
            limit = self._parse_int_value()
        if self._match('OFFSET'):
            offset = self._parse_int_value()

        return Select(
            columns=columns,
            table=table,
            where=where,
            order_by=order_by,
            limit=limit,
            offset=offset,
        )

    def _parse_select_list(self) -> list:
        if self._match('STAR'):
            return ['*']
        cols = [self._expect('IDENT').value]
        while self._match('COMMA'):
            cols.append(self._expect('IDENT').value)
        return cols

    def _parse_order_by(self):
        col = self._expect('IDENT').value
        direction = 'ASC'
        if self._match('ASC'):
            direction = 'ASC'
        elif self._match('DESC'):
            direction = 'DESC'
        return (col, direction)

    def _parse_int_value(self) -> int:
        token = self._peek()
        if token is None or token.type != 'NUMBER':
            raise self._error("expected integer value")
        value = self._advance().value
        return int(value)

    def _parse_insert(self):
        self._expect('INSERT')
        self._expect('INTO')
        name_token = self._expect('IDENT')
        table = name_token.value

        columns = None
        if self._match('LPAREN'):
            columns = []
            columns.append(self._expect('IDENT').value)
            while self._match('COMMA'):
                columns.append(self._expect('IDENT').value)
            self._expect('RPAREN')

        self._expect('VALUES')
        values = self._parse_value_lists()

        return Insert(table=table, columns=columns, values=values)

    def _parse_value_lists(self) -> list:
        values = [self._parse_value_list()]
        while self._match('COMMA'):
            values.append(self._parse_value_list())
        return values

    def _parse_value_list(self) -> list:
        self._expect('LPAREN')
        vals = [self._parse_value()]
        while self._match('COMMA'):
            vals.append(self._parse_value())
        self._expect('RPAREN')
        return vals

    def _parse_value(self):
        """Parse a single value: number, string, NULL, or boolean."""
        token = self._peek()
        if token is None:
            raise self._error("expected value")
        if token.type == 'NUMBER':
            return self._advance().value
        if token.type == 'STRING':
            return self._advance().value
        if token.type == 'NULL':
            self._advance()
            return None
        if token.type == 'BOOL' or token.type in ('TRUE', 'FALSE'):
            # INT/FLOAT/TEXT/BOOL are keyword tokens; handle TRUE/FALSE if present.
            self._advance()
            return token.type == 'TRUE'
        raise self._error(f"unexpected token {token.value!r} in value list")

    def _parse_update(self):
        self._expect('UPDATE')
        name_token = self._expect('IDENT')
        table = name_token.value

        self._expect('SET')
        set_list = self._parse_set_list()

        where = None
        if self._match('WHERE'):
            where = self._parse_where()

        return Update(table=table, set_list=set_list, where=where)

    def _parse_set_list(self) -> list:
        assignments = [self._parse_assignment()]
        while self._match('COMMA'):
            assignments.append(self._parse_assignment())
        return assignments

    def _parse_assignment(self):
        col = self._expect('IDENT').value
        self._expect('OP')  # =
        value = self._parse_value()
        return (col, value)

    def _parse_delete(self):
        self._expect('DELETE')
        self._expect('FROM')
        name_token = self._expect('IDENT')
        table = name_token.value

        where = None
        if self._match('WHERE'):
            where = self._parse_where()

        return Delete(table=table, where=where)

    # ------------------------------------------------------------------
    # WHERE conditions
    # ------------------------------------------------------------------

    def _parse_where(self):
        """Parse WHERE condition: expr ((AND | OR) expr)*"""
        left = self._parse_expression()
        while self._peek() is not None and self._peek().type in ('AND', 'OR'):
            op = self._advance().value
            right = self._parse_expression()
            left = BinaryExpr(left=left, op=op, right=right)
        return left

    def _parse_expression(self):
        """Parse a comparison expression: term OP term."""
        left = self._parse_term()
        token = self._peek()
        if token is not None and token.type == 'OP':
            op = self._advance().value
            right = self._parse_term()
            return BinaryExpr(left=left, op=op, right=right)
        return left

    def _parse_term(self):
        """Parse a single term: column reference or literal."""
        token = self._peek()
        if token is None:
            raise self._error("expected expression term")
        if token.type == 'IDENT':
            self._advance()
            return ColumnRef(name=token.value)
        if token.type == 'NUMBER':
            self._advance()
            return Literal(value=token.value)
        if token.type == 'STRING':
            self._advance()
            return Literal(value=token.value)
        if token.type == 'NULL':
            self._advance()
            return Literal(value=None)
        raise self._error(f"unexpected token {token.value!r} in expression")

    # ------------------------------------------------------------------
    # Transaction commands
    # ------------------------------------------------------------------

    def _parse_txn(self):
        keyword = self._advance().type
        if keyword == 'BEGIN':
            return Begin()
        if keyword == 'COMMIT':
            return Commit()
        if keyword == 'ROLLBACK':
            return Rollback()
        raise self._error(f"unknown transaction command {keyword}")
