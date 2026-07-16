"""Tests for tinydb transaction manager.

Covers: BEGIN / COMMIT / ROLLBACK lifecycle, rollback correctness,
active txn tracking, txn stack retrieval, and simulated crash recovery.
"""

import os
import tempfile
import pytest

from tinydb.transaction.wal import WAL, WalOpType
from tinydb.transaction.txn import TransactionManager


# =========================================================================
# Helpers
# =========================================================================

class MockBufferPool:
    """Minimal buffer pool stand-in for TransactionManager tests."""

    def __init__(self):
        self.pages = {}      # page_id -> bytes
        self.flushed = 0

    def put(self, page_id, data):
        self.pages[page_id] = data

    def get(self, page_id, default=b''):
        return self.pages.get(page_id, default)

    def flush_all(self):
        self.flushed += 1


class MockFileManager:
    """Minimal file manager stand-in (not used heavily in these tests)."""

    def __init__(self, path=None):
        self.path = path or ''


# =========================================================================
# Lifecycle tests
# =========================================================================

class TestTransactionLifecycle:
    """Verify begin / commit / rollback behavior."""

    def setup_method(self):
        self.tmp = tempfile.NamedTemporaryFile(delete=False, suffix='.wal')
        self.tmp.close()
        self.wal = WAL(self.tmp.name)
        self.wal.open()
        self.bp = MockBufferPool()
        self.fm = MockFileManager()
        self.tm = TransactionManager(self.wal, self.bp, self.fm)

    def teardown_method(self):
        if self.wal.file and not self.wal.file.closed:
            self.wal.close()
        if os.path.exists(self.tmp.name):
            os.unlink(self.tmp.name)

    def test_begin_returns_positive_txn_id(self):
        txn_id = self.tm.begin()
        assert txn_id > 0

    def test_begin_increments_ids(self):
        id1 = self.tm.begin()
        id2 = self.tm.begin()
        assert id1 != id2
        assert id2 > id1

    def test_begin_marks_active(self):
        txn_id = self.tm.begin()
        assert self.tm.is_active(txn_id) is True

    def test_commit_writes_to_wal(self):
        txn_id = self.tm.begin()
        self.tm.commit(txn_id)
        records = self.wal.parse_records()
        op_types = [r.op_type for r in records]
        assert WalOpType.BEGIN in op_types
        assert WalOpType.COMMIT in op_types

    def test_commit_removes_from_active(self):
        txn_id = self.tm.begin()
        self.tm.commit(txn_id)
        assert self.tm.is_active(txn_id) is False

    def test_abort_writes_to_wal(self):
        txn_id = self.tm.begin()
        self.tm.abort(txn_id)
        records = self.wal.parse_records()
        op_types = [r.op_type for r in records]
        assert WalOpType.ABORT in op_types

    def test_abort_removes_from_active(self):
        txn_id = self.tm.begin()
        self.tm.abort(txn_id)
        assert self.tm.is_active(txn_id) is False

    def test_unknown_txn_is_not_active(self):
        assert self.tm.is_active(999) is False


# =========================================================================
# Write + txn stack tests
# =========================================================================

class TestTransactionWrites:
    """Verify log_write and get_txn_stack."""

    def setup_method(self):
        self.tmp = tempfile.NamedTemporaryFile(delete=False, suffix='.wal')
        self.tmp.close()
        self.wal = WAL(self.tmp.name)
        self.wal.open()
        self.bp = MockBufferPool()
        self.fm = MockFileManager()
        self.tm = TransactionManager(self.wal, self.bp, self.fm)

    def teardown_method(self):
        if self.wal.file and not self.wal.file.closed:
            self.wal.close()
        if os.path.exists(self.tmp.name):
            os.unlink(self.tmp.name)

    def test_log_write_appends_record(self):
        txn_id = self.tm.begin()
        self.tm.log_write(txn_id, 1, b'old', b'new')
        stack = self.tm.get_txn_stack(txn_id)
        assert len(stack) == 1
        assert stack[0].page_id == 1
        assert stack[0].old_data == b'old'
        assert stack[0].new_data == b'new'

    def test_log_write_multiple_pages(self):
        txn_id = self.tm.begin()
        self.tm.log_write(txn_id, 1, b'a', b'b')
        self.tm.log_write(txn_id, 2, b'c', b'd')
        stack = self.tm.get_txn_stack(txn_id)
        assert len(stack) == 2
        assert stack[0].page_id == 1
        assert stack[1].page_id == 2

    def test_get_txn_stack_isolation(self):
        """Each txn only sees its own writes."""
        t1 = self.tm.begin()
        self.tm.log_write(t1, 1, b'a', b'b')
        t2 = self.tm.begin()
        self.tm.log_write(t2, 2, b'c', b'd')
        s1 = self.tm.get_txn_stack(t1)
        s2 = self.tm.get_txn_stack(t2)
        assert len(s1) == 1
        assert len(s2) == 1
        assert s1[0].page_id == 1
        assert s2[0].page_id == 2

    def test_log_write_unknown_txn_raises(self):
        with pytest.raises(Exception):
            self.tm.log_write(999, 0, b'a', b'b')


