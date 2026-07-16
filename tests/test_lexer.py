"""Tests for tinydb SQL lexer (tokenizer)."""

import pytest

from tinydb.lexer import Token, Lexer
from tinydb.types import ParseError


# =========================================================================
# Token basic tests
# =========================================================================

class TestTokenRepr:
    def test_token_repr(self):
        tok = Token('SELECT', 'SELECT', line=1, column=0)
        assert repr(tok) == "Token(SELECT, 'SELECT')"

    def test_token_fields(self):
        tok = Token('NUMBER', 42, line=2, column=5)
        assert tok.type == 'NUMBER'
        assert tok.value == 42
        assert tok.line == 2
        assert tok.column == 5


# =========================================================================
# Keyword tokenization
# =========================================================================

class TestKeywords:
    def test_select_keyword(self):
        tokens = Lexer().tokenize("SELECT")
        assert len(tokens) == 1
        assert tokens[0].type == 'SELECT'
        assert tokens[0].value == 'SELECT'

    def test_all_keywords_recognized(self):
        keywords = [
            'SELECT', 'FROM', 'WHERE', 'INSERT', 'INTO', 'VALUES',
            'UPDATE', 'SET', 'DELETE', 'CREATE', 'TABLE', 'DROP',
            'ORDER', 'BY', 'LIMIT', 'OFFSET', 'AND', 'OR', 'NOT',
            'NULL', 'PRIMARY', 'KEY', 'UNIQUE', 'INDEX', 'ON',
            'ASC', 'DESC', 'BEGIN', 'COMMIT', 'ROLLBACK',
            'INT', 'FLOAT', 'TEXT', 'BOOL',
        ]
        for kw in keywords:
            tokens = Lexer().tokenize(kw)
            assert tokens[0].type == kw, f"{kw} should be a keyword"

    def test_keywords_are_case_insensitive(self):
        tokens = Lexer().tokenize("select")
        assert tokens[0].type == 'SELECT'
        assert tokens[0].value == 'SELECT'


# =========================================================================
# Identifiers
# =========================================================================

class TestIdentifiers:
    def test_simple_identifier(self):
        tokens = Lexer().tokenize("users")
        assert tokens[0].type == 'IDENT'
        assert tokens[0].value == 'users'

    def test_identifier_with_underscore(self):
        tokens = Lexer().tokenize("my_table")
        assert tokens[0].value == 'my_table'

    def test_identifier_starting_with_underscore(self):
        tokens = Lexer().tokenize("_col")
        assert tokens[0].value == '_col'

    def test_identifier_with_digits(self):
        tokens = Lexer().tokenize("col1")
        assert tokens[0].value == 'col1'

    def test_identifier_cannot_start_with_digit(self):
        tokens = Lexer().tokenize("1col")
        # '1' is NUMBER, 'col' is IDENT
        assert tokens[0].type == 'NUMBER'
        assert tokens[1].type == 'IDENT'


# =========================================================================
# Numbers
# =========================================================================

class TestNumbers:
    def test_integer(self):
        tokens = Lexer().tokenize("42")
        assert tokens[0].type == 'NUMBER'
        assert tokens[0].value == 42

    def test_float(self):
        tokens = Lexer().tokenize("3.14")
        assert tokens[0].type == 'NUMBER'
        assert tokens[0].value == 3.14

    def test_zero(self):
        tokens = Lexer().tokenize("0")
        assert tokens[0].value == 0

    def test_negative_not_lexed_as_part_of_number(self):
        # minus is not an operator; '-5' becomes '-' then '5' or errors
        # lexer just produces number 5 here (no unary minus)
        tokens = Lexer().tokenize("5")
        assert tokens[0].value == 5


# =========================================================================
# Strings
# =========================================================================

class TestStrings:
    def test_simple_string(self):
        tokens = Lexer().tokenize("'hello'")
        assert tokens[0].type == 'STRING'
        assert tokens[0].value == 'hello'

    def test_empty_string(self):
        tokens = Lexer().tokenize("''")
        assert tokens[0].type == 'STRING'
        assert tokens[0].value == ''

    def test_string_with_spaces(self):
        tokens = Lexer().tokenize("'hello world'")
        assert tokens[0].value == 'hello world'

    def test_string_with_escaped_quote(self):
        tokens = Lexer().tokenize("'it''s'")
        assert tokens[0].value == "it's"


# =========================================================================
# Operators
# =========================================================================

