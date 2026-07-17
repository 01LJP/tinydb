"""EXPLAIN execution plan formatter for tinydb.

Builds and formats execution plan trees for EXPLAIN queries.
"""

from tinydb.lexer import Lexer
from tinydb.parser import Parser
from tinydb.ast_nodes import Select, Explain


class ExplainPlan:
    """Build and format execution plans."""

    def __init__(self, db):
        self.db = db

    def explain(self, sql: str) -> str:
        """Parse SQL and return formatted execution plan."""
        # Handle EXPLAIN prefix
        if sql.strip().upper().startswith("EXPLAIN "):
            sql = sql.strip()[8:]

        tokens = Lexer().tokenize(sql)
        ast = Parser(tokens).parse()

        plan = self._build_plan(ast)
        return self._format_plan(plan)

    def _build_plan(self, ast) -> list:
        """Build plan node list from AST."""
        nodes = []

        if isinstance(ast, Select):
            if ast.joins:
                # First table scan
                alias = ast.tables[0].alias if ast.tables else None
                label = alias or ast.table
                nodes.append({"type": "SeqScan", "table": label})
                # Each join
                for join in ast.joins:
                    jalias = join.alias or join.table
                    nodes.append({
                        "type": "NestedLoopJoin",
                        "table": jalias,
                        "join_type": join.join_type,
                    })
            else:
                nodes.append({"type": "SeqScan", "table": ast.table})

            if ast.where is not None:
                nodes.append({"type": "Filter"})

            if ast.group_by:
                nodes.append({"type": "Aggregate", "group_by": ast.group_by})

            if ast.order_by:
                col, direction = ast.order_by
                nodes.append({"type": "Sort", "column": col, "order": direction})

            if ast.limit is not None:
                nodes.append({"type": "Limit", "limit": ast.limit})
        else:
            nodes.append({"type": type(ast).__name__})

        return nodes

    def _format_plan(self, nodes: list) -> str:
        """Format plan nodes as a readable tree."""
        lines = []
        for i, node in enumerate(nodes):
            prefix = "-> " if i > 0 else ""
            ntype = node["type"]
            extras = {k: v for k, v in node.items() if k != "type"}
            if extras:
                extra_str = ", ".join(f"{k}={v}" for k, v in extras.items())
                lines.append(f"{prefix}{ntype} ({extra_str})")
            else:
                lines.append(f"{prefix}{ntype}")
        return "\n".join(lines)
