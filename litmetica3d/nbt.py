"""
Pure Python NBT (Named Binary Tag) reader/writer.

Supports all 12 tag types as of the NBT specification.
Big-endian (Java Edition) encoding.  Includes GZip compression wrapper.

Reference: https://wiki.vg/NBT
"""

import gzip
import io
import struct
from typing import Any, BinaryIO


# ── Tag type constants ──────────────────────────────────────────────────────

TAG_END         = 0
TAG_BYTE        = 1
TAG_SHORT       = 2
TAG_INT         = 3
TAG_LONG        = 4
TAG_FLOAT       = 5
TAG_DOUBLE      = 6
TAG_BYTE_ARRAY  = 7
TAG_STRING      = 8
TAG_LIST        = 9
TAG_COMPOUND    = 10
TAG_INT_ARRAY   = 11
TAG_LONG_ARRAY  = 12

TAG_NAMES = {
    0: "TAG_End",
    1: "TAG_Byte",
    2: "TAG_Short",
    3: "TAG_Int",
    4: "TAG_Long",
    5: "TAG_Float",
    6: "TAG_Double",
    7: "TAG_Byte_Array",
    8: "TAG_String",
    9: "TAG_List",
    10: "TAG_Compound",
    11: "TAG_Int_Array",
    12: "TAG_Long_Array",
}


# ── Low-level read helpers ──────────────────────────────────────────────────

def _read_exact(data: BinaryIO, length: int) -> bytes:
    raw = data.read(length)
    if len(raw) != length:
        raise ValueError(f"Truncated NBT payload: expected {length} bytes, got {len(raw)}")
    return raw


def _read_length(data: BinaryIO) -> int:
    length = _read_int(data)
    if length < 0:
        raise ValueError(f"Negative NBT array length: {length}")
    return length


def _read_ubyte(data: BinaryIO) -> int:
    return struct.unpack(">B", _read_exact(data, 1))[0]


def _read_byte(data: BinaryIO) -> int:
    return struct.unpack(">b", _read_exact(data, 1))[0]

def _read_short(data: io.BytesIO) -> int:
    return struct.unpack(">h", _read_exact(data, 2))[0]

def _read_int(data: io.BytesIO) -> int:
    return struct.unpack(">i", _read_exact(data, 4))[0]

def _read_long(data: io.BytesIO) -> int:
    return struct.unpack(">q", _read_exact(data, 8))[0]

def _read_float(data: io.BytesIO) -> float:
    return struct.unpack(">f", _read_exact(data, 4))[0]

def _read_double(data: io.BytesIO) -> float:
    return struct.unpack(">d", _read_exact(data, 8))[0]

def _decode_nbt_string(raw: bytes) -> str:
    """Decode standard UTF-8 and Java Modified UTF-8/CESU-8 strings."""
    try:
        return raw.decode("utf-8")
    except UnicodeDecodeError:
        # Java's modified UTF-8 represents NUL as C0 80 and supplementary
        # characters as two separately encoded UTF-16 surrogate code units.
        normalized = raw.replace(b"\xc0\x80", b"\x00")
        try:
            text = normalized.decode("utf-8", errors="surrogatepass")
        except UnicodeDecodeError:
            # Keep a damaged display string from aborting the whole schematic.
            # Structural NBT lengths remain intact because bytes were consumed
            # before decoding.
            text = normalized.decode("utf-8", errors="replace")

        result = []
        index = 0
        while index < len(text):
            code = ord(text[index])
            if 0xD800 <= code <= 0xDBFF and index + 1 < len(text):
                low = ord(text[index + 1])
                if 0xDC00 <= low <= 0xDFFF:
                    result.append(chr(
                        0x10000 + ((code - 0xD800) << 10) + (low - 0xDC00)
                    ))
                    index += 2
                    continue
            # Unpaired UTF-16 surrogates are not valid Python Unicode. Replace
            # only that character while preserving the rest of the NBT value.
            result.append("\ufffd" if 0xD800 <= code <= 0xDFFF else text[index])
            index += 1
        return "".join(result)

