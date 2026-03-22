#!/usr/bin/env python3
"""
halva2 Archive Extractor
========================
Format: Raw brotli-compressed PAX tar archive (no magic header).
The "CB FF" bytes often seen at the start are brotli bitstream
encoding artefacts, not a format signature.

Usage:
  python halva2_extract.py <file.halva2>              # extract to ./out/
  python halva2_extract.py <file.halva2> -o <outdir>  # extract to custom dir
  python halva2_extract.py <file.halva2> -l            # list contents only
  python halva2_extract.py <file.halva2> -i            # print archive info
"""

import sys
import io
import os
import tarfile
import argparse
from pathlib import Path

# ── dependency check ────────────────────────────────────────────────────────

try:
    import brotli
except ImportError:
    print("ERROR: 'brotli' package not found.\n"
          "Install with:  pip install brotli", file=sys.stderr)
    sys.exit(1)


# ── core helpers ─────────────────────────────────────────────────────────────

def decompress(path: str) -> bytes:
    """Read a .halva2 file and return the decompressed bytes."""
    with open(path, "rb") as f:
        data = f.read()

    compressed_size = len(data)

    try:
        raw = brotli.decompress(data)
    except brotli.error as e:
        raise ValueError(
            f"Brotli decompression failed: {e}\n"
            "This file may not be a valid halva2 archive, or it could be\n"
            "a 'lesser-compacted' (stored) variant which is not yet supported."
        ) from e

    return raw, compressed_size


def open_tar(raw: bytes) -> tarfile.TarFile:
    """Open decompressed bytes as a tar archive."""
    buf = io.BytesIO(raw)
    try:
        tf = tarfile.open(fileobj=buf, mode="r:")
    except tarfile.TarError as e:
        raise ValueError(f"Failed to open tar archive: {e}") from e
    return tf


# ── commands ─────────────────────────────────────────────────────────────────

def cmd_info(path: str) -> None:
    """Print archive statistics."""
    raw, compressed_size = decompress(path)
    tf = open_tar(raw)
    members = tf.getmembers()
    files   = [m for m in members if m.isfile()]
    dirs    = [m for m in members if m.isdir()]
    total_bytes = sum(m.size for m in files)

    from collections import Counter
    ext_counts = Counter()
    ext_sizes  = Counter()
    for m in files:
        ext = Path(m.name).suffix.lower() or "(no ext)"
        ext_counts[ext] += 1
        ext_sizes[ext]  += m.size

    print(f"File            : {path}")
    print(f"Compressed size : {compressed_size:>12,} bytes  ({compressed_size/1024/1024:.2f} MiB)")
    print(f"Unpacked size   : {len(raw):>12,} bytes  ({len(raw)/1024/1024:.2f} MiB)")
    print(f"Compression     : {compressed_size/len(raw)*100:.1f}%  (ratio {len(raw)/compressed_size:.1f}x)")
    print(f"Tar entries     : {len(members):>5}  ({len(files)} files, {len(dirs)} dirs)")
    print(f"Total data size : {total_bytes:>12,} bytes  ({total_bytes/1024/1024:.2f} MiB)")
    print()
    print("File types:")
    for ext, count in ext_counts.most_common():
        size = ext_sizes[ext]
        bar  = "█" * min(40, int(40 * size / max(ext_sizes.values())))
        print(f"  {ext:<12} {count:>5} files  {size/1024/1024:>8.2f} MiB  {bar}")
    tf.close()


def cmd_list(path: str) -> None:
    """List all entries in the archive."""
    raw, _ = decompress(path)
    tf = open_tar(raw)
    members = tf.getmembers()
    print(f"{'Type':<5} {'Size':>12}  {'Name'}")
    print("-" * 70)
    for m in members:
        kind = "DIR " if m.isdir() else "FILE"
        size = f"{m.size:>12,}" if m.isfile() else " " * 13
        print(f"{kind}  {size}  {m.name}")
    print(f"\nTotal: {len(members)} entries")
    tf.close()


def cmd_extract(path: str, outdir: str) -> None:
    """Extract all files to outdir."""
    out = Path(outdir)
    out.mkdir(parents=True, exist_ok=True)

    print(f"Decompressing {path} …")
    raw, compressed_size = decompress(path)
    print(f"  {compressed_size:,} bytes  →  {len(raw):,} bytes  "
          f"({len(raw)/compressed_size:.1f}x)")

    tf = open_tar(raw)
    members = tf.getmembers()
    files   = [m for m in members if m.isfile()]

    print(f"Extracting {len(files)} files to {out} …")
    extracted = 0
    skipped   = 0

    for member in members:
        # Safety: strip leading slashes / drive letters, resolve path traversal
        name = member.name
        # Normalise Windows-style backslashes from PAX paths
        name = name.replace("\\", os.sep)
        # Strip any leading ./ or /
        name = name.lstrip("./").lstrip(os.sep)
        # Guard against path traversal
        dest = (out / name).resolve()
        if not str(dest).startswith(str(out.resolve())):
            print(f"  [SKIP] path traversal attempt: {member.name}")
            skipped += 1
            continue

        if member.isdir():
            dest.mkdir(parents=True, exist_ok=True)
        elif member.isfile():
            dest.parent.mkdir(parents=True, exist_ok=True)
            f_obj = tf.extractfile(member)
            if f_obj is None:
                skipped += 1
                continue
            dest.write_bytes(f_obj.read())
            extracted += 1
            # Show progress every 50 files
            if extracted % 50 == 0:
                print(f"  … {extracted}/{len(files)} files done")

    tf.close()
    print(f"\nDone! {extracted} files extracted to '{out}'")
    if skipped:
        print(f"WARNING: {skipped} entries were skipped (see above).")


# ── CLI ───────────────────────────────────────────────────────────────────────

def main() -> None:
    parser = argparse.ArgumentParser(
        description="Extract .halva2 archives (brotli-compressed PAX tar).",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=__doc__,
    )
    parser.add_argument("file", help="Path to .halva2 archive")
    group = parser.add_mutually_exclusive_group()
    group.add_argument("-l", "--list",    action="store_true", help="List contents only")
    group.add_argument("-i", "--info",    action="store_true", help="Show archive statistics")
    group.add_argument("-o", "--outdir",  default=None,
                       help="Output directory (default: ./out/<archive_name>)")
    args = parser.parse_args()

    if not os.path.isfile(args.file):
        print(f"ERROR: file not found: {args.file}", file=sys.stderr)
        sys.exit(1)

    try:
        if args.list:
            cmd_list(args.file)
        elif args.info:
            cmd_info(args.file)
        else:
            outdir = args.outdir or os.path.join(
                "out", Path(args.file).stem
            )
            cmd_extract(args.file, outdir)
    except (ValueError, OSError) as e:
        print(f"ERROR: {e}", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()