# =========================================================================
# Rollback tests
# =========================================================================

class TestRollback:
    """Verify rollback correctly restores old_data."""

    def setup_method(self):
        self.tmp = tempfile.NamedTemporaryFile(delete=False, suffix='.wal')
        self.tmp.close()
        self.wal = WAL(self.tmp.name)
        self.wal.open()
        self.bp = MockBufferPool()
        self.fm = MockFileManager()
        self.tm = TransactionManager(self.wal, self.bp, self.fm)

    def teardown_method(self):
        if self.wal.file and not self.wal.file.closed:
            self.wal.close()
        if os.path.exists(self.tmp.name):
            os.unlink(self.tmp.name)

    def test_rollback_restores_old_data(self):
        txn_id = self.tm.begin()
        # Simulate buffer pool already having the "before" state.
        self.bp.pages[1] = b'old_value'
        self.tm.log_write(txn_id, 1, b'old_value', b'new_value')
        # Simulate that the page was updated in memory.
        self.bp.pages[1] = b'new_value'
        # Roll it back.
        self.tm.rollback(txn_id)
        assert self.bp.pages[1] == b'old_value'

    def test_rollback_writes_abort_record(self):
        txn_id = self.tm.begin()
        self.tm.log_write(txn_id, 1, b'a', b'b')
        self.tm.rollback(txn_id)
        records = self.wal.parse_records()
        op_types = [r.op_type for r in records]
        assert WalOpType.ABORT in op_types

    def test_rollback_removes_from_active(self):
        txn_id = self.tm.begin()
        self.tm.log_write(txn_id, 1, b'a', b'b')
        self.tm.rollback(txn_id)
        assert self.tm.is_active(txn_id) is False

    def test_rollback_reverses_order(self):
        """Rollback must apply old_data in reverse write order."""
        txn_id = self.tm.begin()
        self.bp.pages[1] = b'orig_1'
        self.bp.pages[2] = b'orig_2'
        self.tm.log_write(txn_id, 1, b'orig_1', b'mid_1')
        self.bp.pages[1] = b'mid_1'
        self.tm.log_write(txn_id, 1, b'mid_1', b'final_1')
        self.bp.pages[1] = b'final_1'
        self.tm.log_write(txn_id, 2, b'orig_2', b'new_2')
        self.bp.pages[2] = b'new_2'
        self.tm.rollback(txn_id)
        assert self.bp.pages[1] == b'orig_1'
        assert self.bp.pages[2] == b'orig_2'

    def test_rollback_unknown_txn_raises(self):
        with pytest.raises(Exception):
            self.tm.rollback(999)


# =========================================================================
# Crash-recovery simulation
# =========================================================================

class TestCrashRecovery:
    """Verify TransactionManager.recover replays committed transactions."""

    def setup_method(self):
        self.tmp = tempfile.NamedTemporaryFile(delete=False, suffix='.wal')
        self.tmp.close()
        self.wal_path = self.tmp.name

    def teardown_method(self):
        if os.path.exists(self.wal_path):
            os.unlink(self.wal_path)

    def test_recover_committed_txn(self):
        wal = WAL(self.wal_path)
        wal.open()
        tm = TransactionManager(wal, MockBufferPool(), MockFileManager())
        txn_id = tm.begin()
        tm.log_write(txn_id, 10, b'old', b'committed')
        tm.commit(txn_id)
        wal.flush()
        wal.close()

        # Reopen with a fresh buffer pool.
        wal2 = WAL(self.wal_path)
        wal2.open()
        bp = MockBufferPool()
        tm2 = TransactionManager(wal2, bp, MockFileManager())
        result = tm2.recover()
        wal2.close()

        assert result is True
        assert bp.pages[10] == b'committed'

    def test_recover_skips_uncommitted_txn(self):
        wal = WAL(self.wal_path)
        wal.open()
        tm = TransactionManager(wal, MockBufferPool(), MockFileManager())
        t1 = tm.begin()
        tm.log_write(t1, 10, b'old', b'committed')
        tm.commit(t1)
        t2 = tm.begin()
        tm.log_write(t2, 20, b'old2', b'uncommitted')
        wal.flush()
        wal.close()

        wal2 = WAL(self.wal_path)
        wal2.open()
        bp = MockBufferPool()
        tm2 = TransactionManager(wal2, bp, MockFileManager())
        tm2.recover()
        wal2.close()

        assert bp.pages.get(10) == b'committed'
        assert 20 not in bp.pages

    def test_recover_empty_wal(self):
        wal = WAL(self.wal_path)
        wal.open()
        tm = TransactionManager(wal, MockBufferPool(), MockFileManager())
        wal.flush()
        wal.close()

        wal2 = WAL(self.wal_path)
        wal2.open()
        bp = MockBufferPool()
        tm2 = TransactionManager(wal2, bp, MockFileManager())
        result = tm2.recover()
        wal2.close()

        assert result is False
        assert bp.pages == {}