def _read_string(data: io.BytesIO) -> str:
    length = struct.unpack(">H", _read_exact(data, 2))[0]
    return _decode_nbt_string(_read_exact(data, length))

def _read_byte_array(data: io.BytesIO) -> bytearray:
    length = _read_length(data)
    return bytearray(_read_exact(data, length))

def _read_int_array(data: io.BytesIO) -> list[int]:
    length = _read_length(data)
    return [_read_int(data) for _ in range(length)]

def _read_long_array(data: io.BytesIO) -> list[int]:
    length = _read_length(data)
    return [_read_long(data) for _ in range(length)]


# ── Low-level write helpers ─────────────────────────────────────────────────

def _write_ubyte(buf: io.BytesIO, value: int) -> None:
    buf.write(struct.pack(">B", value))

def _write_short(buf: io.BytesIO, value: int) -> None:
    buf.write(struct.pack(">h", value))

def _write_int(buf: io.BytesIO, value: int) -> None:
    buf.write(struct.pack(">i", value))

def _write_long(buf: io.BytesIO, value: int) -> None:
    buf.write(struct.pack(">q", value))

def _write_float(buf: io.BytesIO, value: float) -> None:
    buf.write(struct.pack(">f", value))

def _write_double(buf: io.BytesIO, value: float) -> None:
    buf.write(struct.pack(">d", value))

def _write_string(buf: io.BytesIO, value: str) -> None:
    encoded = value.encode("utf-8")
    buf.write(struct.pack(">H", len(encoded)))
    buf.write(encoded)

def _write_byte_array(buf: io.BytesIO, value: bytearray | bytes) -> None:
    _write_int(buf, len(value))
    buf.write(value)

def _write_int_array(buf: io.BytesIO, value: list[int]) -> None:
    _write_int(buf, len(value))
    for v in value:
        buf.write(struct.pack(">i", v))

def _write_long_array(buf: io.BytesIO, value: list[int]) -> None:
    _write_int(buf, len(value))
    for v in value:
        buf.write(struct.pack(">q", v))


# ── Tag type detection ──────────────────────────────────────────────────────

def _tag_type_for_value(value: Any) -> int:
    """Return the NBT tag type constant for a Python value."""
    if isinstance(value, bool):
        # NBT doesn't have bool; store as byte (Minecraft convention)
        return TAG_BYTE
    if isinstance(value, int):
        return TAG_LONG
    if isinstance(value, float):
        return TAG_DOUBLE
    if isinstance(value, str):
        return TAG_STRING
    if isinstance(value, bytes | bytearray):
        return TAG_BYTE_ARRAY
    if isinstance(value, list):
        if len(value) > 0:
            if isinstance(value[0], int):
                return TAG_LONG_ARRAY
        return TAG_LIST
    if isinstance(value, dict):
        return TAG_COMPOUND
    raise TypeError(f"No NBT tag type for Python type {type(value)}: {value!r}")


# ── Reading ─────────────────────────────────────────────────────────────────

def read_nbt(data: BinaryIO, *, skip_tags: frozenset[str] = frozenset()) -> dict[str, Any]:
    """
    Read an NBT root compound from a BytesIO stream.

    The first byte is the tag type (must be TAG_Compound=10),
    followed by the root name string, then the compound payload.
    """
    tag_type = _read_ubyte(data)
    if tag_type != TAG_COMPOUND:
        raise ValueError(f"Root tag must be TAG_Compound (10), got {tag_type}")
    _root_name = _read_string(data)  # root name – we don't store it
    return _read_compound(data, skip_tags)


