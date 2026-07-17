"""Write-Ahead Log (WAL) for tinydb.

WAL file layout (binary, all fields big-endian):
    Header (16 bytes):
        - magic:      4 bytes  (b'WAL\\x00')
        - version:    2 bytes
        - page_size:  2 bytes
        - checkpoint: 4 bytes
        - padding:   4 bytes
    Followed by a stream of log records.

Each log record:
    - txn_id:    4 bytes  (>I)
    - op_type:   1 byte   (B)
    - page_id:   4 bytes  (>I)
    - old_len:   2 bytes  (>H)
    - new_len:   2 bytes  (>H)
    - old_data:  [old_len bytes]
    - new_data:  [new_len bytes]
    - checksum:  4 bytes  (CRC32 of everything before it, >I)
"""

import os
import struct
import threading
import zlib
from typing import List


# =========================================================================
# WAL constants
# =========================================================================

WAL_MAGIC = b'WAL\x00'
WAL_VERSION = 1
WAL_PAGE_SIZE = 4096
WAL_HEADER_SIZE = 16
# Header: magic (4) + version (2) + page_size (2) + checkpoint (4) + padding (4)
WAL_HEADER_FMT = '>4sHHII'
# Per-record header before data: txn_id (4) + op_type (1) + page_id (4) + old_len (2) + new_len (2)
WAL_RECORD_HDR_FMT = '>IBIHH'
WAL_RECORD_HDR_SIZE = struct.calcsize(WAL_RECORD_HDR_FMT)
WAL_CHECKSUM_SIZE = 4


# =========================================================================
# WAL operation types
# =========================================================================

class WalOpType:
    """WAL log-record operation types."""
    BEGIN = 1
    INSERT = 2
    UPDATE = 3
    DELETE = 4
    COMMIT = 5
    ABORT = 6
    CHECKPOINT = 7


# =========================================================================
# Log record
# =========================================================================

class LogRecord:
    """A single immutable WAL log record."""

    __slots__ = ('txn_id', 'op_type', 'page_id', 'old_data', 'new_data')

    def __init__(self, txn_id: int, op_type: int, page_id: int = 0,
                 old_data: bytes = b'', new_data: bytes = b''):
        self.txn_id = txn_id
        self.op_type = op_type
        self.page_id = page_id
        self.old_data = old_data
        self.new_data = new_data

    def __repr__(self):
        return (
            f'LogRecord(txn_id={self.txn_id}, op_type={self.op_type}, '
            f'page_id={self.page_id}, old_len={len(self.old_data)}, '
            f'new_len={len(self.new_data)})'
        )


# =========================================================================
# WAL
# =========================================================================

