"""SQL lexer (tokenizer) for tinydb.

Converts a raw SQL string into a list of Token objects.
Raises ParseError on illegal characters or unterminated strings.
"""

from typing import List

from tinydb.types import ParseError


class Token:
    """A single lexical token."""

    __slots__ = ('type', 'value', 'line', 'column')

    def __init__(self, type: str, value, line: int = 1, column: int = 0):
        self.type = type
        self.value = value
        self.line = line
        self.column = column

    def __repr__(self):
        return f"Token({self.type}, {self.value!r})"

    def __eq__(self, other):
        if isinstance(other, Token):
            return (self.type == other.type and self.value == other.value
                    and self.line == other.line and self.column == other.column)
        return NotImplemented


class Lexer:
    """Tokenizes a SQL string into a list of :class:`Token`."""

    KEYWORDS = {
        'SELECT', 'FROM', 'WHERE', 'INSERT', 'INTO', 'VALUES',
        'UPDATE', 'SET', 'DELETE', 'CREATE', 'TABLE', 'DROP',
        'ORDER', 'BY', 'LIMIT', 'OFFSET', 'AND', 'OR', 'NOT',
        'NULL', 'PRIMARY', 'KEY', 'UNIQUE', 'INDEX', 'ON',
        'ASC', 'DESC', 'BEGIN', 'COMMIT', 'ROLLBACK',
        'INT', 'FLOAT', 'TEXT', 'BOOL',
        'COUNT', 'SUM', 'AVG', 'GROUP',
    }

    # Single-character punctuation map.
    PUNCT = {
        ';': 'SEMI',
        ',': 'COMMA',
        '(': 'LPAREN',
        ')': 'RPAREN',
        '*': 'STAR',
    }

    def tokenize(self, sql: str) -> List[Token]:
        """Tokenize *sql* into a list of tokens."""
        tokens: List[Token] = []
        i = 0
        line = 1
        column = 0
        n = len(sql)

        while i < n:
            ch = sql[i]

            # --- whitespace ---
            if ch in ' \t\r':
                i += 1
                column += 1
                continue
            if ch == '\n':
                i += 1
                line += 1
                column = 0
                continue

            # --- line comment: -- ... ---
            if ch == '-' and i + 1 < n and sql[i + 1] == '-':
                # skip until end of line
                i += 2
                while i < n and sql[i] != '\n':
                    i += 1
                continue

            # --- string literal: '...' ---
            if ch == "'":
                start_line, start_col = line, column
                i += 1
                column += 1
                parts = []
                while i < n:
                    c = sql[i]
                    if c == "'":
                        # escaped quote '' -> '
                        if i + 1 < n and sql[i + 1] == "'":
                            parts.append("'")
                            i += 2
                            column += 2
                            continue
                        # end of string
                        i += 1
                        column += 1
                        break
                    if c == '\n':
                        parts.append(c)
                        i += 1
                        line += 1
                        column = 0
                        continue
                    parts.append(c)
                    i += 1
                    column += 1
                else:
                    raise ParseError(
                        "unterminated string literal",
                        context=f"line {start_line}, column {start_col}",
                    )
                tokens.append(Token('STRING', ''.join(parts), start_line, start_col))
                continue

            # --- number: int or float ---
            if ch.isdigit():
                start_col = column
                start = i
                while i < n and sql[i].isdigit():
                    i += 1
                    column += 1
                if i < n and sql[i] == '.':
                    i += 1
                    column += 1
                    while i < n and sql[i].isdigit():
                        i += 1
                        column += 1
                    value = float(sql[start:i])
                else:
                    value = int(sql[start:i])
                tokens.append(Token('NUMBER', value, line, start_col))
                continue

            # --- identifier or keyword ---
            if ch.isalpha() or ch == '_':
                start_col = column
                start = i
                while i < n and (sql[i].isalnum() or sql[i] == '_'):
                    i += 1
                    column += 1
                word = sql[start:i]
                upper = word.upper()
                if upper in self.KEYWORDS:
                    tokens.append(Token(upper, upper, line, start_col))
                else:
                    tokens.append(Token('IDENT', word, line, start_col))
                continue

            # --- operators ---
            if ch == '=':
                tokens.append(Token('OP', '=', line, column))
                i += 1
                column += 1
                continue
            if ch == '!' and i + 1 < n and sql[i + 1] == '=':
                tokens.append(Token('OP', '!=', line, column))
                i += 2
                column += 2
                continue
            if ch == '<':
                if i + 1 < n and sql[i + 1] == '=':
                    tokens.append(Token('OP', '<=', line, column))
                    i += 2
                    column += 2
                elif i + 1 < n and sql[i + 1] == '>':
                    tokens.append(Token('OP', '<>', line, column))
                    i += 2
                    column += 2
                else:
                    tokens.append(Token('OP', '<', line, column))
                    i += 1
                    column += 1
                continue
            if ch == '>':
                if i + 1 < n and sql[i + 1] == '=':
                    tokens.append(Token('OP', '>=', line, column))
                    i += 2
                    column += 2
                else:
                    tokens.append(Token('OP', '>', line, column))
                    i += 1
                    column += 1
                continue

            # --- punctuation ---
            if ch in self.PUNCT:
                tokens.append(Token(self.PUNCT[ch], ch, line, column))
                i += 1
                column += 1
                continue

            # --- illegal character ---
            raise ParseError(
                f"illegal character {ch!r}",
                context=f"line {line}, column {column}",
            )

        return tokens
