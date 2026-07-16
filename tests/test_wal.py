"""Tests for tinydb WAL (Write-Ahead Log).

Covers: WAL header, record format, log operations (begin/commit/abort/write),
parsing, crash recovery, and checkpoint.
"""

import os
import struct
import tempfile
import pytest

from tinydb.transaction.wal import (
    WalOpType,
    LogRecord,
    WAL,
    Checkpoint,
)


# =========================================================================
# LogRecord tests
# =========================================================================

class TestLogRecord:
    """Verify LogRecord structure."""

    def test_create_record(self):
        rec = LogRecord(txn_id=1, op_type=WalOpType.INSERT, page_id=5,
                        old_data=b'old', new_data=b'new')
        assert rec.txn_id == 1
        assert rec.op_type == WalOpType.INSERT
        assert rec.page_id == 5
        assert rec.old_data == b'old'
        assert rec.new_data == b'new'

    def test_create_record_defaults(self):
        rec = LogRecord(txn_id=2, op_type=WalOpType.BEGIN)
        assert rec.txn_id == 2
        assert rec.op_type == WalOpType.BEGIN
        assert rec.page_id == 0
        assert rec.old_data == b''
        assert rec.new_data == b''

    def test_op_type_constants(self):
        assert WalOpType.BEGIN == 1
        assert WalOpType.INSERT == 2
        assert WalOpType.UPDATE == 3
        assert WalOpType.DELETE == 4
        assert WalOpType.COMMIT == 5
        assert WalOpType.ABORT == 6
        assert WalOpType.CHECKPOINT == 7


# =========================================================================
# WAL header tests
# =========================================================================

class TestWalHeader:
    """Verify WAL file header is written on creation."""

    def setup_method(self):
        self.tmp = tempfile.NamedTemporaryFile(delete=False, suffix='.wal')
        self.tmp.close()
        self.wal_path = self.tmp.name

    def teardown_method(self):
        if os.path.exists(self.wal_path):
            os.unlink(self.wal_path)

    def test_header_written_on_open(self):
        wal = WAL(self.wal_path)
        wal.open()
        wal.close()
        with open(self.wal_path, 'rb') as f:
            header = f.read(16)
        magic = header[:4]
        assert magic == b'WAL\x00'

    def test_header_fields(self):
        wal = WAL(self.wal_path)
        wal.open()
        wal.close()
        with open(self.wal_path, 'rb') as f:
            header = f.read(16)
        # Header is 16 bytes: magic(4) version(2) page_size(2) checkpoint(4) padding(4)
        assert len(header) == 16
        magic, version, page_size, checkpoint, _pad = struct.unpack('>4sHHII', header)
        assert magic == b'WAL\x00'
        assert version == 1
        assert page_size == 4096
        assert checkpoint == 0


# =========================================================================
# WAL record I/O tests
# =========================================================================

