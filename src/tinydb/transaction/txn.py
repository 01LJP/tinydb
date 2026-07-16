"""Transaction lifecycle manager for tinydb.

Coordinates the WAL and buffer pool to provide BEGIN / COMMIT / ROLLBACK
semantics and crash recovery.
"""

from typing import List

from tinydb.transaction.wal import WAL, WalOpType, LogRecord


class TransactionError(Exception):
    """Base class for transaction-related errors."""
    pass


class TransactionManager:
    """Transaction lifecycle manager.

    Holds the next transaction id counter and the set of currently active
    transactions.  All mutations flow through the WAL so that recovery can
    replay committed work after a crash.
    """

    def __init__(self, wal: WAL, buffer_pool, file_manager):
        self.wal = wal
        self.buffer_pool = buffer_pool
        self.file_manager = file_manager
        self.txn_counter = 0
        self.active_txns = set()
        # txn_id -> {page_id : bytes}  snapshot of clean page images at BEGIN.
        self._snapshots: dict = {}

    # ------------------------------------------------------------------
    # Lifecycle
    # ------------------------------------------------------------------

    def begin(self) -> int:
        """Start a transaction and return its id."""
        self.txn_counter += 1
        txn_id = self.txn_counter
        self.active_txns.add(txn_id)
        self.wal.log_begin(txn_id)
        return txn_id

    def commit(self, txn_id: int):
        """Commit a transaction: write COMMIT to WAL and flush."""
        self._check_active(txn_id)
        self.wal.log_commit(txn_id)
        self.wal.flush()
        self.active_txns.discard(txn_id)

    def abort(self, txn_id: int):
        """Abort a transaction without rolling back in-memory state.

        Writes an ABORT record; the caller should use ``rollback`` to undo
        any in-memory page changes.
        """
        self._check_active(txn_id)
        self.wal.log_abort(txn_id)
        self.wal.flush()
        self.active_txns.discard(txn_id)

    def snapshot_before(self, txn_id: int, buffer_pool):
        """Record a pre-transaction snapshot of every cached page image.

        On rollback these bytes are restored so the buffer pool reverts to
        its pre-transaction state.
        """
        snap = {}
        for page_id, page in buffer_pool._cache.items():
            snap[page_id] = bytes(page.buf)
        self._snapshots[txn_id] = snap

    def rollback(self, txn_id: int):
        """Rollback a transaction: undo writes in reverse order, then abort.

        Uses the WAL to find every page this transaction touched and
        restores the old_data on the buffer pool.  As a fallback the
        pre-transaction snapshot is restored for any page that was not
        explicitly logged.
        """
        self._check_active(txn_id)
        # Restore the pre-transaction snapshot for every cached page.
        snap = self._snapshots.pop(txn_id, {})
        for page_id, data in snap.items():
            self.buffer_pool.put(page_id, data)
        # Also apply WAL old_data in reverse for explicit log records.
        stack = self.get_txn_stack(txn_id)
        for rec in reversed(stack):
            if rec.old_data:
                self.buffer_pool.put(rec.page_id, rec.old_data)
        self.wal.log_abort(txn_id)
        self.wal.flush()
        self.active_txns.discard(txn_id)

    # ------------------------------------------------------------------
    # Write path
    # ------------------------------------------------------------------

    def log_write(self, txn_id: int, page_id: int, old_data: bytes, new_data: bytes):
        """Record a page mutation in the WAL."""
        self._check_active(txn_id)
        self.wal.log_write(txn_id, page_id, old_data, new_data)

    # ------------------------------------------------------------------
    # Queries
    # ------------------------------------------------------------------

    def get_txn_stack(self, txn_id: int) -> List[LogRecord]:
        """Return this transaction's write records in log order."""
        records = self.wal.parse_records()
        return [
            r for r in records
            if r.txn_id == txn_id
            and r.op_type in (WalOpType.INSERT, WalOpType.UPDATE, WalOpType.DELETE)
        ]

    def is_active(self, txn_id: int) -> bool:
        """Return True if the transaction is currently in-flight."""
        return txn_id in self.active_txns

    # ------------------------------------------------------------------
    # Crash recovery
    # ------------------------------------------------------------------

    def recover(self) -> bool:
        """Run WAL recovery against the buffer pool.

        Delegates to ``WAL.recover`` which redoes committed transactions
        and discards uncommitted ones.  Returns True if any work was
        replayed.
        """
        return self.wal.recover(self.buffer_pool)

    # ------------------------------------------------------------------
    # Internal
    # ------------------------------------------------------------------

    def _check_active(self, txn_id: int):
        """Raise if the given transaction is not currently active."""
        if not self.is_active(txn_id):
            raise TransactionError(
                f'transaction {txn_id} is not active'
            )
