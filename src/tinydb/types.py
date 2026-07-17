from enum import Enum
from typing import Any


class DataType(Enum):
    INT = "INT"
    FLOAT = "FLOAT"
    TEXT = "TEXT"
    BOOL = "BOOL"


class ColumnDef:
    def __init__(self, name: str, data_type: DataType,
                 nullable: bool = True, is_unique: bool = False, is_pk: bool = False):
        self.name = name
        self.data_type = data_type
        self.nullable = nullable
        self.is_unique = is_unique
        self.is_pk = is_pk


def serialize_value(value: Any, data_type: DataType) -> bytes:
    """将 Python 值序列化为字节"""
    import struct
    if value is None:
        return b''
    if data_type == DataType.INT:
        return struct.pack('>i', int(value))
    elif data_type == DataType.FLOAT:
        return struct.pack('>d', float(value))
    elif data_type == DataType.TEXT:
        return value.encode('utf-8')
    elif data_type == DataType.BOOL:
        return b'\x01' if value else b'\x00'
    raise ValueError(f"Unknown type: {data_type}")


def deserialize_value(data: bytes, data_type: DataType) -> Any:
    """将字节反序列化为 Python 值"""
    import struct
    if not data:
        return None
    if data_type == DataType.INT:
        return struct.unpack('>i', data)[0]
    elif data_type == DataType.FLOAT:
        return struct.unpack('>d', data)[0]
    elif data_type == DataType.TEXT:
        return data.decode('utf-8')
    elif data_type == DataType.BOOL:
        return data[0] != 0
    raise ValueError(f"Unknown type: {data_type}")


# =========================================================================
# 异常类
# =========================================================================

class TinydbError(Exception):
    """tinydb 基础异常"""
    def __init__(self, message: str, context: str = ""):
        self.context = context
        if context:
            super().__init__(f"[{self.__class__.__name__.upper()}] {message} (context: {context})")
        else:
            super().__init__(f"[{self.__class__.__name__.upper()}] {message}")


class ParseError(TinydbError):
    pass


class TypeMismatchError(TinydbError):
    pass


class ConstraintError(TinydbError):
    pass


class TableNotFoundError(TinydbError):
    pass


class ColumnNotFoundError(TinydbError):
    pass


class TransactionError(TinydbError):
    pass


class StorageError(TinydbError):
    pass


class JoinError(TinydbError):
    pass


def check_value_type(value: Any, data_type: DataType) -> bool:
    """检查值是否符合数据类型"""
    if value is None:
        return True
    if data_type == DataType.INT:
        return isinstance(value, int) and not isinstance(value, bool)
    elif data_type == DataType.FLOAT:
        return isinstance(value, (int, float)) and not isinstance(value, bool)
    elif data_type == DataType.TEXT:
        return isinstance(value, str)
    elif data_type == DataType.BOOL:
        return isinstance(value, bool)
    return False
