"""WHERE-clause filter for tinydb.

Iterates a source operator and yields only rows for which the given
AST expression evaluates to True.
"""

from tinydb.ast_nodes import BinaryExpr, ColumnRef, Literal


# Comparison operators supported by the filter.
_CMP_OPS = {
    '=': lambda a, b: a == b,
    '!=': lambda a, b: a != b,
    '<>': lambda a, b: a != b,
    '<': lambda a, b: a < b,
    '>': lambda a, b: a > b,
    '<=': lambda a, b: a <= b,
    '>=': lambda a, b: a >= b,
}


class Filter:
    """Apply a WHERE condition to every row from *source*."""

    def __init__(self, source, condition):
        """
        Parameters
        ----------
        source : iterable of dict
            Upstream row source (e.g. SeqScan, another Filter, …).
        condition : tinydb.ast_nodes.Expr
            Root of the AST expression tree (BinaryExpr / ColumnRef / Literal).
        """
        self.source = source
        self.condition = condition

    def __iter__(self):
        """Yield rows that satisfy the WHERE condition."""
        for row in self.source:
            if self._eval(row, self.condition):
                yield row

    def _eval(self, row, expr):
        """Recursively evaluate *expr* against *row*.

        Any comparison that touches a NULL value yields False (SQL
        three-valued logic simplified to "NULL is never true").
        """
        if isinstance(expr, BinaryExpr):
            if expr.op == 'AND':
                return self._eval(row, expr.left) and self._eval(row, expr.right)
            if expr.op == 'OR':
                return self._eval(row, expr.left) or self._eval(row, expr.right)

            # Comparison such as age > 25
            left = self._eval(row, expr.left)
            right = self._eval(row, expr.right)
            if left is None or right is None:
                return False
            op_fn = _CMP_OPS.get(expr.op)
            if op_fn is None:
                raise ValueError(f"unsupported operator {expr.op!r}")
            return op_fn(left, right)

        if isinstance(expr, ColumnRef):
            # Support qualified column references (table.column)
            if expr.table:
                return row.get(f"{expr.table}.{expr.name}")
            # Try unqualified match first
            val = row.get(expr.name)
            if val is not None:
                return val
            # Try matching with any table prefix (for JOIN results)
            for k, v in row.items():
                if k.endswith(f".{expr.name}"):
                    return v
            return None

        if isinstance(expr, Literal):
            return expr.value

        raise TypeError(f"unexpected expression node: {type(expr).__name__}")
