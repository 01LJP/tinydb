"""Tests for tinydb type system: serialization, deserialization, type checking, and exceptions."""

import pytest
import struct

from tinydb.types import (
    DataType,
    ColumnDef,
    serialize_value,
    deserialize_value,
    TinydbError,
    ParseError,
    TypeMismatchError,
    ConstraintError,
    TableNotFoundError,
    ColumnNotFoundError,
    TransactionError,
    StorageError,
    check_value_type,
)


# =========================================================================
# Serialization round-trip tests
# =========================================================================

class TestSerializeDeserializeRoundTrip:
    """Verify serialize -> deserialize returns the original value."""

    def test_int_round_trip(self):
        original = 42
        data = serialize_value(original, DataType.INT)
        assert deserialize_value(data, DataType.INT) == original

    def test_negative_int_round_trip(self):
        original = -999
        data = serialize_value(original, DataType.INT)
        assert deserialize_value(data, DataType.INT) == original

    def test_zero_int_round_trip(self):
        original = 0
        data = serialize_value(original, DataType.INT)
        assert deserialize_value(data, DataType.INT) == original

    def test_max_int_round_trip(self):
        original = 2**31 - 1
        data = serialize_value(original, DataType.INT)
        assert deserialize_value(data, DataType.INT) == original

    def test_min_int_round_trip(self):
        original = -(2**31)
        data = serialize_value(original, DataType.INT)
        assert deserialize_value(data, DataType.INT) == original

    def test_float_round_trip(self):
        original = 3.14159
        data = serialize_value(original, DataType.FLOAT)
        assert deserialize_value(data, DataType.FLOAT) == pytest.approx(original)

    def test_negative_float_round_trip(self):
        original = -2.71828
        data = serialize_value(original, DataType.FLOAT)
        assert deserialize_value(data, DataType.FLOAT) == pytest.approx(original)

    def test_zero_float_round_trip(self):
        original = 0.0
        data = serialize_value(original, DataType.FLOAT)
        assert deserialize_value(data, DataType.FLOAT) == pytest.approx(original)

    def test_text_round_trip(self):
        original = "Hello, TinyDB!"
        data = serialize_value(original, DataType.TEXT)
        assert deserialize_value(data, DataType.TEXT) == original

    def test_empty_text_serializes_to_empty_bytes(self):
        """Empty text serializes to b'', which deserializes to None.

        This is a known trade-off: the simple serialization format uses
        empty bytes to represent NULL, so empty string loses distinction.
        """
        original = ""
        data = serialize_value(original, DataType.TEXT)
        assert data == b''
        # Empty bytes maps to NULL (None) on deserialization
        assert deserialize_value(data, DataType.TEXT) is None

    def test_unicode_text_round_trip(self):
        original = "你好世界 🌍 café"
        data = serialize_value(original, DataType.TEXT)
        assert deserialize_value(data, DataType.TEXT) == original

    def test_bool_true_round_trip(self):
        original = True
        data = serialize_value(original, DataType.BOOL)
        assert deserialize_value(data, DataType.BOOL) == original

    def test_bool_false_round_trip(self):
        original = False
        data = serialize_value(original, DataType.BOOL)
        assert deserialize_value(data, DataType.BOOL) == original

    def test_none_round_trip(self):
        """None serializes to empty bytes and deserializes back to None."""
        for dtype in DataType:
            data = serialize_value(None, dtype)
            assert data == b''
            assert deserialize_value(data, dtype) is None


# =========================================================================
# Serialization format tests
# =========================================================================

class TestSerializationFormat:
    """Verify the binary format of serialized values."""

    def test_int_is_4_bytes_big_endian(self):
        data = serialize_value(1, DataType.INT)
        assert len(data) == 4
        assert data == struct.pack('>i', 1)

    def test_float_is_8_bytes_big_endian(self):
        data = serialize_value(1.0, DataType.FLOAT)
        assert len(data) == 8
        assert data == struct.pack('>d', 1.0)

    def test_bool_true_is_single_byte(self):
        data = serialize_value(True, DataType.BOOL)
        assert data == b'\x01'

    def test_bool_false_is_single_byte(self):
        data = serialize_value(False, DataType.BOOL)
        assert data == b'\x00'

    def test_text_is_utf8_bytes(self):
        data = serialize_value("abc", DataType.TEXT)
        assert data == b'abc'

    def test_none_is_empty_bytes(self):
        for dtype in DataType:
            assert serialize_value(None, dtype) == b''


# =========================================================================
# Type checking tests
# =========================================================================

