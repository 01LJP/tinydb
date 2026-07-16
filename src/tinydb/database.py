"""Database core for tinydb.

Glues together the storage, catalog, executor, index, and transaction
subsystems behind a single :meth:`Database.execute` entry point that
accepts raw SQL strings.
"""

import copy
from contextlib import contextmanager
from typing import Any, Dict, List, Optional

from tinydb.lexer import Lexer
from tinydb.parser import Parser
from tinydb.ast_nodes import (
    Select, Insert, Update, Delete,
    CreateTable, DropTable, CreateIndex,
    Begin, Commit, Rollback,
    ColumnDefAST, AggregateExpr,
)
from tinydb.types import (
    DataType, ColumnDef,
    ConstraintError, TableNotFoundError, ColumnNotFoundError,
)
from tinydb.storage.file_manager import FileManager
from tinydb.storage.buffer_pool import BufferPool
from tinydb.storage.table import Table
from tinydb.catalog import Catalog
from tinydb.index.btree import IndexManager
from tinydb.transaction.wal import WAL
from tinydb.transaction.txn import TransactionManager
from tinydb.executor.plan import PlanSelector
from tinydb.executor.filter import Filter
from tinydb.executor.sort import Sort
from tinydb.executor.limit import Limit
from tinydb.executor.aggregate import Aggregate


# =========================================================================
# Helpers
# =========================================================================

_DATA_TYPE_MAP = {
    "INT": DataType.INT,
    "FLOAT": DataType.FLOAT,
    "TEXT": DataType.TEXT,
    "BOOL": DataType.BOOL,
}


def _ast_to_columns(columns: List[ColumnDefAST]) -> List[ColumnDef]:
    """Convert a list of ColumnDefAST to runtime ColumnDef objects."""
    return [
        ColumnDef(
            name=c.name,
            data_type=_DATA_TYPE_MAP[c.data_type],
            nullable=c.nullable,
            is_unique=c.is_unique,
            is_pk=c.is_pk,
        )
        for c in columns
    ]


# =========================================================================
# Database
# =========================================================================

