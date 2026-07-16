"""Aggregate operator for tinydb.

Materialises the upstream input, partitions it by the optional GROUP BY
column, then applies aggregate functions (COUNT, SUM, AVG) to each group.
"""

from tinydb.ast_nodes import AggregateExpr


def _apply_agg(func, column, rows):
    """Run one aggregate over *rows*.

    Parameters
    ----------
    func : str
        'COUNT' | 'SUM' | 'AVG'.
    column : str
        Column name, or '*' for COUNT(*).
    rows : list of dict
        The input rows (all rows if there is no GROUP BY, otherwise one
        group).

    Returns
    -------
    int | float
        The aggregated value.  Returns 0 for COUNT on an empty input;
        returns 0 for SUM/AVG on an empty input (the operator is never
        called that way because at least one row always exists, but we
        defensive-code it anyway).
    """
    if func == 'COUNT':
        if column == '*':
            return len(rows)
        return sum(1 for r in rows if r.get(column) is not None)

    if func == 'SUM':
        vals = [r[column] for r in rows if r.get(column) is not None]
        return sum(vals) if vals else 0

    if func == 'AVG':
        vals = [r[column] for r in rows if r.get(column) is not None]
        if not vals:
            return 0
        return sum(vals) / len(vals)

    raise ValueError(f"unsupported aggregate function {func!r}")


class Aggregate:
    """Compute aggregates, optionally grouped by a column.

    The output column for an aggregate is named after the function in
    lower case, e.g. ``COUNT(*)`` → ``{"count": ...}``.
    """

    def __init__(self, source, select_columns, group_by=None):
        """
        Parameters
        ----------
        source : iterable of dict
            Upstream row source.
        select_columns : list
            Either plain column names (str) or :class:`AggregateExpr` nodes.
        group_by : str or None
            Column name to group by, or None for a single global group.
        """
        self.source = source
        self.select_columns = select_columns
        self.group_by = group_by

    def execute(self):
        """Materialise, group, aggregate, and return ``list[dict]``."""
        all_rows = list(self.source)
        agg_columns = [c for c in self.select_columns if isinstance(c, AggregateExpr)]
        plain_columns = [c for c in self.select_columns if not isinstance(c, AggregateExpr)]

        def _build_group_row(rows):
            """Build the output dict for a single group of rows."""
            out = {}
            for col in plain_columns:
                # Non-aggregate column in a GROUP BY query: take the first row's value.
                out[col] = rows[0].get(col) if rows else None
            for agg in agg_columns:
                out[agg.func.lower()] = _apply_agg(agg.func, agg.column, rows)
            return out

        if self.group_by is None:
            # One global group.
            return [_build_group_row(all_rows)]

        # Partition by group_by column, preserving first-seen order.
        groups = []
        group_index = {}
        for row in all_rows:
            key = row.get(self.group_by)
            if key not in group_index:
                group_index[key] = len(groups)
                groups.append([])
            groups[group_index[key]].append(row)

        return [_build_group_row(g) for g in groups]
