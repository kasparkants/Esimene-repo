"""Read-only signature scanner and file carver. Python 3.10+, no dependencies."""
from __future__ import annotations

import argparse
import json
import os
from pathlib import Path
import stat
import struct
import sys
import zipfile

CHUNK = 1024 * 1024
SIGNATURES = {"jpg": b"\xff\xd8\xff", "png": b"\x89PNG\r\n\x1a\n", "pdf": b"%PDF-", "zip": b"PK\x03\x04"}
FOOTERS = {"jpg": b"\xff\xd9", "png": b"\x00\x00\x00\x00IEND\xaeB`\x82", "pdf": b"%%EOF", "zip": b"PK\x05\x06"}


def raw_source(path: Path) -> bool:
    return str(path).startswith("\\\\.\\") or stat.S_ISBLK(path.stat().st_mode)


class AlignedReader:
    """Translate logical reads to aligned device reads (including Windows disks)."""
    def __init__(self, stream):
        self.stream = stream
        self.position = 0

    def seek(self, position):
        self.position = position

    def read(self, size):
        alignment = 4096
        base = self.position // alignment * alignment
        skip = self.position - base
        count = ((skip + size + alignment - 1) // alignment) * alignment
        self.stream.seek(base)
        data = self.stream.read(count)[skip:skip + size]
        self.position += len(data)
        return data


def offsets(stream, start, stop, kinds):
    """Find signatures across chunk boundaries without loading the disk."""
    position, tail = start, b""
    overlap = max(map(len, SIGNATURES.values())) - 1
    while stop is None or position < stop:
        stream.seek(position)
        data = stream.read(CHUNK if stop is None else min(CHUNK, stop - position))
        if not data:
            break
        block = tail + data
        base = position - len(tail)
        found = []
        for kind in kinds:
            signature = SIGNATURES[kind]
            cursor = 0
            while True:
                index = block.find(signature, cursor)
                if index < 0:
                    break
                absolute = base + index
                if absolute >= start and absolute + len(signature) > position:
                    found.append((absolute, kind))
                cursor = index + 1
        yield from sorted(found)
        tail = block[-overlap:]
        position += len(data)


def extent(stream, offset, kind, maximum, stop):
    """Find a bounded end marker; signatures alone never establish completeness."""
    limit = maximum if stop is None else min(maximum, stop - offset)
    stream.seek(offset)
    total, tail = 0, b""
    footer = FOOTERS[kind]
    while total < limit:
        block_start = offset + total - len(tail)
        data = stream.read(min(CHUNK, limit - total))
        if not data:
            break
        block = tail + data
        index = block.find(footer)
        if index >= 0:
            end = block_start + index + len(footer)
            if kind == "zip":
                stream.seek(end)
                record = stream.read(18)
                if len(record) != 18:
                    return None
                comment = struct.unpack_from("<H", record, 16)[0]
                end += 18 + comment
                stream.seek(end - 1)
                if not stream.read(1):
                    return None
            if end - offset <= limit:
                return end - offset
            return None
        total += len(data)
        tail = block[-(len(footer) - 1):]
    return None


def carve(stream, offset, length, target):
    stream.seek(offset)
    partial = target.with_name(target.name + ".partial")
    try:
        with partial.open("xb") as output:
            remaining = length
            while remaining:
                data = stream.read(min(CHUNK, remaining))
                if not data:
                    raise OSError("Source ended while copying a candidate")
                output.write(data)
                remaining -= len(data)
        # Linking publishes without overwriting an existing destination.
        os.link(partial, target)
        partial.unlink()
    except BaseException:
        # Do not delete a pre-existing file if exclusive creation failed.
        if 'output' in locals():
            partial.unlink(missing_ok=True)
        raise


def positive(value):
    number = int(value)
    if number <= 0:
        raise argparse.ArgumentTypeError("must be positive")
    return number


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("source", type=Path, help="disk image, ordinary file, or read-only raw device")
    parser.add_argument("--types", nargs="+", choices=SIGNATURES, default=list(SIGNATURES))
    parser.add_argument("--start", type=int, default=0, help="starting byte offset")
    parser.add_argument("--length", type=positive, help="maximum bytes of source to scan")
    parser.add_argument("--max-file-mib", type=positive, default=64)
    parser.add_argument("--max-candidates", type=positive, default=10000)
    parser.add_argument("--recover", type=Path, help="NEW directory for carved files; disk images only")
    args = parser.parse_args(argv)
    if args.start < 0:
        parser.error("--start must be nonnegative")
    source = args.source if str(args.source).startswith("\\\\.\\") else args.source.resolve()
    is_raw = raw_source(source)
    if args.recover and is_raw:
        parser.error("Image the drive first, then recover from the image to a separate healthy drive. Direct-device recovery is disabled to avoid overwriting recoverable data.")
    # Open the source before making any output. Never open it for writing.
    with source.open("rb", buffering=0) as source_stream:
        if args.recover:
            args.recover.mkdir(parents=True, exist_ok=False)
        size = 0 if is_raw else os.fstat(source_stream.fileno()).st_size
        stream = AlignedReader(source_stream) if is_raw else source_stream
        stop = args.start + args.length if args.length else (size or None)
        if size and stop is not None:
            stop = min(stop, size)
        candidates = 0
        truncated = False
        for offset, kind in offsets(stream, args.start, stop, set(args.types)):
            if candidates >= args.max_candidates:
                truncated = True
                break
            candidates += 1
            length = extent(stream, offset, kind, args.max_file_mib * CHUNK, stop)
            item = {"offset": offset, "format": kind, "bytes": length,
                    "status": "end-marker-found" if length else "incomplete-or-false-positive"}
            if length and args.recover:
                target = args.recover / f"{offset:016x}.{kind}"
                carve(stream, offset, length, target)
                item["saved_to"] = str(target)
                if kind == "zip":
                    try:
                        with zipfile.ZipFile(target) as archive:
                            item["zip_directory_valid"] = bool(archive.infolist())
                    except (zipfile.BadZipFile, OSError):
                        item["zip_directory_valid"] = False
            print(json.dumps(item), flush=True)
        print(json.dumps({"summary": True, "candidates": candidates, "candidate_limit_reached": truncated,
                          "note": "Signatures may be live files, deleted files, duplicates, embedded data, or false positives. End markers do not prove file integrity."}), flush=True)
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except KeyboardInterrupt:
        print("Scan interrupted; already completed copies remain available.", file=sys.stderr)
        raise SystemExit(130)
    except (OSError, ValueError) as error:
        print(f"Recovery error: {error}", file=sys.stderr)
        raise SystemExit(1)