class Database:
    """The tinydb database.

    Owns every subsystem and exposes a single SQL-execution entry point.
    """

    def __init__(self, path: str):
        self.path = path
        self.file_manager = FileManager(path)
        self.buffer_pool = BufferPool(self.file_manager, capacity=100)
        self.catalog = Catalog(self.buffer_pool)
        self.wal = WAL(path + ".wal")
        self.wal.open()
        self.txn_manager = TransactionManager(
            self.wal, self.buffer_pool, self.file_manager
        )
        self.index_manager = IndexManager(self.buffer_pool, self.catalog)

        # Currently-active transaction id (None if auto-commit mode).
        self._current_txn_id: Optional[int] = None

        # Crash recovery on startup.
        self._recover()

        # Rebuild live Table objects from catalog metadata so scans work.
        self._rebuild_table_objects()

    # ------------------------------------------------------------------
    # Lifecycle
    # ------------------------------------------------------------------

    def _recover(self):
        """Run WAL recovery on startup."""
        self.txn_manager.recover()

    def _rebuild_table_objects(self):
        """Reconstruct live Table objects from persisted catalog metadata."""
        for name, info in self.catalog.tables.items():
            columns = self.catalog.columns.get(info.table_id, [])
            table = Table(
                table_id=info.table_id,
                name=info.name,
                columns=columns,
                buffer_pool=self.buffer_pool,
            )
            table.root_page_id = info.root_page_id
            table._page_ids = list(info.page_ids) if info.page_ids else []
            self.catalog.register_table_object(name, table)

    def close(self):
        """Flush everything and close the database."""
        self.buffer_pool.flush_all()
        self.wal.close()
        self.file_manager.close()

    def __enter__(self):
        return self

    def __exit__(self, *args):
        self.close()

    # ------------------------------------------------------------------
    # Main entry point
    # ------------------------------------------------------------------

    def execute(self, sql: str):
        """Parse and execute a SQL statement, returning the result.

        Return types:
            - SELECT      -> List[Dict[str, Any]]
            - INSERT/UPDATE/DELETE -> {"affected_rows": int}
            - DDL / txn   -> {"status": "ok"}
        """
        tokens = Lexer().tokenize(sql)
        ast = Parser(tokens).parse()

        # --- DDL ---
        if isinstance(ast, CreateTable):
            return self._exec_create_table(ast)
        if isinstance(ast, DropTable):
            return self._exec_drop_table(ast)
        if isinstance(ast, CreateIndex):
            return self._exec_create_index(ast)

        # --- Transaction control ---
        if isinstance(ast, Begin):
            return self._exec_begin()
        if isinstance(ast, Commit):
            return self._exec_commit()
        if isinstance(ast, Rollback):
            return self._exec_rollback()

        # --- DML ---
        if isinstance(ast, Insert):
            return self._exec_insert(ast)
        if isinstance(ast, Select):
            return self._exec_select(ast)
        if isinstance(ast, Update):
            return self._exec_update(ast)
        if isinstance(ast, Delete):
            return self._exec_delete(ast)

        raise ValueError(f"unknown statement type: {type(ast).__name__}")

    # ------------------------------------------------------------------
    # DDL
    # ------------------------------------------------------------------

    def _exec_create_table(self, ast: CreateTable) -> dict:
        columns = _ast_to_columns(ast.columns)
        table_id = self.catalog.create_table(ast.table, columns)
        # Allocate a root data page and register the live Table object.
        table = Table(
            table_id=table_id,
            name=ast.table,
            columns=columns,
            buffer_pool=self.buffer_pool,
        )
        table._allocate_page()
        self.catalog.register_table_object(ast.table, table)
        # Persist the allocated page ids so the table can be rebuilt on restart.
        info = self.catalog.get_table(ast.table)
        info.root_page_id = table.root_page_id
        info.page_ids = list(table._page_ids)
        self.catalog.update_table_info(ast.table, info)
        return {"status": "ok"}

    def _exec_drop_table(self, ast: DropTable) -> dict:
        self.catalog.drop_table(ast.table)
        return {"status": "ok"}

    def _exec_create_index(self, ast: CreateIndex) -> dict:
        self.index_manager.create_index(ast.table, ast.column)
        return {"status": "ok"}

    # ------------------------------------------------------------------
    # Transaction control
    # ------------------------------------------------------------------

    def _exec_begin(self) -> dict:
        if self._current_txn_id is not None:
            raise ConstraintError("a transaction is already active")
        self._current_txn_id = self.txn_manager.begin()
        # Snapshot every dirty page's current image for potential rollback.
        self.txn_manager.snapshot_before(self._current_txn_id, self.buffer_pool)
        return {"status": "ok"}

    def _exec_commit(self) -> dict:
        if self._current_txn_id is None:
            raise ConstraintError("no active transaction to commit")
        self.txn_manager.commit(self._current_txn_id)
        self._current_txn_id = None
        return {"status": "ok"}

    def _exec_rollback(self) -> dict:
        if self._current_txn_id is None:
            raise ConstraintError("no active transaction to rollback")
        self.txn_manager.rollback(self._current_txn_id)
        self._current_txn_id = None
        return {"status": "ok"}

    # ------------------------------------------------------------------
    # DML: INSERT
    # ------------------------------------------------------------------

    def _exec_insert(self, ast: Insert) -> dict:
        table = self._require_table(ast.table)
        columns = table.columns

        # Resolve the target column order.
        if ast.columns is not None:
            col_names = ast.columns
            col_indices = []
            for name in col_names:
                for i, c in enumerate(columns):
                    if c.name == name:
                        col_indices.append(i)
                        break
                else:
                    raise ColumnNotFoundError(
                        f"column {name!r} not found in table {ast.table!r}"
                    )
        else:
            col_indices = list(range(len(columns)))

        affected = 0
        for value_list in ast.values:
            # Build a full-length values row (None for unspecified columns).
            row_values: list = [None] * len(columns)
            for idx, val in zip(col_indices, value_list):
                row_values[idx] = val

            self._check_constraints(table, row_values)
            before_pages = set(table._page_ids)
            record_id = table.insert(row_values)
            # If a new page was allocated, persist the page list.
            if set(table._page_ids) != before_pages:
                info = self.catalog.get_table(ast.table)
                info.page_ids = list(table._page_ids)
                info.root_page_id = table.root_page_id
                self.catalog.update_table_info(ast.table, info)
            # Maintain indexes.
            row_dict = {
                col.name: val for col, val in zip(columns, row_values)
            }
            self.index_manager.insert_indexes(ast.table, row_dict, record_id)
            affected += 1

        return {"affected_rows": affected}

    # ------------------------------------------------------------------
    # DML: SELECT
    # ------------------------------------------------------------------

    def _exec_select(self, ast: Select) -> List[Dict[str, Any]]:
        # Pick a physical scan operator.
        plan = PlanSelector(self.catalog, self.index_manager)
        scan = plan.select_scan(ast.table, ast.where)

        pipeline: Any = scan

        # WHERE
        if ast.where is not None:
            pipeline = Filter(pipeline, ast.where)

        # Detect aggregate vs plain query.
        has_aggregate = ast.columns != ["*"] and any(
            isinstance(c, AggregateExpr) for c in ast.columns
        )

        if has_aggregate:
            # Aggregate handles its own grouping; ORDER BY / LIMIT apply
            # to the aggregated output.
            pipeline = Sort(pipeline, ast.group_by or "", "ASC") if ast.group_by else pipeline
            result = Aggregate(pipeline, ast.columns, group_by=ast.group_by).execute()
            # ORDER BY on aggregate output.
            if ast.order_by is not None:
                col, direction = ast.order_by
                result = sorted(
                    result,
                    key=lambda r: r.get(col),
                    reverse=(direction == "DESC"),
                )
            if ast.limit is not None or ast.offset is not None:
                offset = ast.offset or 0
                if ast.limit is None:
                    result = result[offset:]
                else:
                    result = result[offset:offset + ast.limit]
            return result

        # Plain query: ORDER BY → LIMIT.
        if ast.order_by is not None:
            col, direction = ast.order_by
            pipeline = Sort(pipeline, col, direction)

        if ast.limit is not None or ast.offset is not None:
            pipeline = Limit(pipeline, ast.limit, ast.offset)

        return list(pipeline)

    # ------------------------------------------------------------------
    # DML: UPDATE
    # ------------------------------------------------------------------

    def _exec_update(self, ast: Update) -> dict:
        table = self._require_table(ast.table)
        columns = table.columns

        # Build a column-name → index map.
        col_index = {c.name: i for i, c in enumerate(columns)}

        affected = 0
        for row in table.scan():
            row_dict = row.to_dict()
            if ast.where is not None:
                # Evaluate the WHERE condition inline.
                src = Filter(iter([row_dict]), ast.where)
                if not list(src):
                    continue

            # Deep copy the original row BEFORE mutation.  The index manager
            # needs to see the original (old) values so it can delete the
            # stale index keys.
            old_row = copy.deepcopy(row_dict)

            # Build the new values list.
            new_values = list(row.values)
            for col_name, val in ast.set_list:
                if col_name not in col_index:
                    raise ColumnNotFoundError(
                        f"column {col_name!r} not found in table {ast.table!r}"
                    )
                new_values[col_index[col_name]] = val

            self._check_constraints(table, new_values, exclude_record_id=row.record_id)
            # ``_write_record_at`` tombstones the old record and appends a new
            # one, so record_id may change.  The new id is needed for the
            # index update below.
            new_record_id = self._write_record_at(table, row.record_id, new_values)
            new_row = dict(zip([c.name for c in columns], new_values))
            self.index_manager.update_indexes(
                ast.table, old_row, new_row, new_record_id
            )
            affected += 1

        return {"affected_rows": affected}

    # ------------------------------------------------------------------
    # DML: DELETE
    # ------------------------------------------------------------------

    def _exec_delete(self, ast: Delete) -> dict:
        table = self._require_table(ast.table)

        affected = 0
        for row in table.scan():
            row_dict = row.to_dict()
            if ast.where is not None:
                src = Filter(iter([row_dict]), ast.where)
                if not list(src):
                    continue
            # Tombstone the record.
            page_id = row.record_id >> 16
            slot_id = row.record_id & 0xFFFF
            page = self.buffer_pool.get_page(page_id)
            page.delete_record(slot_id)
            self.buffer_pool.mark_dirty(page_id)
            self.index_manager.delete_indexes(ast.table, row_dict, row.record_id)
            affected += 1

        return {"affected_rows": affected}

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _require_table(self, name: str) -> Table:
        """Return the live Table object for *name* or raise."""
        table = self.catalog.get_table_object(name)
        if table is None:
            raise TableNotFoundError(f"table {name!r} does not exist")
        return table

    def _check_constraints(
        self,
        table: Table,
        values: list,
        exclude_record_id: Optional[int] = None,
    ):
        """Validate NOT NULL, PRIMARY KEY, and UNIQUE constraints.

        Scans the table to detect duplicate PK / unique values.  The row
        at *exclude_record_id* is ignored so UPDATE can re-validate against
        other rows.
        """
        pk_columns = [c for c in table.columns if c.is_pk]
        unique_columns = [c for c in table.columns if c.is_unique and not c.is_pk]

        for i, col in enumerate(table.columns):
            val = values[i]
            # NOT NULL check.
            if not col.nullable and val is None:
                raise ConstraintError(
                    f"NOT NULL constraint violated on column {col.name!r}"
                )

        # PK / UNIQUE checks require a scan.
        if pk_columns or unique_columns:
            for row in table.scan():
                if row.record_id == exclude_record_id:
                    continue
                for col in pk_columns:
                    ci = table.columns.index(col)
                    if row.values[ci] == values[ci]:
                        raise ConstraintError(
                            f"PRIMARY KEY constraint violated: "
                            f"value {values[ci]!r} already exists in table {table.name!r}"
                        )
                for col in unique_columns:
                    ci = table.columns.index(col)
                    if values[ci] is not None and row.values[ci] == values[ci]:
                        raise ConstraintError(
                            f"UNIQUE constraint violated: "
                            f"value {values[ci]!r} already exists in column {col.name!r}"
                        )

    def _write_record_at(self, table: Table, record_id: int, values: list) -> int:
        """Replace the record at *record_id* with *values*.

        The slotted-page layout cannot grow a record in place: a longer
        value would overflow into the next slot.  To stay symmetric with
        ``insert`` / ``delete`` we tombstone the old record and append a
        fresh one (which may land on any page with enough free space).
        Returns the new record_id.
        """
        page_id = record_id >> 16
        slot_id = record_id & 0xFFFF
        page = self.buffer_pool.get_page(page_id)
        page.delete_record(slot_id)
        self.buffer_pool.mark_dirty(page_id)

        before_pages = set(table._page_ids)
        new_record_id = table.insert(values)
        # If a new page was allocated, persist the page list so the table
        # can be rebuilt on restart.
        if set(table._page_ids) != before_pages:
            info = self.catalog.get_table(table.name)
            info.page_ids = list(table._page_ids)
            info.root_page_id = table.root_page_id
            self.catalog.update_table_info(table.name, info)
        return new_record_id


# =========================================================================
# Public context manager
# =========================================================================

@contextmanager
def open(path: str):
    """Open a tinydb database at *path* and close it on exit."""
    db = Database(path)
    try:
        yield db
    finally:
        db.close()
