"""Nested-loop join executor for tinydb.

Supports INNER JOIN, LEFT JOIN, and CROSS JOIN by materializing the right
table and iterating over it for each left row.
"""

from tinydb.ast_nodes import BinaryExpr, ColumnRef, Literal
from tinydb.executor.filter import _CMP_OPS


class NestedLoopJoin:
    """Nested-loop join operator.

    Materializes the right table, then for each left row scans the right
    rows and yields merged rows according to the join type.
    """

    def __init__(self, left_source, right_table, join_type, on_condition,
                 catalog, buffer_pool, left_alias=None, right_alias=None):
        """
        Parameters
        ----------
        left_source : iterable of dict
            Upstream row source (left side of the join).
        right_table : str
            Name of the right table.
        join_type : str
            'INNER', 'LEFT', or 'CROSS'.
        on_condition : Expr or None
            The ON condition AST node. None for CROSS JOIN.
        catalog : Catalog
            To look up the right table's Table object.
        buffer_pool : BufferPool
            Unused (table owns its own reference).
        left_alias : str or None
            Alias for the left table (used in output column naming).
        right_alias : str or None
            Alias for the right table (used in output column naming).
        """
        self.left_source = left_source
        self.right_table = right_table
        self.join_type = join_type
        self.on_condition = on_condition
        self.catalog = catalog
        self.buffer_pool = buffer_pool
        self.left_alias = left_alias
        self.right_alias = right_alias

        # Resolve right table object.
        info = catalog.get_table(right_table)
        if info is None:
            from tinydb.types import JoinError
            raise JoinError(f"table {right_table!r} not found")
        self._right_table_obj = catalog.get_table_object(right_table)
        if self._right_table_obj is None:
            from tinydb.storage.table import Table as _Table
            self._right_table_obj = _Table(
                table_id=info.table_id,
                name=info.name,
                columns=info.columns,
                buffer_pool=buffer_pool,
            )
            self._right_table_obj.root_page_id = info.root_page_id
            self._right_table_obj._page_ids = list(info.page_ids) if info.page_ids else []

    def _prefix(self, table_name, alias):
        """Return the prefix for column names: alias or table name."""
        return alias or table_name

    def _right_scan(self):
        """Materialize all right table rows as dicts with prefixed keys."""
        prefix = self._prefix(self.right_table, self.right_alias)
        rows = []
        for row in self._right_table_obj.scan():
            d = {}
            for col, val in zip(row.columns, row.values):
                d[f"{prefix}.{col.name}"] = val
            rows.append(d)
        return rows

    def _ensure_prefixed(self, row, table_name, alias):
        """Ensure row keys are prefixed with table.column format.

        If keys are already prefixed (from a previous join), return as-is.
        Otherwise, prefix with the given table name/alias.
        """
        prefix = self._prefix(table_name, alias)
        # Check if already prefixed (any key contains a dot)
        sample_key = next(iter(row), None)
        if sample_key and '.' in sample_key:
            return row
        return {f"{prefix}.{k}": v for k, v in row.items()}

    def _merge_rows(self, left_row, right_row):
        """Merge left and right row dicts into one."""
        merged = dict(left_row)
        merged.update(right_row)
        return merged

    def _null_right_row(self, right_rows_sample):
        """Create a right row with all NULL values."""
        if not right_rows_sample:
            return {}
        # Use the keys from the first right row as template
        return {k: None for k in right_rows_sample[0].keys()}

    def _eval_on(self, left_row, right_row):
        """Evaluate the ON condition against merged rows."""
        if self.on_condition is None:
            return True
        merged = self._merge_rows(left_row, right_row)
        return self._eval_expr(merged, self.on_condition)

    def _eval_expr(self, row, expr):
        """Recursively evaluate an expression against a row."""
        if isinstance(expr, BinaryExpr):
            if expr.op == 'AND':
                return self._eval_expr(row, expr.left) and self._eval_expr(row, expr.right)
            if expr.op == 'OR':
                return self._eval_expr(row, expr.left) or self._eval_expr(row, expr.right)

            left = self._eval_expr(row, expr.left)
            right = self._eval_expr(row, expr.right)
            if left is None or right is None:
                return False
            op_fn = _CMP_OPS.get(expr.op)
            if op_fn is None:
                raise ValueError(f"unsupported operator {expr.op!r}")
            return op_fn(left, right)

        if isinstance(expr, ColumnRef):
            # Resolve column reference with optional table qualifier
            if expr.table:
                key = f"{expr.table}.{expr.name}"
                return row.get(key)
            # Try unqualified match
            val = row.get(expr.name)
            if val is not None:
                return val
            # Try finding with any prefix
            for k, v in row.items():
                if k.endswith(f".{expr.name}"):
                    return v
            return None

        if isinstance(expr, Literal):
            return expr.value

        raise TypeError(f"unexpected expression node: {type(expr).__name__}")

    def __iter__(self):
        """Yield merged rows according to the join type."""
        right_rows = self._right_scan()
        has_match = set()  # track left row indices that matched (for LEFT JOIN)

        for left_idx, left_row in enumerate(self.left_source):
            # Ensure left row keys are prefixed
            left_row = self._ensure_prefixed(left_row, self._prefix('', None) or
                                              self._left_table_name(left_row), self.left_alias)

            matched = False
            for right_row in right_rows:
                if self._eval_on(left_row, right_row):
                    yield self._merge_rows(left_row, right_row)
                    matched = True

            if matched:
                has_match.add(left_idx)
            elif self.join_type == 'LEFT':
                # No match: yield left row + NULL right columns
                null_right = self._null_right_row(right_rows)
                yield self._merge_rows(left_row, null_right)

        # CROSS JOIN with empty left: also yield if right has rows but left is empty
        # (handled naturally by the loop above)

    def _left_table_name(self, row):
        """Infer left table name from row keys."""
        for k in row:
            if '.' in k:
                return k.split('.', 1)[0]
        return 'unknown'
