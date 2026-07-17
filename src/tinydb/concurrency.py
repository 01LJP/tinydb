"""Concurrency control primitives for tinydb.

Provides ReadWriteLock (multiple-reader, single-writer) and LockManager
(table-level lock management with a global lock for DDL operations).
"""

import threading
from typing import Dict


class ReadWriteLock:
    """Multiple-reader, single-writer lock.

    Allows concurrent reads but exclusive writes. Writers wait until all
    current readers release the lock.
    """

    def __init__(self):
        self._read_ready = threading.Condition(threading.Lock())
        self._readers = 0

    def acquire_read(self):
        """Acquire a shared read lock."""
        with self._read_ready:
            self._readers += 1

    def release_read(self):
        """Release a shared read lock."""
        with self._read_ready:
            self._readers -= 1
            if self._readers == 0:
                self._read_ready.notify_all()

    def acquire_write(self):
        """Acquire an exclusive write lock.

        Blocks until all current readers release.
        """
        self._read_ready.acquire()
        while self._readers > 0:
            self._read_ready.wait()

    def release_write(self):
        """Release an exclusive write lock."""
        self._read_ready.release()

    def __enter__(self):
        """Context manager for write lock (default)."""
        self.acquire_write()
        return self

    def __exit__(self, *args):
        self.release_write()


class ReadLockContext:
    """Context manager for acquiring a read lock."""

    def __init__(self, lock: ReadWriteLock):
        self.lock = lock

    def __enter__(self):
        self.lock.acquire_read()
        return self

    def __exit__(self, *args):
        self.lock.release_read()


class WriteLockContext:
    """Context manager for acquiring a write lock."""

    def __init__(self, lock: ReadWriteLock):
        self.lock = lock

    def __enter__(self):
        self.lock.acquire_write()
        return self

    def __exit__(self, *args):
        self.lock.release_write()


class LockManager:
    """Manages per-table locks and a global lock for DDL operations.

    Thread-safe: the internal dictionary is protected by its own lock.
    """

    def __init__(self):
        self._global_lock = ReadWriteLock()
        self._table_locks: Dict[str, ReadWriteLock] = {}
        self._lock_table_lock = threading.Lock()  # protects _table_locks dict

    def get_table_lock(self, table_name: str) -> ReadWriteLock:
        """Return the ReadWriteLock for a table, creating it if needed."""
        with self._lock_table_lock:
            if table_name not in self._table_locks:
                self._table_locks[table_name] = ReadWriteLock()
            return self._table_locks[table_name]

    def read_lock(self, table_name: str) -> ReadLockContext:
        """Return a context manager for a table read lock."""
        return ReadLockContext(self.get_table_lock(table_name))

    def write_lock(self, table_name: str) -> WriteLockContext:
        """Return a context manager for a table write lock."""
        return WriteLockContext(self.get_table_lock(table_name))

    def global_read_lock(self) -> ReadLockContext:
        """Return a context manager for the global read lock."""
        return ReadLockContext(self._global_lock)

    def global_write_lock(self) -> WriteLockContext:
        """Return a context manager for the global write lock."""
        return WriteLockContext(self._global_lock)
