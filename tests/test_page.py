"""Tests for tinydb storage page: Page data structure and Record serialization."""

import struct
import pytest

from tinydb.storage.page import Page, serialize_record, deserialize_record
from tinydb.types import DataType, ColumnDef


# =========================================================================
# Page constants & creation tests
# =========================================================================

class TestPageCreation:
    """Verify Page initializes with correct header and layout."""

    def test_page_size_constant(self):
        assert Page.PAGE_SIZE == 4096

    def test_header_size_constant(self):
        assert Page.HEADER_SIZE == 12

    def test_page_type_constants(self):
        assert Page.TABLE_DATA == 1
        assert Page.INDEX_DATA == 2
        assert Page.CATALOG == 3

    def test_default_page_is_table_data(self):
        p = Page(page_id=0)
        assert p.flags == Page.TABLE_DATA

    def test_custom_flags(self):
        p = Page(page_id=1, flags=Page.CATALOG)
        assert p.flags == Page.CATALOG

    def test_initial_slot_count_is_zero(self):
        p = Page(page_id=0)
        assert p.slot_count == 0

    def test_initial_free_space(self):
        """Free space = page size minus header (no slots, no records)."""
        p = Page(page_id=0)
        assert p.free_space == Page.PAGE_SIZE - Page.HEADER_SIZE

    def test_page_id_stored(self):
        p = Page(page_id=42)
        assert p.page_id == 42


# =========================================================================
# Insert / Get / Delete tests
# =========================================================================

class TestInsertGetDelete:
    """Verify record insertion, retrieval and deletion."""

    def test_insert_returns_slot_id(self):
        p = Page(page_id=0)
        slot = p.insert_record(b'hello')
        assert slot == 0

    def test_insert_multiple_returns_incrementing_slot_ids(self):
        p = Page(page_id=0)
        s0 = p.insert_record(b'first')
        s1 = p.insert_record(b'second')
        assert s0 == 0
        assert s1 == 1

    def test_get_record_returns_inserted_data(self):
        p = Page(page_id=0)
        p.insert_record(b'hello world')
        assert p.get_record(0) == b'hello world'

    def test_get_record_multiple(self):
        p = Page(page_id=0)
        p.insert_record(b'alpha')
        p.insert_record(b'beta')
        assert p.get_record(0) == b'alpha'
        assert p.get_record(1) == b'beta'

    def test_slot_count_increments(self):
        p = Page(page_id=0)
        p.insert_record(b'a')
        p.insert_record(b'b')
        assert p.slot_count == 2

    def test_delete_record_marks_zero_length(self):
        """After delete, the slot's length becomes 0 (tombstone)."""
        p = Page(page_id=0)
        p.insert_record(b'delete-me')
        p.delete_record(0)
        # record data is tombstoned: slot length == 0
        assert p.get_record(0) == b''

    def test_delete_does_not_affect_other_records(self):
        p = Page(page_id=0)
        p.insert_record(b'keep')
        p.insert_record(b'remove')
        p.delete_record(1)
        assert p.get_record(0) == b'keep'
        assert p.get_record(1) == b''

    def test_get_invalid_slot_raises(self):
        p = Page(page_id=0)
        with pytest.raises(IndexError):
            p.get_record(0)

    def test_insert_empty_bytes(self):
        p = Page(page_id=0)
        slot = p.insert_record(b'')
        assert slot == 0
        assert p.get_record(0) == b''


# =========================================================================
# Free space management tests
# =========================================================================

class TestFreeSpace:
    """Verify has_space and space accounting."""

    def test_has_space_true_when_empty(self):
        p = Page(page_id=0)
        assert p.has_space(100) is True

    def test_has_space_false_when_too_large(self):
        p = Page(page_id=0)
        # larger than entire page
        assert p.has_space(Page.PAGE_SIZE + 1) is False

    def test_has_space_accounts_for_slot_overhead(self):
        """Each insert needs data_len + 4 bytes (record + slot entry)."""
        p = Page(page_id=0)
        # free_space initial
        free = p.free_space
        # exactly fits: data + 4 (one slot)
        assert p.has_space(free - 4) is True
        assert p.has_space(free - 3) is False

    def test_free_space_decreases_after_insert(self):
        p = Page(page_id=0)
        before = p.free_space
        p.insert_record(b'12345')  # 5 bytes data + 4 bytes slot
        after = p.free_space
        assert after == before - 5 - 4

    def test_page_fills_up(self):
        p = Page(page_id=0)
        slot_ids = []
        # insert small records until full
        while p.has_space(10):
            sid = p.insert_record(b'0123456789')  # 10 bytes + 4 slot
            slot_ids.append(sid)
        assert len(slot_ids) > 0
        assert p.has_space(10) is False


# =========================================================================
# Serialization round-trip tests
# =========================================================================