class TestWalRecordIO:
    """Verify records can be written and parsed back."""

    def setup_method(self):
        self.tmp = tempfile.NamedTemporaryFile(delete=False, suffix='.wal')
        self.tmp.close()
        self.wal_path = self.tmp.name
        self.wal = WAL(self.wal_path)
        self.wal.open()

    def teardown_method(self):
        if self.wal.file and not self.wal.file.closed:
            self.wal.close()
        if os.path.exists(self.wal_path):
            os.unlink(self.wal_path)

    def test_log_begin(self):
        self.wal.log_begin(1)
        records = self.wal.parse_records()
        assert len(records) == 1
        assert records[0].txn_id == 1
        assert records[0].op_type == WalOpType.BEGIN

    def test_log_write(self):
        self.wal.log_write(1, 5, b'old_data', b'new_data')
        records = self.wal.parse_records()
        assert len(records) == 1
        rec = records[0]
        assert rec.txn_id == 1
        assert rec.op_type == WalOpType.INSERT
        assert rec.page_id == 5
        assert rec.old_data == b'old_data'
        assert rec.new_data == b'new_data'

    def test_log_commit(self):
        self.wal.log_commit(1)
        records = self.wal.parse_records()
        assert len(records) == 1
        assert records[0].op_type == WalOpType.COMMIT

    def test_log_abort(self):
        self.wal.log_abort(1)
        records = self.wal.parse_records()
        assert len(records) == 1
        assert records[0].op_type == WalOpType.ABORT

    def test_log_multiple_records(self):
        self.wal.log_begin(1)
        self.wal.log_write(1, 0, b'a', b'b')
        self.wal.log_write(1, 1, b'c', b'd')
        self.wal.log_commit(1)
        records = self.wal.parse_records()
        assert len(records) == 4
        assert records[0].op_type == WalOpType.BEGIN
        assert records[1].op_type == WalOpType.INSERT
        assert records[2].op_type == WalOpType.INSERT
        assert records[3].op_type == WalOpType.COMMIT

    def test_log_empty_data(self):
        self.wal.log_write(1, 0, b'', b'')
        records = self.wal.parse_records()
        assert len(records) == 1
        assert records[0].old_data == b''
        assert records[0].new_data == b''

    def test_log_large_data(self):
        big = b'X' * 4096
        self.wal.log_write(1, 0, big, big)
        records = self.wal.parse_records()
        assert len(records) == 1
        assert len(records[0].old_data) == 4096
        assert len(records[0].new_data) == 4096

    def test_parse_empty_wal(self):
        records = self.wal.parse_records()
        assert records == []

    def test_persist_across_close_reopen(self):
        self.wal.log_begin(7)
        self.wal.log_write(7, 3, b'x', b'y')
        self.wal.log_commit(7)
        self.wal.close()
        wal2 = WAL(self.wal_path)
        wal2.open()
        records = wal2.parse_records()
        wal2.close()
        assert len(records) == 3
        assert records[0].txn_id == 7
        assert records[1].page_id == 3
        assert records[1].old_data == b'x'
        assert records[1].new_data == b'y'
        assert records[2].op_type == WalOpType.COMMIT


# =========================================================================
# WAL flush tests
# =========================================================================

class TestWalFlush:
    """Verify flush forces data to disk."""

    def setup_method(self):
        self.tmp = tempfile.NamedTemporaryFile(delete=False, suffix='.wal')
        self.tmp.close()
        self.wal_path = self.tmp.name
        self.wal = WAL(self.wal_path)
        self.wal.open()

    def teardown_method(self):
        if self.wal.file and not self.wal.file.closed:
            self.wal.close()
        if os.path.exists(self.wal_path):
            os.unlink(self.wal_path)

    def test_flush_writes_to_disk(self):
        self.wal.log_begin(1)
        self.wal.flush()
        # Read directly from disk without going through the WAL object.
        with open(self.wal_path, 'rb') as f:
            data = f.read()
        # Header is 16 bytes; record bytes should follow.
        assert len(data) > 16
        # First 4 bytes are magic.
        assert data[:4] == b'WAL\x00'


# =========================================================================
# Crash recovery tests
# =========================================================================