def _read_tag(data: BinaryIO, tag_type: int, skip_tags: frozenset[str] = frozenset()) -> Any:
    """Dispatch reader for a single tag value (no name, no type byte)."""
    if tag_type == TAG_BYTE:
        return _read_byte(data)
    elif tag_type == TAG_SHORT:
        return _read_short(data)
    elif tag_type == TAG_INT:
        return _read_int(data)
    elif tag_type == TAG_LONG:
        return _read_long(data)
    elif tag_type == TAG_FLOAT:
        return _read_float(data)
    elif tag_type == TAG_DOUBLE:
        return _read_double(data)
    elif tag_type == TAG_STRING:
        return _read_string(data)
    elif tag_type == TAG_BYTE_ARRAY:
        return _read_byte_array(data)
    elif tag_type == TAG_INT_ARRAY:
        return _read_int_array(data)
    elif tag_type == TAG_LONG_ARRAY:
        return _read_long_array(data)
    elif tag_type == TAG_LIST:
        return _read_list(data, skip_tags)
    elif tag_type == TAG_COMPOUND:
        return _read_compound(data, skip_tags)
    else:
        raise ValueError(f"Unknown NBT tag type: {tag_type}")


def _read_list(data: BinaryIO, skip_tags: frozenset[str] = frozenset()) -> list:
    """Read a TAG_List: list_type byte, length int, then length entries."""
    list_type = _read_ubyte(data)
    length = _read_int(data)
    result = []
    for _ in range(length):
        result.append(_read_tag(data, list_type, skip_tags))
    return result


def _read_compound(data: BinaryIO, skip_tags: frozenset[str] = frozenset()) -> dict[str, Any]:
    """Read a TAG_Compound: name-type pairs terminated by TAG_End."""
    result = {}
    while True:
        tag_type = _read_ubyte(data)
        if tag_type == TAG_END:
            break
        name = _read_string(data)
        if name in skip_tags:
            _skip_tag(data, tag_type)
        else:
            result[name] = _read_tag(data, tag_type, skip_tags)
    return result


def _skip_bytes(data: BinaryIO, length: int) -> None:
    """Consume an unwanted payload with bounded memory, checking truncation."""
    while length:
        count = min(length, 65536)
        _read_exact(data, count)
        length -= count


def _skip_tag(data: BinaryIO, tag_type: int) -> None:
    """Skip a payload without allocating its arrays, lists or compounds."""
    sizes = {TAG_BYTE: 1, TAG_SHORT: 2, TAG_INT: 4, TAG_LONG: 8,
             TAG_FLOAT: 4, TAG_DOUBLE: 8}
    if tag_type in sizes:
        _skip_bytes(data, sizes[tag_type])
    elif tag_type == TAG_STRING:
        _skip_bytes(data, struct.unpack(">H", _read_exact(data, 2))[0])
    elif tag_type in (TAG_BYTE_ARRAY, TAG_INT_ARRAY, TAG_LONG_ARRAY):
        width = {TAG_BYTE_ARRAY: 1, TAG_INT_ARRAY: 4, TAG_LONG_ARRAY: 8}[tag_type]
        _skip_bytes(data, _read_length(data) * width)
    elif tag_type == TAG_LIST:
        subtype = _read_ubyte(data)
        length = _read_int(data)
        if length <= 0:
            return
        if subtype in sizes:
            _skip_bytes(data, sizes[subtype] * length)
        else:
            for _ in range(length):
                _skip_tag(data, subtype)
    elif tag_type == TAG_COMPOUND:
        while True:
            subtype = _read_ubyte(data)
            if subtype == TAG_END:
                break
            _skip_tag(data, TAG_STRING)  # tag name
            _skip_tag(data, subtype)
    else:
        raise ValueError(f"Unknown NBT tag type: {tag_type}")


# ── Writing ─────────────────────────────────────────────────────────────────

def write_nbt(data: dict[str, Any]) -> bytes:
    """Encode a dictionary as a GZip-compressed NBT compound."""
    buf = io.BytesIO()
    _write_compound_full(buf, data, name="")
    return buf.getvalue()


