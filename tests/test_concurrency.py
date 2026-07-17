"""Tests for concurrency control."""

import os
import tempfile
import threading
import time
import pytest

import tinydb
from tinydb.concurrency import ReadWriteLock, LockManager
from tinydb.connection import ConnectionPool, Connection


@pytest.fixture
def db_path():
    """Create a temporary database path."""
    with tempfile.NamedTemporaryFile(suffix=".tdb", delete=False) as f:
        path = f.name
    try:
        yield path
    finally:
        for ext in ["", ".wal"]:
            if os.path.exists(path + ext):
                os.unlink(path + ext)


class TestReadWriteLock:
    """Test ReadWriteLock primitive."""

    def test_concurrent_reads(self):
        lock = ReadWriteLock()
        results = []

        def reader(n):
            lock.acquire_read()
            results.append(f"read_{n}_start")
            time.sleep(0.05)
            results.append(f"read_{n}_end")
            lock.release_read()

        threads = [threading.Thread(target=reader, args=(i,)) for i in range(3)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()

        # All reads should have started before any ended
        starts = [r for r in results if r.endswith("_start")]
        assert len(starts) == 3

    def test_write_blocks_read(self):
        lock = ReadWriteLock()
        events = []

        def writer():
            lock.acquire_write()
            events.append("write_start")
            time.sleep(0.1)
            events.append("write_end")
            lock.release_write()

        def reader():
            time.sleep(0.02)  # let writer start first
            lock.acquire_read()
            events.append("read_start")
            lock.release_read()
            events.append("read_end")

        t1 = threading.Thread(target=writer)
        t2 = threading.Thread(target=reader)
        t1.start()
        t2.start()
        t1.join()
        t2.join()

        # Read should not start until write ends
        write_end_idx = events.index("write_end")
        read_start_idx = events.index("read_start")
        assert read_start_idx > write_end_idx

    def test_writes_are_serialized(self):
        lock = ReadWriteLock()
        active_writers = []
        max_concurrent = []

        def writer(n):
            lock.acquire_write()
            active_writers.append(n)
            max_concurrent.append(len(active_writers))
            time.sleep(0.05)
            active_writers.remove(n)
            lock.release_write()

        threads = [threading.Thread(target=writer, args=(i,)) for i in range(3)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()

        # At most 1 writer active at a time
        assert max(m for m in max_concurrent) <= 1


class TestLockManager:
    """Test LockManager."""

    def test_table_lock_independence(self):
        mgr = LockManager()
        lock_a = mgr.get_table_lock("table_a")
        lock_b = mgr.get_table_lock("table_b")
        assert lock_a is not lock_b

    def test_same_table_same_lock(self):
        mgr = LockManager()
        lock1 = mgr.get_table_lock("table_a")
        lock2 = mgr.get_table_lock("table_a")
        assert lock1 is lock2

    def test_different_tables_concurrent_writes(self):
        mgr = LockManager()
        results = []

        def write_table(name):
            with mgr.write_lock(name):
                results.append(f"{name}_start")
                time.sleep(0.05)
                results.append(f"{name}_end")

        t1 = threading.Thread(target=write_table, args=("a",))
        t2 = threading.Thread(target=write_table, args=("b",))
        t1.start()
        t2.start()
        t1.join()
        t2.join()

        # Both should complete without blocking each other
        assert len(results) == 4


class TestConcurrentDatabase:
    """Test concurrent database access."""

    def test_concurrent_selects(self, db_path):
        """Test concurrent reads through a shared Database instance."""
        db = tinydb.Database(db_path)
        db.execute("CREATE TABLE t (id INT, val TEXT)")
        for i in range(10):
            db.execute(f"INSERT INTO t VALUES ({i}, 'v{i}')")

        results = []
        errors = []

        def reader():
            try:
                r = db.execute("SELECT * FROM t")
                results.append(len(r))
            except Exception as e:
                errors.append(e)

        threads = [threading.Thread(target=reader) for _ in range(5)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()

        assert not errors
        assert all(r == 10 for r in results)
        db.close()

    def test_concurrent_inserts(self, db_path):
        """Test concurrent inserts through a shared Database instance."""
        db = tinydb.Database(db_path)
        db.execute("CREATE TABLE t (id INT PRIMARY KEY, val TEXT)")

        errors = []

        def inserter(start):
            try:
                for i in range(5):
                    db.execute(f"INSERT INTO t VALUES ({start + i}, 'v{start + i}')")
            except Exception as e:
                errors.append(e)

        threads = [threading.Thread(target=inserter, args=(i * 100,)) for i in range(3)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()

        assert not errors

        result = db.execute("SELECT * FROM t")
        assert len(result) == 15  # 3 threads * 5 inserts
        db.close()


class TestConnectionPool:
    """Test ConnectionPool."""

    def test_acquire_release(self, db_path):
        with tinydb.open(db_path) as db:
            db.execute("CREATE TABLE t (id INT)")

        pool = ConnectionPool(db_path, max_connections=2)
        conn1 = pool.acquire()
        conn2 = pool.acquire()

        pool.release(conn1)
        pool.release(conn2)

        # Acquire should reuse pooled connections
        conn3 = pool.acquire()
        pool.release(conn3)
        pool.close_all()

    def test_max_connections_blocks(self, db_path):
        with tinydb.open(db_path) as db:
            db.execute("CREATE TABLE t (id INT)")

        pool = ConnectionPool(db_path, max_connections=1)
        conn1 = pool.acquire()

        acquired = []

        def try_acquire():
            conn = pool.acquire()
            acquired.append(True)
            pool.release(conn)

        t = threading.Thread(target=try_acquire)
        t.start()
        time.sleep(0.05)

        # Should not have acquired yet (pool full)
        assert len(acquired) == 0

        pool.release(conn1)
        t.join(timeout=1)
        assert len(acquired) == 1
        pool.close_all()

    def test_close_all(self, db_path):
        pool = ConnectionPool(db_path, max_connections=3)
        for _ in range(3):
            pool.release(Connection(tinydb.Database(db_path)))
        pool.close_all()
        assert len(pool._pool) == 0