class TestWalRecovery:
    """Verify WAL crash recovery logic."""

    def setup_method(self):
        self.tmp = tempfile.NamedTemporaryFile(delete=False, suffix='.wal')
        self.tmp.close()
        self.wal_path = self.tmp.name

    def teardown_method(self):
        if os.path.exists(self.wal_path):
            os.unlink(self.wal_path)

    def _make_mock_buffer_pool(self):
        """Return a mock buffer pool that records put() calls."""

        class MockBufferPool:
            def __init__(self):
                self.writes = {}

            def put(self, page_id, data):
                self.writes[page_id] = data

        return MockBufferPool()

    def test_recover_committed_transaction(self):
        wal = WAL(self.wal_path)
        wal.open()
        wal.log_begin(1)
        wal.log_write(1, 10, b'old', b'committed_value')
        wal.log_commit(1)
        wal.close()

        wal2 = WAL(self.wal_path)
        wal2.open()
        bp = self._make_mock_buffer_pool()
        result = wal2.recover(bp)
        wal2.close()

        assert result is True
        assert 10 in bp.writes
        assert bp.writes[10] == b'committed_value'

    def test_recover_discards_uncommitted_transaction(self):
        wal = WAL(self.wal_path)
        wal.open()
        wal.log_begin(1)
        wal.log_write(1, 10, b'old', b'committed_value')
        wal.log_commit(1)
        # Txn 2 started but never committed.
        wal.log_begin(2)
        wal.log_write(2, 20, b'old2', b'uncommitted_value')
        wal.close()

        wal2 = WAL(self.wal_path)
        wal2.open()
        bp = self._make_mock_buffer_pool()
        result = wal2.recover(bp)
        wal2.close()

        assert result is True
        assert bp.writes.get(10) == b'committed_value'
        assert 20 not in bp.writes

    def test_recover_empty_wal(self):
        wal = WAL(self.wal_path)
        wal.open()
        wal.close()

        wal2 = WAL(self.wal_path)
        wal2.open()
        bp = self._make_mock_buffer_pool()
        result = wal2.recover(bp)
        wal2.close()

        assert result is False
        assert bp.writes == {}

    def test_recover_multiple_committed_txns(self):
        wal = WAL(self.wal_path)
        wal.open()
        wal.log_begin(1)
        wal.log_write(1, 1, b'a', b'A')
        wal.log_commit(1)
        wal.log_begin(2)
        wal.log_write(2, 2, b'b', b'B')
        wal.log_commit(2)
        wal.close()

        wal2 = WAL(self.wal_path)
        wal2.open()
        bp = self._make_mock_buffer_pool()
        wal2.recover(bp)
        wal2.close()

        assert bp.writes == {1: b'A', 2: b'B'}


# =========================================================================
# Checkpoint tests
# =========================================================================

class TestCheckpoint:
    """Verify Checkpoint management."""

    def setup_method(self):
        self.tmp = tempfile.NamedTemporaryFile(delete=False, suffix='.wal')
        self.tmp.close()
        self.wal_path = self.tmp.name

    def teardown_method(self):
        if os.path.exists(self.wal_path):
            os.unlink(self.wal_path)

    def _make_mock_buffer_pool(self):
        class MockBufferPool:
            def __init__(self):
                self.flushed = 0

            def flush_all(self):
                self.flushed += 1

        return MockBufferPool()

    def test_checkpoint_writes_record_and_clears_wal(self):
        wal = WAL(self.wal_path)
        wal.open()
        wal.log_begin(1)
        wal.log_write(1, 0, b'a', b'b')
        wal.log_commit(1)

        bp = self._make_mock_buffer_pool()
        cp = Checkpoint(wal, bp, interval=1)
        cp.do_checkpoint()
        wal.close()

        # After checkpoint, WAL should contain only the CHECKPOINT record.
        wal2 = WAL(self.wal_path)
        wal2.open()
        records = wal2.parse_records()
        wal2.close()

        assert len(records) == 1
        assert records[0].op_type == WalOpType.CHECKPOINT
        assert bp.flushed == 1

    def test_maybe_checkpoint_triggers_at_interval(self):
        wal = WAL(self.wal_path)
        wal.open()
        bp = self._make_mock_buffer_pool()
        cp = Checkpoint(wal, bp, interval=3)

        cp.maybe_checkpoint()
        cp.maybe_checkpoint()
        assert bp.flushed == 0
        cp.maybe_checkpoint()
        assert bp.flushed == 1
        wal.close()

    def test_maybe_checkpoint_resets_count(self):
        wal = WAL(self.wal_path)
        wal.open()
        bp = self._make_mock_buffer_pool()
        cp = Checkpoint(wal, bp, interval=2)

        cp.maybe_checkpoint()
        cp.maybe_checkpoint()
        assert bp.flushed == 1
        cp.maybe_checkpoint()
        cp.maybe_checkpoint()
        assert bp.flushed == 2
        wal.close()
