"""VPK structures and read-only checksum verification, adapted from the local vpk-entry-remover helper."""
from __future__ import annotations
import os,struct,zlib,hashlib
from pathlib import Path
VPK_SIGNATURE=0x55aa1234
EMBEDDED_ARCHIVE_INDEX=0x7fff
COPY_CHUNK=8<<20

class VpkError(Exception):
    """Raised for anything that means 'do not touch this archive'."""

class Header:
    __slots__ = (
        "version",
        "tree_size",
        "file_data_size",
        "archive_md5_size",
        "other_md5_size",
        "signature_size",
        "header_size",
        "file_size",
    )

    def __init__(self, version, tree_size, file_data_size, archive_md5_size,
                 other_md5_size, signature_size, header_size, file_size):
        self.version = version
        self.tree_size = tree_size
        self.file_data_size = file_data_size
        self.archive_md5_size = archive_md5_size
        self.other_md5_size = other_md5_size
        self.signature_size = signature_size
        self.header_size = header_size
        self.file_size = file_size

    @property
    def data_start(self) -> int:
        return self.header_size + self.tree_size

    @property
    def archive_md5_start(self) -> int:
        return self.data_start + self.file_data_size

    @property
    def other_md5_start(self) -> int:
        return self.archive_md5_start + self.archive_md5_size

    @property
    def signature_start(self) -> int:
        return self.other_md5_start + self.other_md5_size

    @property
    def declared_size(self) -> int:
        return self.signature_start + self.signature_size

    @property
    def trailer_size(self) -> int:
        """Bytes from the signature section to EOF.

        Some Valve-packed archives (e.g. Deadlock's own pak01_dir.vpk) carry a
        nested signature VPK there that is larger than the header's declared
        signature size, so the trailer is treated as opaque and copied whole.
        """
        return self.file_size - self.signature_start

    def serialize(self, tree_size: int, file_data_size: int) -> bytes:
        if self.version >= 2:
            return struct.pack(
                "<IIIIIII",
                VPK_SIGNATURE,
                self.version,
                tree_size,
                file_data_size,
                self.archive_md5_size,
                self.other_md5_size,
                self.signature_size,
            )
        return struct.pack("<III", VPK_SIGNATURE, self.version, tree_size)

class Entry:
    __slots__ = (
        "ext", "dir", "name", "crc", "preload_bytes", "archive_index",
        "offset", "length", "preload_data", "out_offset",
    )

    def __init__(self, ext, dir_, name, crc, preload_bytes, archive_index,
                 offset, length, preload_data):
        self.ext = ext
        self.dir = dir_
        self.name = name
        self.crc = crc
        self.preload_bytes = preload_bytes
        self.archive_index = archive_index
        self.offset = offset
        self.length = length
        self.preload_data = preload_data
        self.out_offset = offset

    @property
    def path(self) -> str:
        # Root-level entries use a single space as their directory in VPK.
        return f"{self.name}.{self.ext}" if self.dir == " " else f"{self.dir}/{self.name}.{self.ext}"

    @property
    def embedded(self) -> bool:
        return self.archive_index == EMBEDDED_ARCHIVE_INDEX

    def __repr__(self) -> str:
        return f"<Entry {self.path!r} offset={self.offset} length={self.length}>"

def read_header(f) -> Header:
    f.seek(0, os.SEEK_END)
    file_size = f.tell()
    f.seek(0)

    raw = f.read(8)
    if len(raw) != 8:
        raise VpkError("file is too small to be a VPK")
    signature, version = struct.unpack("<II", raw)
    if signature != VPK_SIGNATURE:
        raise VpkError(f"not a VPK: signature 0x{signature:08X}, expected 0x{VPK_SIGNATURE:08X}")
    if version not in (1, 2):
        raise VpkError(f"unsupported VPK version {version} (only v1 and v2 are supported)")

    raw = f.read(4)
    if len(raw) != 4:
        raise VpkError("truncated header")
    (tree_size,) = struct.unpack("<I", raw)

    if version >= 2:
        raw = f.read(16)
        if len(raw) != 16:
            raise VpkError("truncated header")
        file_data_size, archive_md5_size, other_md5_size, signature_size = struct.unpack("<IIII", raw)
        header_size = 28
    else:
        # v1 has no trailer sections; the data region runs to EOF.
        archive_md5_size = other_md5_size = signature_size = 0
        header_size = 12
        file_data_size = file_size - header_size - tree_size

    if tree_size <= 0 or tree_size > file_size:
        raise VpkError(f"implausible tree size {tree_size}")

    header = Header(version, tree_size, file_data_size, archive_md5_size,
                    other_md5_size, signature_size, header_size, file_size)

    if version >= 2 and header.declared_size > file_size:
        raise VpkError(
            f"file is truncated: header declares {header.declared_size} bytes but the file is "
            f"{file_size} - refusing to touch a malformed archive"
        )
    if header.data_start > file_size:
        raise VpkError("data region starts past end of file")

    return header

