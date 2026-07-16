"""Slotted Page data structure and Record serialization.

Page layout (4096 bytes):
    +----------------------------------------------+
    | Page Header (12 bytes)                        |
    |   page_id: 4B | slot_count: 2B               |
    |   free_space: 2B | flags: 4B                  |
    +----------------------------------------------+
    | Slot Array (grows forward from header)        |
    |   [offset: 2B, length: 2B] per slot          |
    +----------------------------------------------+
    | Free Space                                    |
    +----------------------------------------------+
    | Records (grow backward from page end)         |
    +----------------------------------------------+
"""

import struct
import math

from tinydb.types import (
    DataType,
    serialize_value,
    deserialize_value,
    StorageError,
)

# =========================================================================
# Page constants
# =========================================================================

PAGE_SIZE = 4096
HEADER_SIZE = 12
SLOT_SIZE = 4  # offset (2B) + length (2B)

TABLE_DATA = 1
INDEX_DATA = 2
CATALOG = 3

# Big-endian: page_id(u32), slot_count(u16), free_space(u16), flags(u32)
HEADER_FMT = ">IHHI"
# Big-endian: offset(u16), length(u16)
SLOT_FMT = ">HH"


# =========================================================================
# Page
# =========================================================================


class Page:
    """A fixed-size 4096-byte slotted page.

    Records are stored from the end of the page growing backward.
    The slot array grows forward from just after the header.
    Free space lies between the two.
    """

    PAGE_SIZE = PAGE_SIZE
    HEADER_SIZE = HEADER_SIZE
    TABLE_DATA = TABLE_DATA
    INDEX_DATA = INDEX_DATA
    CATALOG = CATALOG

    __slots__ = ("buf", "page_id", "slot_count", "free_space", "flags")

    def __init__(self, page_id: int, flags: int = TABLE_DATA):
        self.buf = bytearray(PAGE_SIZE)
        self.page_id = page_id
        self.slot_count = 0
        self.free_space = PAGE_SIZE - HEADER_SIZE
        self.flags = flags
        self._write_header()

    # ------------------------------------------------------------------
    # Header / slot accessors
    # ------------------------------------------------------------------

    def _write_header(self) -> None:
        struct.pack_into(
            HEADER_FMT, self.buf, 0,
            self.page_id, self.slot_count, self.free_space, self.flags,
        )

    def _read_header(self) -> None:
        (
            self.page_id, self.slot_count, self.free_space, self.flags,
        ) = struct.unpack_from(HEADER_FMT, self.buf, 0)

    def _write_slot(self, slot_id: int, offset: int, length: int) -> None:
        pos = HEADER_SIZE + slot_id * SLOT_SIZE
        struct.pack_into(SLOT_FMT, self.buf, pos, offset, length)

    def _read_slot(self, slot_id: int):
        pos = HEADER_SIZE + slot_id * SLOT_SIZE
        return struct.unpack_from(SLOT_FMT, self.buf, pos)

    @property
    def _record_ptr(self) -> int:
        """Offset where the next record would start (growing backward)."""
        return self.free_space + HEADER_SIZE + self.slot_count * SLOT_SIZE

    # ------------------------------------------------------------------
    # Core operations
    # ------------------------------------------------------------------

    def has_space(self, data_len: int) -> bool:
        """Return True if a record of *data_len* bytes plus one slot fits."""
        return data_len + SLOT_SIZE <= self.free_space

    def insert_record(self, data: bytes) -> int:
        """Insert a record and return its slot_id.

        Raises StorageError if the page lacks sufficient free space.
        """
        data_len = len(data)
        if not self.has_space(data_len):
            raise StorageError(
                f"page {self.page_id}: need {data_len + SLOT_SIZE} bytes, "
                f"only {self.free_space} free"
            )
        ptr = self._record_ptr
        rec_offset = ptr - data_len
        # Write record bytes.
        self.buf[rec_offset:rec_offset + data_len] = data
        # Append slot entry.
        self._write_slot(self.slot_count, rec_offset, data_len)
        self.slot_count += 1
        self.free_space -= data_len + SLOT_SIZE
        self._write_header()
        return self.slot_count - 1

    def get_record(self, slot_id: int) -> bytes:
        """Return the record bytes for *slot_id*.

        Returns b'' for a deleted (tombstoned) record.
        Raises IndexError for an invalid slot_id.
        """
        if slot_id < 0 or slot_id >= self.slot_count:
            raise IndexError(
                f"page {self.page_id}: slot {slot_id} out of range "
                f"[0, {self.slot_count})"
            )
        offset, length = self._read_slot(slot_id)
        return bytes(self.buf[offset:offset + length])

    def delete_record(self, slot_id: int) -> None:
        """Mark a record as deleted (tombstone). Does not move other records."""
        if slot_id < 0 or slot_id >= self.slot_count:
            raise IndexError(
                f"page {self.page_id}: slot {slot_id} out of range "
                f"[0, {self.slot_count})"
            )
        offset, _length = self._read_slot(slot_id)
        self._write_slot(slot_id, offset, 0)

    # ------------------------------------------------------------------
    # Serialization
    # ------------------------------------------------------------------

    def to_bytes(self) -> bytes:
        """Serialize the page to exactly 4096 bytes."""
        self._write_header()
        return bytes(self.buf)

    @classmethod
    def from_bytes(cls, data: bytes):
        """Deserialize a page from bytes.

        An all-zero buffer means the page was never written, so a fresh
        empty page is returned (page_id 0, full free space).
        """
        buf = bytearray(data[:PAGE_SIZE])
        if len(buf) < PAGE_SIZE:
            buf.extend(b"\x00" * (PAGE_SIZE - len(buf)))
        page = cls.__new__(cls)
        page.buf = buf
        # Never-written pages come back as all-zero bytes.
        if not any(buf):
            page.page_id = 0
            page.slot_count = 0
            page.free_space = PAGE_SIZE - HEADER_SIZE
            page.flags = TABLE_DATA
            page._write_header()
        else:
            page._read_header()
        return page


