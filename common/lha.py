"""Minimal pure-Python LHA reader (header levels 0-2, methods -lh0-, -lh4-..-lh7-, -lhd-)."""
import struct
from dataclasses import dataclass
from pathlib import PurePosixPath

NC = 510          # literal/length alphabet size
NT = 19           # code-length alphabet size
THRESHOLD = 3
DICBITS = {"-lh4-": 12, "-lh5-": 13, "-lh6-": 15, "-lh7-": 16}


class LhaError(Exception):
    pass


_CRC_TABLE = []
for _i in range(256):
    _c = _i
    for _ in range(8):
        _c = (_c >> 1) ^ 0xA001 if _c & 1 else _c >> 1
    _CRC_TABLE.append(_c)


def _crc16(data: bytes) -> int:
    crc = 0
    for b in data:
        crc = (crc >> 8) ^ _CRC_TABLE[(crc ^ b) & 0xFF]
    return crc


@dataclass
class Entry:
    path: str
    method: str
    packed_size: int
    size: int
    crc: int
    data_offset: int

    @property
    def is_dir(self) -> bool:
        return self.method == "-lhd-"


class _Bits:
    def __init__(self, data: bytes):
        self.data = data
        self.pos = 0  # bit position

    def get(self, n: int) -> int:
        if n == 0:
            return 0
        end = self.pos + n
        if end > len(self.data) * 8 + 32:
            raise LhaError("unexpected end of compressed data")
        first, last = self.pos >> 3, (end + 7) >> 3
        chunk = int.from_bytes(self.data[first:last].ljust(last - first, b"\0"), "big")
        chunk >>= (last << 3) - end
        self.pos = end
        return chunk & ((1 << n) - 1)

    def bit(self) -> int:
        p = self.pos
        self.pos = p + 1
        i = p >> 3
        return (self.data[i] >> (7 - (p & 7))) & 1 if i < len(self.data) else 0


class _Huffman:
    """Canonical Huffman decoder built from code lengths (ar002 code assignment)."""

    def __init__(self, lengths, const_symbol=None):
        self.const = const_symbol
        if const_symbol is not None:
            return
        maxlen = max(lengths) if lengths else 0
        count = [0] * (maxlen + 2)
        for l in lengths:
            if l:
                count[l] += 1
        self.first = [0] * (maxlen + 2)   # first code of each length
        self.offset = [0] * (maxlen + 2)  # index into sorted symbols
        self.count = count
        self.maxlen = maxlen
        code = idx = 0
        for l in range(1, maxlen + 1):
            self.first[l] = code
            self.offset[l] = idx
            code = (code + count[l]) << 1
            idx += count[l]
        self.symbols = [s for l in range(1, maxlen + 1) for s, sl in enumerate(lengths) if sl == l]

    def decode(self, bits: _Bits) -> int:
        if self.const is not None:
            return self.const
        code = 0
        for l in range(1, self.maxlen + 1):
            code = (code << 1) | bits.bit()
            delta = code - self.first[l]
            if 0 <= delta < self.count[l]:
                return self.symbols[self.offset[l] + delta]
        raise LhaError("invalid Huffman code")


def _read_pt(bits: _Bits, nn: int, nbit: int, special: int) -> _Huffman:
    n = bits.get(nbit)
    if n == 0:
        return _Huffman(None, const_symbol=bits.get(nbit))
    lens = [0] * nn
    i = 0
    while i < n:
        c = bits.get(3)
        if c == 7:
            while bits.bit():
                c += 1
        lens[i] = c
        i += 1
        if i == special:
            i += bits.get(2)
    return _Huffman(lens)


def _read_c(bits: _Bits, pt: _Huffman) -> _Huffman:
    n = bits.get(9)
    if n == 0:
        return _Huffman(None, const_symbol=bits.get(9))
    lens = [0] * NC
    i = 0
    while i < n:
        c = pt.decode(bits)
        if c <= 2:
            if c == 0:
                c = 1
            elif c == 1:
                c = bits.get(4) + 3
            else:
                c = bits.get(9) + 20
            i += c
        else:
            lens[i] = c - 2
            i += 1
    return _Huffman(lens)