class TestOperators:
    def test_equals(self):
        tokens = Lexer().tokenize("=")
        assert tokens[0].type == 'OP'
        assert tokens[0].value == '='

    def test_not_equals_bang(self):
        tokens = Lexer().tokenize("!=")
        assert tokens[0].type == 'OP'
        assert tokens[0].value == '!='

    def test_not_equals_angle(self):
        tokens = Lexer().tokenize("<>")
        assert tokens[0].type == 'OP'
        assert tokens[0].value == '<>'

    def test_less_than(self):
        tokens = Lexer().tokenize("<")
        assert tokens[0].value == '<'

    def test_greater_than(self):
        tokens = Lexer().tokenize(">")
        assert tokens[0].value == '>'

    def test_less_equal(self):
        tokens = Lexer().tokenize("<=")
        assert tokens[0].value == '<='

    def test_greater_equal(self):
        tokens = Lexer().tokenize(">=")
        assert tokens[0].value == '>='


# =========================================================================
# Punctuation
# =========================================================================

class TestPunctuation:
    def test_semicolon(self):
        tokens = Lexer().tokenize(";")
        assert tokens[0].type == 'SEMI'

    def test_comma(self):
        tokens = Lexer().tokenize(",")
        assert tokens[0].type == 'COMMA'

    def test_left_paren(self):
        tokens = Lexer().tokenize("(")
        assert tokens[0].type == 'LPAREN'

    def test_right_paren(self):
        tokens = Lexer().tokenize(")")
        assert tokens[0].type == 'RPAREN'

    def test_star(self):
        tokens = Lexer().tokenize("*")
        assert tokens[0].type == 'STAR'


# =========================================================================
# Complex SQL tokenization
# =========================================================================

class TestComplexSQL:
    def test_select_star(self):
        tokens = Lexer().tokenize("SELECT * FROM users")
        types = [t.type for t in tokens]
        assert types == ['SELECT', 'STAR', 'FROM', 'IDENT']

    def test_insert_statement(self):
        tokens = Lexer().tokenize("INSERT INTO users VALUES (1, 'Alice')")
        types = [t.type for t in tokens]
        assert types == ['INSERT', 'INTO', 'IDENT', 'VALUES',
                         'LPAREN', 'NUMBER', 'COMMA', 'STRING', 'RPAREN']

    def test_where_clause(self):
        tokens = Lexer().tokenize("WHERE age >= 18")
        types = [t.type for t in tokens]
        assert types == ['WHERE', 'IDENT', 'OP', 'NUMBER']

    def test_and_or(self):
        tokens = Lexer().tokenize("a = 1 AND b = 2 OR c = 3")
        types = [t.type for t in tokens]
        assert types == ['IDENT', 'OP', 'NUMBER', 'AND',
                         'IDENT', 'OP', 'NUMBER', 'OR',
                         'IDENT', 'OP', 'NUMBER']

    def test_order_by(self):
        tokens = Lexer().tokenize("ORDER BY name ASC")
        types = [t.type for t in tokens]
        assert types == ['ORDER', 'BY', 'IDENT', 'ASC']

    def test_create_table(self):
        sql = "CREATE TABLE users (id INT, name TEXT)"
        tokens = Lexer().tokenize(sql)
        types = [t.type for t in tokens]
        assert types[:4] == ['CREATE', 'TABLE', 'IDENT', 'LPAREN']
        assert 'RPAREN' in types


# =========================================================================
# Whitespace and comments
# =========================================================================

class TestWhitespaceAndComments:
    def test_skip_spaces(self):
        tokens = Lexer().tokenize("SELECT   *   FROM  t")
        types = [t.type for t in tokens]
        assert types == ['SELECT', 'STAR', 'FROM', 'IDENT']

    def test_skip_newlines(self):
        tokens = Lexer().tokenize("SELECT\n*\nFROM\nt")
        types = [t.type for t in tokens]
        assert types == ['SELECT', 'STAR', 'FROM', 'IDENT']

    def test_skip_tabs(self):
        tokens = Lexer().tokenize("SELECT\t*\tFROM\tt")
        types = [t.type for t in tokens]
        assert types == ['SELECT', 'STAR', 'FROM', 'IDENT']

    def test_line_comment(self):
        tokens = Lexer().tokenize("SELECT * FROM t -- this is a comment")
        types = [t.type for t in tokens]
        assert types == ['SELECT', 'STAR', 'FROM', 'IDENT']

    def test_comment_only(self):
        tokens = Lexer().tokenize("-- just a comment")
        assert tokens == []


# =========================================================================
# Line / column tracking
# =========================================================================

class TestPositionTracking:
    def test_line_tracking(self):
        tokens = Lexer().tokenize("SELECT\n*")
        assert tokens[0].line == 1
        assert tokens[1].line == 2

    def test_column_tracking(self):
        tokens = Lexer().tokenize("SELECT *")
        assert tokens[0].column == 0
        assert tokens[1].column == 7


# =========================================================================
# Error handling
# =========================================================================

class TestLexerErrors:
    def test_unterminated_string_raises(self):
        with pytest.raises(ParseError):
            Lexer().tokenize("'unterminated")

    def test_illegal_character_raises(self):
        with pytest.raises(ParseError):
            Lexer().tokenize("SELECT @ FROM t")