# =========================================================================
# Record serialization
# =========================================================================


def serialize_record(columns: list, values: list) -> bytes:
    """Serialize column definitions and values into record bytes.

    Format: null_bitmap | column_sizes | column_values
        - null_bitmap:  1 bit per column (1 = NULL), MSB-first, padded to bytes
        - column_sizes: uint16 per column giving the byte length of the value
        - column_values: serialized value bytes concatenated (empty for NULL)
    """
    n = len(columns)
    num_bitmap_bytes = (n + 7) // 8

    # null bitmap
    bitmap = bytearray(num_bitmap_bytes)
    for i, val in enumerate(values):
        if val is None:
            bitmap[i // 8] |= 1 << (7 - i % 8)

    # serialize each value, record sizes
    sizes = []
    value_parts = []
    for col, val in zip(columns, values):
        part = serialize_value(val, col.data_type)
        sizes.append(len(part))
        value_parts.append(part)

    column_sizes = b"".join(struct.pack(">H", s) for s in sizes)
    column_values = b"".join(value_parts)

    return bytes(bitmap) + column_sizes + column_values


def deserialize_record(columns: list, data: bytes) -> list:
    """Deserialize record bytes (see :func:`serialize_record`) into a value list."""
    n = len(columns)
    num_bitmap_bytes = (n + 7) // 8

    bitmap = data[:num_bitmap_bytes]

    # read column sizes
    sizes = []
    pos = num_bitmap_bytes
    for _ in range(n):
        sizes.append(struct.unpack_from(">H", data, pos)[0])
        pos += 2

    # read values
    values = []
    for i, col in enumerate(columns):
        if bitmap[i // 8] & (1 << (7 - i % 8)):
            values.append(None)
        else:
            sz = sizes[i]
            val_data = data[pos:pos + sz]
            values.append(deserialize_value(val_data, col.data_type))
            pos += sz

    return values