def write_nbt_uncompressed(data: dict[str, Any], root_name: str = "") -> bytes:
    """Encode a dictionary as uncompressed NBT (useful for debugging)."""
    buf = io.BytesIO()
    _write_compound_full(buf, data, name=root_name)
    return buf.getvalue()


def _write_compound_full(buf: io.BytesIO, data: dict[str, Any], name: str = "") -> None:
    """Write a full named compound (type byte + name + payload + TAG_End)."""
    _write_ubyte(buf, TAG_COMPOUND)
    _write_string(buf, name)
    _write_compound_payload(buf, data)


def _write_compound_payload(buf: io.BytesIO, data: dict[str, Any]) -> None:
    """Write compound entries + TAG_End."""
    for key, value in data.items():
        tag_type = _tag_type_for_value(value)
        _write_ubyte(buf, tag_type)
        _write_string(buf, key)
        _write_tag_value(buf, value, tag_type)
    _write_ubyte(buf, TAG_END)


def _write_tag_value(buf: io.BytesIO, value: Any, tag_type: int) -> None:
    """Write a single tag value (already dispatched by type)."""
    if tag_type == TAG_BYTE:
        buf.write(struct.pack(">b", int(value)))
    elif tag_type == TAG_SHORT:
        _write_short(buf, value)
    elif tag_type == TAG_INT:
        _write_int(buf, value)
    elif tag_type == TAG_LONG:
        _write_long(buf, value)
    elif tag_type == TAG_FLOAT:
        _write_float(buf, value)
    elif tag_type == TAG_DOUBLE:
        _write_double(buf, value)
    elif tag_type == TAG_STRING:
        _write_string(buf, value)
    elif tag_type == TAG_BYTE_ARRAY:
        _write_byte_array(buf, value)
    elif tag_type == TAG_INT_ARRAY:
        _write_int_array(buf, value)
    elif tag_type == TAG_LONG_ARRAY:
        _write_long_array(buf, value)
    elif tag_type == TAG_LIST:
        _write_list_value(buf, value)
    elif tag_type == TAG_COMPOUND:
        _write_compound_payload(buf, value)
    else:
        raise ValueError(f"Unknown NBT tag type: {tag_type}")


def _write_list_value(buf: io.BytesIO, value: list) -> None:
    """Write a TAG_List with auto-detected element type."""
    if len(value) == 0:
        _write_ubyte(buf, TAG_END)
        _write_int(buf, 0)
        return
    elem_type = _tag_type_for_value(value[0])
    # Verify all elements have the same type
    for item in value[1:]:
        if _tag_type_for_value(item) != elem_type:
            raise TypeError("All list elements must have the same NBT tag type")
    _write_ubyte(buf, elem_type)
    _write_int(buf, len(value))
    for item in value:
        _write_tag_value(buf, item, elem_type)


# ── GZip helpers ────────────────────────────────────────────────────────────

def read_gzip_nbt(path: str, *, skip_tags: frozenset[str] = frozenset()) -> dict[str, Any]:
    """Read a GZip-compressed NBT file and return the root compound dict."""
    with gzip.open(path, "rb") as f:
        return read_nbt(f, skip_tags=skip_tags)


def read_raw_nbt(path: str) -> dict[str, Any]:
    """Read an uncompressed NBT file and return the root compound dict."""
    with open(path, "rb") as f:
        return read_nbt(f)


def write_gzip_nbt(path: str, data: dict[str, Any]) -> None:
    """Write a dictionary as a GZip-compressed NBT file."""
    raw = write_nbt(data)
    with gzip.open(path, "wb") as f:
        f.write(raw)


def write_raw_nbt(path: str, data: dict[str, Any], root_name: str = "") -> None:
    """Write a dictionary as an uncompressed NBT file."""
    raw = write_nbt_uncompressed(data, root_name)
    with open(path, "wb") as f:
        f.write(raw)
