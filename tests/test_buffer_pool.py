"""Tests for tinydb file manager and buffer pool."""

import os
import struct
import tempfile
import pytest

from tinydb.storage.page import Page
from tinydb.storage.file_manager import FileManager
from tinydb.storage.buffer_pool import BufferPool


# =========================================================================
# FileManager tests
# =========================================================================

class TestFileManager:
    """Verify single-file page storage."""

    def setup_method(self):
        self.tmp = tempfile.NamedTemporaryFile(delete=False, suffix='.db')
        self.tmp.close()
        self.fm = FileManager(self.tmp.name)

    def teardown_method(self):
        self.fm.close()
        os.unlink(self.tmp.name)

    def test_create_new_file_if_not_exists(self):
        """FileManager creates the file when it doesn't exist."""
        assert os.path.exists(self.tmp.name)

    def test_allocate_page_returns_incrementing_ids(self):
        p0 = self.fm.allocate_page()
        p1 = self.fm.allocate_page()
        assert p0 == 0
        assert p1 == 1

    def test_write_then_read_page(self):
        p = Page(page_id=0, flags=Page.TABLE_DATA)
        p.insert_record(b'hello')
        self.fm.write_page(0, p)

        p2 = self.fm.read_page(0)
        assert p2.page_id == 0
        assert p2.get_record(0) == b'hello'

    def test_read_page_preserves_flags(self):
        p = Page(page_id=0, flags=Page.CATALOG)
        self.fm.write_page(0, p)
        p2 = self.fm.read_page(0)
        assert p2.flags == Page.CATALOG

    def test_read_unwritten_page_returns_empty_page(self):
        """Reading a page beyond what's written returns a zeroed page."""
        p = self.fm.read_page(5)
        assert p.page_id == 0
        assert p.slot_count == 0

    def test_write_multiple_pages(self):
        for pid in range(3):
            p = Page(page_id=pid)
            p.insert_record(f'page-{pid}'.encode())
            self.fm.write_page(pid, p)

        for pid in range(3):
            p = self.fm.read_page(pid)
            assert p.get_record(0) == f'page-{pid}'.encode()

    def test_write_page_persists_across_close(self):
        p = Page(page_id=0)
        p.insert_record(b'persistent')
        self.fm.write_page(0, p)
        self.fm.close()

        fm2 = FileManager(self.tmp.name)
        p2 = fm2.read_page(0)
        assert p2.get_record(0) == b'persistent'
        fm2.close()

    def test_free_page_adds_to_free_list(self):
        self.fm.allocate_page()  # 0
        self.fm.allocate_page()  # 1
        self.fm.free_page(0)
        # next allocation should reuse page 0
        assert self.fm.allocate_page() == 0


# =========================================================================
# BufferPool tests
# =========================================================================

class TestBufferPool:
    """Verify LRU buffer pool with dirty page tracking."""

    def setup_method(self):
        self.tmp = tempfile.NamedTemporaryFile(delete=False, suffix='.db')
        self.tmp.close()
        self.fm = FileManager(self.tmp.name)
        self.bp = BufferPool(self.fm, capacity=3)

    def teardown_method(self):
        self.bp.close()
        os.unlink(self.tmp.name)

    def test_get_page_loads_from_disk(self):
        p = Page(page_id=0)
        p.insert_record(b'disk-data')
        self.fm.write_page(0, p)

        # fresh pool
        bp = BufferPool(self.fm, capacity=3)
        p2 = bp.get_page(0)
        assert p2.get_record(0) == b'disk-data'
        bp.close()

    def test_get_page_caches(self):
        """Second get_page for same id should return same object (cache hit)."""
        p = Page(page_id=0)
        p.insert_record(b'cached')
        self.fm.write_page(0, p)

        bp = BufferPool(self.fm, capacity=3)
        p1 = bp.get_page(0)
        p2 = bp.get_page(0)
        assert p1 is p2
        bp.close()

    def test_mark_dirty_then_flush(self):
        p = self.bp.get_page(0)
        p.insert_record(b'dirty-data')
        self.bp.mark_dirty(0)

        self.bp.flush_page(0)

        # read back from disk directly
        p2 = self.fm.read_page(0)
        assert p2.get_record(0) == b'dirty-data'

    def test_flush_all_writes_all_dirty(self):
        p0 = self.bp.get_page(0)
        p0.insert_record(b'd0')
        self.bp.mark_dirty(0)
        p1 = self.bp.get_page(1)
        p1.insert_record(b'd1')
        self.bp.mark_dirty(1)

        self.bp.flush_all()

        assert self.fm.read_page(0).get_record(0) == b'd0'
        assert self.fm.read_page(1).get_record(0) == b'd1'

    def test_evict_removes_lru(self):
        """When pool is full, adding a new page evicts the LRU page."""
        # fill pool: pages 0, 1, 2
        self.bp.get_page(0)
        self.bp.get_page(1)
        self.bp.get_page(2)

        # access page 0 to make it recently used
        self.bp.get_page(0)

        # allocate page 3 -> should evict page 1 (LRU)
        self.bp.get_page(3)

        assert 3 in self.bp._cache
        assert 1 not in self.bp._cache
        # 0 and 2 should still be present
        assert 0 in self.bp._cache
        assert 2 in self.bp._cache

    def test_evict_dirty_page_writes_back(self):
        """Evicting a dirty page flushes it to disk first."""
        p = self.bp.get_page(0)
        p.insert_record(b'evict-me')
        self.bp.mark_dirty(0)

        # fill rest so page 0 is LRU
        self.bp.get_page(1)
        self.bp.get_page(2)
        # trigger eviction of page 0 by adding page 3
        self.bp.get_page(3)

        # page 0 should have been flushed
        p2 = self.fm.read_page(0)
        assert p2.get_record(0) == b'evict-me'

    def test_close_flushes_all(self):
        p = self.bp.get_page(0)
        p.insert_record(b'close-data')
        self.bp.mark_dirty(0)
        self.bp.close()

        # Reopen the file with a fresh FileManager to verify persistence.
        fm2 = FileManager(self.tmp.name)
        p2 = fm2.read_page(0)
        assert p2.get_record(0) == b'close-data'
        fm2.close()

    def test_default_capacity_is_100(self):
        bp = BufferPool(self.fm)
        assert bp.capacity == 100
        bp.close()
