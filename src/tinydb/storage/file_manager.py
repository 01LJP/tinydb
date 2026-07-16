"""Single-file page storage manager for tinydb.

File layout:
    page 0      -> catalog page
    page 1..N   -> table-data / index-data pages

A free-list tracks pages that were freed and can be reused on the next
allocation.
"""

import os

from tinydb.storage.page import Page, PAGE_SIZE


class FileManager:
    """Manages reading and writing fixed-size pages in a single ``.db`` file."""

    def __init__(self, path: str):
        self.path = path
        if not os.path.exists(path):
            self._file = open(path, "w+b")
        else:
            self._file = open(path, "r+b")

        self._file.seek(0, 2)  # seek to end
        size = self._file.tell()
        self._next_page_id = size // PAGE_SIZE
        self._free_pages: list = []

    # ------------------------------------------------------------------
    # Page I/O
    # ------------------------------------------------------------------

    def read_page(self, page_id: int) -> Page:
        """Read a page from disk. Returns a zeroed page if unwritten."""
        self._file.seek(page_id * PAGE_SIZE)
        data = self._file.read(PAGE_SIZE)
        if len(data) < PAGE_SIZE:
            data = data + b"\x00" * (PAGE_SIZE - len(data))
        return Page.from_bytes(data)

    def write_page(self, page_id: int, page: Page) -> None:
        """Write a page to disk at the given page slot."""
        self._file.seek(page_id * PAGE_SIZE)
        self._file.write(page.to_bytes())
        self._file.flush()

    # ------------------------------------------------------------------
    # Allocation
    # ------------------------------------------------------------------

    def allocate_page(self) -> int:
        """Return a fresh page id, reusing a freed page if available."""
        if self._free_pages:
            return self._free_pages.pop()
        pid = self._next_page_id
        self._next_page_id += 1
        # Extend the file so the new page slot is addressable.
        self._file.seek(pid * PAGE_SIZE)
        self._file.write(b"\x00" * PAGE_SIZE)
        self._file.flush()
        return pid

    def free_page(self, page_id: int) -> None:
        """Mark a page as free so its slot can be reused."""
        self._free_pages.append(page_id)

    # ------------------------------------------------------------------
    # Lifecycle
    # ------------------------------------------------------------------

    def close(self) -> None:
        """Close the underlying file handle (idempotent)."""
        if not self._file.closed:
            self._file.close()