class WAL:
    """Write-Ahead Log.

    Records every transactional mutation so that the engine can recover a
    consistent state after a crash.
    """

    def __init__(self, wal_path: str):
        self.wal_path = wal_path
        self.file = None
        self._write_lock = threading.Lock()

    # ------------------------------------------------------------------
    # Lifecycle
    # ------------------------------------------------------------------

    def open(self):
        """Open the WAL file, creating it (with header) if necessary."""
        if os.path.exists(self.wal_path) and os.path.getsize(self.wal_path) >= WAL_HEADER_SIZE:
            self.file = open(self.wal_path, 'r+b')
        else:
            self.file = open(self.wal_path, 'w+b')
            self._write_header()

    def _write_header(self):
        """Flush the 16-byte WAL header to the start of the file."""
        header = struct.pack(
            WAL_HEADER_FMT,
            WAL_MAGIC,
            WAL_VERSION,
            WAL_PAGE_SIZE,
            0,  # checkpoint position
            0,  # padding
        )
        self.file.seek(0)
        self.file.write(header)
        self.file.flush()

    def close(self):
        """Close the underlying file handle."""
        if self.file and not self.file.closed:
            self.file.close()
        self.file = None

    # ------------------------------------------------------------------
    # Logging operations
    # ------------------------------------------------------------------

    def log_begin(self, txn_id: int):
        """Record a transaction BEGIN."""
        self._write_record(txn_id, WalOpType.BEGIN)

    def log_write(self, txn_id: int, page_id: int, old_data: bytes, new_data: bytes):
        """Record a page modification (insert/update/delete all use this)."""
        self._write_record(txn_id, WalOpType.INSERT, page_id, old_data, new_data)

    def log_commit(self, txn_id: int):
        """Record a transaction COMMIT."""
        self._write_record(txn_id, WalOpType.COMMIT)

    def log_abort(self, txn_id: int):
        """Record a transaction ABORT."""
        self._write_record(txn_id, WalOpType.ABORT)

    def log_checkpoint(self):
        """Record a CHECKPOINT (used by the Checkpoint manager)."""
        self._write_record(0, WalOpType.CHECKPOINT)

    # ------------------------------------------------------------------
    # Low-level record write
    # ------------------------------------------------------------------

    def _write_record(self, txn_id: int, op_type: int, page_id: int = 0,
                      old_data: bytes = b'', new_data: bytes = b''):
        """Append one binary log record to the WAL file (thread-safe)."""
        with self._write_lock:
            assert self.file is not None, 'WAL not open'
            record = struct.pack(
                WAL_RECORD_HDR_FMT,
                txn_id, op_type, page_id, len(old_data), len(new_data),
            )
            record += old_data + new_data
            checksum = zlib.crc32(record) & 0xFFFFFFFF
            record += struct.pack('>I', checksum)
            self.file.seek(0, 2)  # seek to end
            self.file.write(record)

    # ------------------------------------------------------------------
    # Flush
    # ------------------------------------------------------------------

    def flush(self):
        """Force buffered WAL data down to the OS and fsync to disk."""
        if self.file and not self.file.closed:
            self.file.flush()
            try:
                os.fsync(self.file.fileno())
            except OSError:
                pass

    # ------------------------------------------------------------------
    # Parse records
    # ------------------------------------------------------------------

    def parse_records(self) -> List[LogRecord]:
        """Parse every log record in the WAL file.

        The 16-byte header is skipped.  Records are read sequentially until
        the end of file or a structurally invalid / corrupt tail is reached.
        """
        records: List[LogRecord] = []
        if self.file is None:
            return records
        self.file.seek(0, 2)
        file_size = self.file.tell()
        if file_size <= WAL_HEADER_SIZE:
            return records
        self.file.seek(WAL_HEADER_SIZE)
        while True:
            pos = self.file.tell()
            remaining = file_size - pos
            if remaining < WAL_RECORD_HDR_SIZE + WAL_CHECKSUM_SIZE:
                break
            hdr = self.file.read(WAL_RECORD_HDR_SIZE)
            if len(hdr) < WAL_RECORD_HDR_SIZE:
                break
            txn_id, op_type, page_id, old_len, new_len = struct.unpack(
                WAL_RECORD_HDR_FMT, hdr
            )
            payload_size = old_len + new_len
            if remaining - WAL_RECORD_HDR_SIZE < payload_size + WAL_CHECKSUM_SIZE:
                break
            old_data = self.file.read(old_len) if old_len else b''
            new_data = self.file.read(new_len) if new_len else b''
            if len(old_data) < old_len or len(new_data) < new_len:
                break
            crc_bytes = self.file.read(WAL_CHECKSUM_SIZE)
            if len(crc_bytes) < WAL_CHECKSUM_SIZE:
                break
            (expected_crc,) = struct.unpack('>I', crc_bytes)
            actual_crc = zlib.crc32(hdr + old_data + new_data) & 0xFFFFFFFF
            if actual_crc != expected_crc:
                # Corrupt record: stop parsing.
                break
            records.append(LogRecord(txn_id, op_type, page_id, old_data, new_data))
        return records

    # ------------------------------------------------------------------
    # Crash recovery
    # ------------------------------------------------------------------

    def recover(self, buffer_pool) -> bool:
        """Redo recovery from this WAL.

        Steps:
        1. Parse all log records.
        2. Identify which transactions committed (or aborted).
        3. Redo every committed transaction's page writes on the buffer pool.
        4. Discard uncommitted / aborted transactions.

        Returns True if recovery actually replayed at least one record,
        False if the WAL was empty.
        """
        records = self.parse_records()
        if not records:
            return False

        committed_txns = set()
        aborted_txns = set()
        for rec in records:
            if rec.op_type == WalOpType.COMMIT:
                committed_txns.add(rec.txn_id)
            elif rec.op_type == WalOpType.ABORT:
                aborted_txns.add(rec.txn_id)

        # Redo committed writes (INSERT/UPDATE/DELETE records).
        for rec in records:
            if rec.op_type in (WalOpType.INSERT, WalOpType.UPDATE, WalOpType.DELETE):
                if rec.txn_id in committed_txns and rec.txn_id not in aborted_txns:
                    if rec.new_data:
                        buffer_pool.put(rec.page_id, rec.new_data)
        return True

    # ------------------------------------------------------------------
    # Truncate (used by checkpoint)
    # ------------------------------------------------------------------

    def truncate(self):
        """Erase all log records, rewrite a fresh header."""
        if self.file and not self.file.closed:
            self.file.seek(0)
            self.file.truncate(0)
            self._write_header()


# =========================================================================
# Checkpoint
# =========================================================================

class Checkpoint:
    """Periodic WAL checkpoint manager.

    After every ``interval`` completed transactions, call ``do_checkpoint``:
    1. flush all dirty pages back to the main DB file via the buffer pool,
    2. clear the WAL file,
    3. append a CHECKPOINT record.
    """

    def __init__(self, wal: WAL, buffer_pool, interval: int = 100):
        self.wal = wal
        self.buffer_pool = buffer_pool
        self.interval = interval
        self.txn_count = 0

    def maybe_checkpoint(self):
        """Trigger a checkpoint if interval transactions have completed."""
        self.txn_count += 1
        if self.txn_count >= self.interval:
            self.do_checkpoint()

    def do_checkpoint(self):
        """Perform a checkpoint now."""
        # 1. Flush dirty pages to the main DB file.
        self.buffer_pool.flush_all()
        # 2. Clear the WAL and write a fresh header.
        self.wal.truncate()
        # 3. Append a CHECKPOINT record.
        self.wal.log_checkpoint()
        self.wal.flush()
        # 4. Reset counter.
        self.txn_count = 0