def _decompress(data: bytes, size: int, dicbits: int) -> bytes:
    np_ = dicbits + 1
    pbit = 5 if dicbits > 13 else 4
    bits = _Bits(data)
    out = bytearray()
    blocksize = 0
    c_tree = p_tree = None
    while len(out) < size:
        if blocksize == 0:
            blocksize = bits.get(16)
            t_tree = _read_pt(bits, NT, 5, 3)
            c_tree = _read_c(bits, t_tree)
            p_tree = _read_pt(bits, np_, pbit, -1)
        blocksize -= 1
        sym = c_tree.decode(bits)
        if sym < 256:
            out.append(sym)
            continue
        length = sym - 256 + THRESHOLD
        j = p_tree.decode(bits)
        dist = ((1 << (j - 1)) + bits.get(j - 1)) if j else 0
        src = len(out) - dist - 1
        if src < 0:
            raise LhaError("invalid back-reference")
        for k in range(length):
            out.append(out[src + k])
    return bytes(out[:size])


def _clean_path(name: str) -> str:
    name = name.split("\0", 1)[0]  # Amiga archivers append the file comment after a NUL
    parts = [p for p in name.replace("\\", "/").split("/") if p not in ("", ".", "..")]
    return "/".join(parts)


def read_entries(data: bytes):
    pos, entries = 0, []
    while pos < len(data) and data[pos] != 0:
        hsize = data[pos]
        method = data[pos + 2:pos + 7].decode("latin-1")
        packed, size = struct.unpack_from("<II", data, pos + 7)
        level = data[pos + 20]
        if level in (0, 1):
            nlen = data[pos + 21]
            name = data[pos + 22:pos + 22 + nlen].decode("latin-1")
            crc = struct.unpack_from("<H", data, pos + 22 + nlen)[0]
            data_start = pos + hsize + 2
            dirname = ""
            if level == 1:
                p = pos + 22 + nlen + 3          # crc(2) + os(1)
                nxt = struct.unpack_from("<H", data, p)[0]
                p += 2
                while nxt:
                    ext = data[p:p + nxt]
                    if ext[0] == 0x01:
                        name = ext[1:nxt - 2].decode("latin-1")
                    elif ext[0] == 0x02:
                        dirname = ext[1:nxt - 2].decode("latin-1").replace("\xff", "/")
                    packed -= nxt
                    p += nxt
                    nxt = struct.unpack_from("<H", data, p - 2)[0]
                data_start = p
            if dirname:
                name = dirname.rstrip("/") + "/" + name
        elif level == 2:
            hsize = struct.unpack_from("<H", data, pos)[0]
            crc = struct.unpack_from("<H", data, pos + 21)[0]
            name, dirname = "", ""
            p = pos + 24
            nxt = struct.unpack_from("<H", data, p - 2)[0]
            while nxt:
                ext = data[p:p + nxt]
                if ext[0] == 0x01:
                    name = ext[1:nxt - 2].decode("latin-1")
                elif ext[0] == 0x02:
                    dirname = ext[1:nxt - 2].decode("latin-1").replace("\xff", "/")
                p += nxt
                nxt = struct.unpack_from("<H", data, p - 2)[0]
            name = (dirname.rstrip("/") + "/" + name) if dirname else name
            data_start = pos + hsize
        else:
            raise LhaError(f"unsupported header level {level}")
        entries.append(Entry(_clean_path(name), method, packed, size, crc, data_start))
        pos = data_start + packed
    return entries


def iter_files(archive_path):
    """Yield (path, content) for every entry in the archive; content is None for directories."""
    from pathlib import Path
    data = Path(archive_path).read_bytes()
    for e in read_entries(data):
        if not e.path:
            continue
        if e.is_dir:
            yield e.path, None
            continue
        raw = data[e.data_offset:e.data_offset + e.packed_size]
        if e.method == "-lh0-":
            content = raw
        elif e.method in DICBITS:
            content = _decompress(raw, e.size, DICBITS[e.method])
        else:
            raise LhaError(f"unsupported method {e.method} for {e.path}")
        if _crc16(content) != e.crc:
            raise LhaError(f"CRC mismatch for {e.path}")
        yield e.path, content


def extract(archive_path, dest) -> list[str]:
    """Extract every file in the archive under `dest`; returns the relative paths written."""
    from pathlib import Path
    dest = Path(dest)
    written = []
    for path, content in iter_files(archive_path):
        target = dest / PurePosixPath(path)
        if content is None:
            target.mkdir(parents=True, exist_ok=True)
            continue
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(content)
        written.append(path)
    return written
