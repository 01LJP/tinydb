"""LRU page buffer pool for tinydb.

Caches up to *capacity* pages in memory.  On eviction the least-recently-used
page is removed; dirty pages are written back to disk before being evicted.
"""

from collections import OrderedDict

from tinydb.storage.page import Page


class BufferPool:
    """An LRU cache of pages backed by a :class:`~tinydb.storage.file_manager.FileManager`."""

    def __init__(self, file_manager, capacity: int = 100):
        self.file_manager = file_manager
        self.capacity = capacity
        self._cache: OrderedDict = OrderedDict()  # page_id -> Page
        self._dirty: set = set()                 # set of page_id

    # ------------------------------------------------------------------
    # Core operations
    # ------------------------------------------------------------------

    def get_page(self, page_id: int) -> Page:
        """Fetch a page, using the cache on a hit and loading on a miss."""
        if page_id in self._cache:
            self._cache.move_to_end(page_id)
            return self._cache[page_id]

        # Cache miss: load from disk.
        page = self.file_manager.read_page(page_id)
        self._cache[page_id] = page
        self._cache.move_to_end(page_id)

        if len(self._cache) > self.capacity:
            self.evict()

        return page

    def put(self, page_id: int, data: bytes) -> None:
        """Replace a page's contents in the cache (used by WAL recovery).

        Resets the page buffer to *data* and marks it dirty so the redo
        lands on disk when the buffer pool is flushed.
        """
        if page_id not in self._cache:
            self.get_page(page_id)
        page = self._cache[page_id]
        # Reinitialise the raw buffer to the redone image.
        page.buf = bytearray(page.PAGE_SIZE)
        page.buf[:len(data)] = data[:page.PAGE_SIZE]
        page._read_header()
        self._cache.move_to_end(page_id)
        self._dirty.add(page_id)

    def mark_dirty(self, page_id: int) -> None:
        """Mark a page dirty so it is written back on eviction/flush."""
        self._dirty.add(page_id)

    def flush_page(self, page_id: int) -> None:
        """Write a single dirty page to disk and clear its dirty flag."""
        if page_id in self._dirty:
            page = self._cache[page_id]
            self.file_manager.write_page(page_id, page)
            self._dirty.discard(page_id)

    def flush_all(self) -> None:
        """Write every dirty page to disk."""
        for page_id in list(self._dirty):
            self.flush_page(page_id)

    # ------------------------------------------------------------------
    # Eviction
    # ------------------------------------------------------------------

    def evict(self) -> None:
        """Evict the least-recently-used page, flushing it first if dirty."""
        page_id, page = self._cache.popitem(last=False)
        if page_id in self._dirty:
            self.file_manager.write_page(page_id, page)
            self._dirty.discard(page_id)

    # ------------------------------------------------------------------
    # Lifecycle
    # ------------------------------------------------------------------

    def close(self) -> None:
        """Flush all dirty pages then close the underlying file manager.

        Idempotent: subsequent calls are a no-op.
        """
        if not self.file_manager._file.closed:
            self.flush_all()
            self.file_manager.close()