class TestPageSerialization:
    """Verify to_bytes / from_bytes preserve page contents."""

    def test_to_bytes_returns_4096_bytes(self):
        p = Page(page_id=0)
        data = p.to_bytes()
        assert len(data) == 4096

    def test_to_bytes_header_encoded(self):
        p = Page(page_id=7, flags=Page.INDEX_DATA)
        data = p.to_bytes()
        page_id, slot_count, free_space, flags = struct.unpack_from('>IHHI', data, 0)
        assert page_id == 7
        assert flags == Page.INDEX_DATA
        assert slot_count == 0

    def test_from_bytes_round_trip_empty(self):
        p = Page(page_id=3, flags=Page.CATALOG)
        data = p.to_bytes()
        p2 = Page.from_bytes(data)
        assert p2.page_id == 3
        assert p2.flags == Page.CATALOG
        assert p2.slot_count == 0
        assert p2.free_space == p.free_space

    def test_from_bytes_round_trip_with_records(self):
        p = Page(page_id=1)
        p.insert_record(b'record-A')
        p.insert_record(b'record-B')
        data = p.to_bytes()
        p2 = Page.from_bytes(data)
        assert p2.slot_count == 2
        assert p2.get_record(0) == b'record-A'
        assert p2.get_record(1) == b'record-B'

    def test_from_bytes_preserves_delete(self):
        p = Page(page_id=1)
        p.insert_record(b'alive')
        p.insert_record(b'gone')
        p.delete_record(1)
        p2 = Page.from_bytes(p.to_bytes())
        assert p2.get_record(0) == b'alive'
        assert p2.get_record(1) == b''

    def test_from_bytes_can_still_insert(self):
        """After deserialization, the page must remain writable."""
        p = Page(page_id=1)
        p.insert_record(b'x' * 100)
        p2 = Page.from_bytes(p.to_bytes())
        assert p2.has_space(100)
        sid = p2.insert_record(b'new')
        assert p2.get_record(sid) == b'new'


# =========================================================================
# Record serialization tests (serialize_record / deserialize_record)
# =========================================================================

class TestRecordSerialization:
    """Verify column-aware record serialization."""

    def test_round_trip_simple(self):
        columns = [
            ColumnDef("id", DataType.INT),
            ColumnDef("name", DataType.TEXT),
        ]
        values = [1, "Alice"]
        data = serialize_record(columns, values)
        result = deserialize_record(columns, data)
        assert result == [1, "Alice"]

    def test_round_trip_all_types(self):
        columns = [
            ColumnDef("i", DataType.INT),
            ColumnDef("f", DataType.FLOAT),
            ColumnDef("t", DataType.TEXT),
            ColumnDef("b", DataType.BOOL),
        ]
        values = [42, 3.14, "hello", True]
        data = serialize_record(columns, values)
        result = deserialize_record(columns, data)
        assert result[0] == 42
        assert result[1] == pytest.approx(3.14)
        assert result[2] == "hello"
        assert result[3] is True

    def test_round_trip_with_nulls(self):
        columns = [
            ColumnDef("a", DataType.INT),
            ColumnDef("b", DataType.TEXT),
            ColumnDef("c", DataType.BOOL),
        ]
        values = [None, "x", None]
        data = serialize_record(columns, values)
        result = deserialize_record(columns, data)
        assert result == [None, "x", None]

    def test_round_trip_all_nulls(self):
        columns = [
            ColumnDef("a", DataType.INT),
            ColumnDef("b", DataType.TEXT),
        ]
        values = [None, None]
        data = serialize_record(columns, values)
        result = deserialize_record(columns, data)
        assert result == [None, None]

    def test_round_trip_empty_text(self):
        """Empty text serializes to empty bytes, deserializes as None."""
        columns = [ColumnDef("t", DataType.TEXT)]
        data = serialize_record(columns, [""])
        result = deserialize_record(columns, data)
        assert result == [None]

    def test_null_bitmap_format(self):
        """First byte of serialized data is the null bitmap."""
        columns = [
            ColumnDef("a", DataType.INT),
            ColumnDef("b", DataType.INT),
        ]
        # a=NULL, b=not null -> bitmap byte should have bit 0 set
        data = serialize_record(columns, [None, 5])
        bitmap_byte = data[0]
        assert bitmap_byte == 0b10000000
        result = deserialize_record(columns, data)
        assert result == [None, 5]

    def test_column_sizes_present(self):
        """Verify the column_sizes region is big-endian uint16 per column."""
        columns = [
            ColumnDef("id", DataType.INT),
            ColumnDef("name", DataType.TEXT),
        ]
        values = [7, "Bob"]
        data = serialize_record(columns, values)
        # null bitmap: 1 byte (2 cols -> 1 byte)
        # column_sizes: 2 bytes each = 4 bytes
        # INT 7 -> 4 bytes, TEXT 'Bob' -> 3 bytes
        ns = 1  # null bitmap bytes for 2 cols
        sizes_offset = ns
        off = sizes_offset
        id_size = struct.unpack_from('>H', data, off)[0]
        name_size = struct.unpack_from('>H', data, off + 2)[0]
        assert id_size == 4
        assert name_size == 3