class TestCheckValueType:
    """Verify check_value_type correctly validates Python values against DataType."""

    @pytest.mark.parametrize("value,expected", [
        (0, True),
        (42, True),
        (-100, True),
        (2**31 - 1, True),
    ])
    def test_int_accepts_integers(self, value, expected):
        assert check_value_type(value, DataType.INT) is expected

    @pytest.mark.parametrize("value", [True, False, 3.14, "123", None])
    def test_int_rejects_non_integers(self, value):
        # None is always accepted (represents NULL)
        if value is None:
            assert check_value_type(value, DataType.INT) is True
        else:
            assert check_value_type(value, DataType.INT) is False

    @pytest.mark.parametrize("value,expected", [
        (0.0, True),
        (3.14, True),
        (-1.5, True),
        (1, True),  # int is acceptable as float
    ])
    def test_float_accepts_numbers(self, value, expected):
        assert check_value_type(value, DataType.FLOAT) is expected

    @pytest.mark.parametrize("value", [True, False, "3.14", None])
    def test_float_rejects_non_numbers(self, value):
        if value is None:
            assert check_value_type(value, DataType.FLOAT) is True
        else:
            assert check_value_type(value, DataType.FLOAT) is False

    @pytest.mark.parametrize("value,expected", [
        ("", True),
        ("hello", True),
        ("123", True),
    ])
    def test_text_accepts_strings(self, value, expected):
        assert check_value_type(value, DataType.TEXT) is expected

    @pytest.mark.parametrize("value", [123, 3.14, True, None])
    def test_text_rejects_non_strings(self, value):
        if value is None:
            assert check_value_type(value, DataType.TEXT) is True
        else:
            assert check_value_type(value, DataType.TEXT) is False

    @pytest.mark.parametrize("value,expected", [
        (True, True),
        (False, True),
    ])
    def test_bool_accepts_booleans(self, value, expected):
        assert check_value_type(value, DataType.BOOL) is expected

    @pytest.mark.parametrize("value", [1, 0, "true", "false", None])
    def test_bool_rejects_non_booleans(self, value):
        if value is None:
            assert check_value_type(value, DataType.BOOL) is True
        else:
            assert check_value_type(value, DataType.BOOL) is False

    def test_none_is_accepted_by_all_types(self):
        """None (NULL) should be accepted by every type."""
        for dtype in DataType:
            assert check_value_type(None, dtype) is True


# =========================================================================
# DataType enum tests
# =========================================================================

class TestDataType:
    """Verify DataType enum values."""

    def test_enum_values(self):
        assert DataType.INT.value == "INT"
        assert DataType.FLOAT.value == "FLOAT"
        assert DataType.TEXT.value == "TEXT"
        assert DataType.BOOL.value == "BOOL"

    def test_enum_members(self):
        assert len(DataType) == 4


# =========================================================================
# ColumnDef tests
# =========================================================================

class TestColumnDef:
    """Verify ColumnDef construction and defaults."""

    def test_basic_column(self):
        col = ColumnDef("id", DataType.INT)
        assert col.name == "id"
        assert col.data_type == DataType.INT
        assert col.nullable is True
        assert col.is_unique is False
        assert col.is_pk is False

    def test_not_null_column(self):
        col = ColumnDef("name", DataType.TEXT, nullable=False)
        assert col.nullable is False

    def test_unique_column(self):
        col = ColumnDef("email", DataType.TEXT, is_unique=True)
        assert col.is_unique is True

    def test_primary_key_column(self):
        col = ColumnDef("id", DataType.INT, is_pk=True, nullable=False)
        assert col.is_pk is True
        assert col.nullable is False


# =========================================================================
# Exception hierarchy tests
# =========================================================================

class TestExceptionHierarchy:
    """Verify exception classes and their inheritance."""

    def test_tinydb_error_is_base(self):
        assert issubclass(ParseError, TinydbError)
        assert issubclass(TypeMismatchError, TinydbError)
        assert issubclass(ConstraintError, TinydbError)
        assert issubclass(TableNotFoundError, TinydbError)
        assert issubclass(ColumnNotFoundError, TinydbError)
        assert issubclass(TransactionError, TinydbError)
        assert issubclass(StorageError, TinydbError)

    def test_tinydb_error_is_exception(self):
        assert issubclass(TinydbError, Exception)

    def test_error_without_context(self):
        err = TinydbError("something went wrong")
        assert "[TINYDBERROR]" in str(err)
        assert "something went wrong" in str(err)
        assert err.context == ""

    def test_error_with_context(self):
        err = TinydbError("bad syntax", context="lexer")
        msg = str(err)
        assert "[TINYDBERROR]" in msg
        assert "bad syntax" in msg
        assert "lexer" in msg
        assert err.context == "lexer"

    def test_parse_error_message(self):
        err = ParseError("unexpected token", context="line 1")
        assert "[PARSEERROR]" in str(err)
        assert "unexpected token" in str(err)

    def test_type_mismatch_error_message(self):
        err = TypeMismatchError("expected INT, got TEXT")
        assert "[TYPEMISMATCHERROR]" in str(err)

    def test_constraint_error_message(self):
        err = ConstraintError("duplicate key")
        assert "[CONSTRAINTERROR]" in str(err)

    def test_table_not_found_error_message(self):
        err = TableNotFoundError("no such table: users")
        assert "[TABLENOTFOUNDERROR]" in str(err)

    def test_column_not_found_error_message(self):
        err = ColumnNotFoundError("no such column: age")
        assert "[COLUMNNOTFOUNDERROR]" in str(err)

    def test_transaction_error_message(self):
        err = TransactionError("deadlock detected")
        assert "[TRANSACTIONERROR]" in str(err)

    def test_storage_error_message(self):
        err = StorageError("disk full")
        assert "[STORAGEERROR]" in str(err)

    def test_errors_are_catchable_as_tinydb_error(self):
        """All specific errors should be catchable via TinydbError."""
        for exc_class in [ParseError, TypeMismatchError, ConstraintError,
                          TableNotFoundError, ColumnNotFoundError,
                          TransactionError, StorageError]:
            try:
                raise exc_class("test")
            except TinydbError:
                pass  # expected
            else:
                pytest.fail(f"{exc_class.__name__} not caught as TinydbError")
