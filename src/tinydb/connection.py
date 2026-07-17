"""Connection management for tinydb.

Provides ConnectionPool for managing multiple concurrent connections
to the same database file.
"""

import threading
from typing import Optional

from tinydb.database import Database


class Connection:
    """A single database connection.

    Wraps a Database instance and tracks transaction state.
    """

    def __init__(self, db: Database):
        self.db = db
        self._in_transaction = False

    def execute(self, sql: str):
        """Execute a SQL statement."""
        return self.db.execute(sql)

    def begin(self):
        """Start a transaction."""
        self.db.execute("BEGIN")
        self._in_transaction = True

    def commit(self):
        """Commit the current transaction."""
        self.db.execute("COMMIT")
        self._in_transaction = False

    def rollback(self):
        """Rollback the current transaction."""
        self.db.execute("ROLLBACK")
        self._in_transaction = False

    def close(self):
        """Close the underlying database."""
        if self._in_transaction:
            self.rollback()
        self.db.close()

    def __enter__(self):
        return self

    def __exit__(self, *args):
        self.close()


class ConnectionPool:
    """Manages multiple connections to the same database.

    Connections are created on demand and reused. A semaphore limits
    the number of concurrent connections.
    """

    def __init__(self, db_path: str, max_connections: int = 10):
        self.db_path = db_path
        self.max_connections = max_connections
        self._pool: list = []
        self._lock = threading.Lock()
        self._semaphore = threading.Semaphore(max_connections)

    def acquire(self) -> Connection:
        """Acquire a connection from the pool.

        Blocks if the pool is at capacity. Creates a new connection
        if the pool is empty.
        """
        self._semaphore.acquire()
        with self._lock:
            if self._pool:
                return self._pool.pop()
        # Pool is empty, create new connection
        db = Database(self.db_path)
        return Connection(db)

    def release(self, conn: Connection):
        """Release a connection back to the pool."""
        with self._lock:
            self._pool.append(conn)
        self._semaphore.release()

    def close_all(self):
        """Close all pooled connections."""
        with self._lock:
            for conn in self._pool:
                conn.close()
            self._pool.clear()

    def __enter__(self):
        return self

    def __exit__(self, *args):
        self.close_all()
