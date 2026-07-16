"""AST node definitions for tinydb SQL parser.

All nodes are @dataclass for concise construction and readable repr().
Expression nodes (BinaryExpr, ColumnRef, Literal) form the WHERE tree.
Statement nodes are the top-level AST returned by the parser.
"""

from dataclasses import dataclass, field
from typing import Any, List, Optional, Tuple


# =========================================================================
# Expression nodes (used in WHERE, SET, etc.)
# =========================================================================

@dataclass
class BinaryExpr:
    """A binary expression: left op right (e.g. age > 25, AND/OR nesting)."""
    left: 'Expr'
    op: str
    right: 'Expr'


@dataclass
class ColumnRef:
    """Reference to a column by name."""
    name: str


@dataclass
class Literal:
    """A literal value: int, float, str, bool, or None (NULL)."""
    value: Any


# Type alias for any expression node.
Expr = Any  # BinaryExpr | ColumnRef | Literal


# =========================================================================
# DML statement nodes
# =========================================================================

@dataclass
class Select:
    """SELECT statement AST."""
    columns: List[str]                              # ['*'] or ['col1', 'col2']
    table: str
    where: Optional[Expr] = None
    order_by: Optional[Tuple[str, str]] = None      # (column, 'ASC'|'DESC')
    limit: Optional[int] = None
    offset: Optional[int] = None


@dataclass
class Insert:
    """INSERT statement AST."""
    table: str
    columns: Optional[List[str]] = None
    values: List[List[Any]] = field(default_factory=list)


@dataclass
class Update:
    """UPDATE statement AST."""
    table: str
    set_list: List[Tuple[str, Any]] = field(default_factory=list)
    where: Optional[Expr] = None


@dataclass
class Delete:
    """DELETE statement AST."""
    table: str
    where: Optional[Expr] = None


# =========================================================================
# DDL statement nodes
# =========================================================================

@dataclass
class ColumnDefAST:
    """Column definition inside CREATE TABLE."""
    name: str
    data_type: str          # 'INT', 'FLOAT', 'TEXT', 'BOOL'
    nullable: bool = True
    is_unique: bool = False
    is_pk: bool = False


@dataclass
class CreateTable:
    """CREATE TABLE statement AST."""
    table: str
    columns: List[ColumnDefAST] = field(default_factory=list)


@dataclass
class DropTable:
    """DROP TABLE statement AST."""
    table: str


@dataclass
class CreateIndex:
    """CREATE INDEX statement AST."""
    table: str
    column: str


# =========================================================================
# Transaction command nodes
# =========================================================================

@dataclass
class Begin:
    """BEGIN statement AST."""
    pass


@dataclass
class Commit:
    """COMMIT statement AST."""
    pass


@dataclass
class Rollback:
    """ROLLBACK statement AST."""
    pass