def _read_cstr(buf: bytes, pos: int):
    end = buf.index(0, pos)
    return buf[pos:end].decode("utf-8", "surrogateescape"), end + 1

def parse_tree(tree: bytes) -> list:
    entries = []
    pos = 0
    size = len(tree)

    while pos < size:
        ext, pos = _read_cstr(tree, pos)
        if not ext:
            break
        while True:
            dir_, pos = _read_cstr(tree, pos)
            if not dir_:
                break
            while True:
                name, pos = _read_cstr(tree, pos)
                if not name:
                    break
                if pos + 18 > size:
                    raise VpkError("truncated directory entry")
                crc, preload, archive_index, offset, length, terminator = struct.unpack_from(
                    "<IHHIIH", tree, pos
                )
                pos += 18
                if terminator != 0xFFFF:
                    raise VpkError(f"bad entry terminator 0x{terminator:04X}")
                if preload:
                    if pos + preload > size:
                        raise VpkError("truncated preload data")
                    preload_data = tree[pos:pos + preload]
                    pos += preload
                else:
                    preload_data = b""
                entries.append(Entry(ext, dir_, name, crc, preload, archive_index,
                                     offset, length, preload_data))
    return entries

def build_tree(entries) -> bytes:
    """Rebuild the tree, preserving the original extension/directory grouping order."""
    by_ext = {}
    for e in entries:
        by_ext.setdefault(e.ext, {}).setdefault(e.dir, []).append(e)

    out = bytearray()

    def wcs(s: str) -> None:
        out.extend(s.encode("utf-8", "surrogateescape"))
        out.append(0)

    for ext, dirs in by_ext.items():
        wcs(ext)
        for dir_, group in dirs.items():
            wcs(dir_)
            for e in group:
                wcs(e.name)
                out.extend(struct.pack("<IHHIIH", e.crc, e.preload_bytes,
                                       e.archive_index, e.out_offset, e.length, 0xFFFF))
                if e.preload_bytes:
                    out.extend(e.preload_data)
            out.append(0)
        out.append(0)
    out.append(0)
    return bytes(out)

def verify(path: Path):
    """Re-read the archive and check every CRC32 and every MD5. Returns problems."""
    problems = []
    with open(path, "rb") as f:
        try:
            header = read_header(f)
        except VpkError as exc:
            return [f"header: {exc}"]

        tree_bytes = f.read(header.tree_size)
        try:
            entries = parse_tree(tree_bytes)
        except VpkError as exc:
            return [f"tree: {exc}"]

        # CRC32 of every entry's payload, compared against the value in the tree.
        for e in entries:
            crc = zlib.crc32(e.preload_data) if e.preload_data else 0
            if e.length == 0:
                if crc != e.crc:
                    problems.append(f"{e.path}: crc 0x{e.crc:08X} != computed 0x{crc:08X}")
                continue
            if not e.embedded:
                continue  # payload lives in a different file; cannot check here
            if e.offset + e.length > header.file_data_size:
                problems.append(f"{e.path}: offset+length runs past the data region")
                continue
            f.seek(header.data_start + e.offset)
            remaining = e.length
            while remaining > 0:
                chunk = f.read(min(COPY_CHUNK, remaining))
                if not chunk:
                    problems.append(f"{e.path}: short read")
                    break
                crc = zlib.crc32(chunk, crc)
                remaining -= len(chunk)
            else:
                if crc != e.crc:
                    problems.append(f"{e.path}: crc 0x{e.crc:08X} != computed 0x{crc:08X}")

        if header.version < 2 or header.other_md5_size != 48:
            return problems

        f.seek(header.other_md5_start)
        other = f.read(48)
        if len(other) != 48:
            problems.append("OtherMD5 section: truncated")
            return problems
        tree_hash, archive_hash, whole_hash = other[0:16], other[16:32], other[32:48]

        computed_tree = hashlib.md5(tree_bytes).digest()
        if computed_tree != tree_hash:
            problems.append(f"md5 tree: stored {tree_hash.hex()} != computed {computed_tree.hex()}")

        f.seek(header.archive_md5_start)
        archive_bytes = f.read(header.archive_md5_size)
        computed_archive = hashlib.md5(archive_bytes).digest()
        if computed_archive != archive_hash:
            problems.append(f"md5 archive: stored {archive_hash.hex()} != computed {computed_archive.hex()}")

        # Field 2 covers everything before and including the two checksums above.
        f.seek(0)
        digest = hashlib.md5()
        remaining = header.other_md5_start + 32
        while remaining > 0:
            chunk = f.read(min(COPY_CHUNK, remaining))
            if not chunk:
                break
            digest.update(chunk)
            remaining -= len(chunk)
        computed_whole = digest.digest()
        if computed_whole != whole_hash:
            problems.append(f"md5 whole: stored {whole_hash.hex()} != computed {computed_whole.hex()}")

    return problems
