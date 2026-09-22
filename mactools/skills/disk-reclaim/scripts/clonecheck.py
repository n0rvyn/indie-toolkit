#!/usr/bin/env python3
"""Detect APFS clones by comparing physical block addresses.

`du` counts a clone's full size, but cloned blocks are shared with the
original — deleting the clone frees little or nothing. F_LOG2PHYS_EXT
returns the device offset of a file's first extent; two files that map to
the same offset share blocks.

Usage:
    clonecheck.py <reference> <candidate> [<candidate> ...]
    clonecheck.py --selftest

Exit 0 always (this is a probe, not a gate). Output is TSV:
    SHARED|DISTINCT|ERR <devoffset> <path>
"""
import fcntl
import os
import struct
import subprocess
import sys
import tempfile

F_LOG2PHYS_EXT = 65


def devoffset(path, offset=0):
    """Physical device offset of the extent containing `offset`."""
    fd = os.open(path, os.O_RDONLY)
    try:
        buf = struct.pack("=IQq", 0, 1024 * 1024, offset)
        res = fcntl.fcntl(fd, F_LOG2PHYS_EXT, buf)
        _flags, _contig, dev = struct.unpack("=IQq", res)
        return dev
    finally:
        os.close(fd)


def alloc(path):
    """(logical bytes, allocated bytes) — allocated is what the disk holds."""
    st = os.stat(path)
    return st.st_size, st.st_blocks * 512


def compare(ref, candidates):
    try:
        ref_off = devoffset(ref)
    except OSError as exc:
        print(f"ERR\t-\t{ref}\t{exc}")
        return
    print(f"REF\t{ref_off}\t{ref}")
    for cand in candidates:
        try:
            off = devoffset(cand)
        except OSError as exc:
            print(f"ERR\t-\t{cand}\t{exc}")
            continue
        verdict = "SHARED" if off == ref_off else "DISTINCT"
        print(f"{verdict}\t{off}\t{cand}")


def selftest():
    """Prove the checker returns non-zero on a known positive before its
    zeros are trusted. Builds its own fixtures — no dependency on what
    happens to be installed on this host."""
    ok = True
    with tempfile.TemporaryDirectory() as tmp:
        # --- positive control 1: a real APFS clone must read as SHARED ---
        src = os.path.join(tmp, "src.bin")
        with open(src, "wb") as fh:
            fh.write(os.urandom(4 * 1024 * 1024))
        dst = os.path.join(tmp, "clone.bin")
        rc = subprocess.run(["cp", "-c", src, dst], capture_output=True).returncode
        if rc != 0:
            print("SKIP  clone detection — `cp -c` failed (non-APFS volume?)")
        else:
            same = devoffset(src) == devoffset(dst)
            print(f"{'PASS' if same else 'FAIL'}  clone -> SHARED "
                  f"(src={devoffset(src)} clone={devoffset(dst)})")
            ok &= same

        # --- negative control: an independent copy must read as DISTINCT ---
        indep = os.path.join(tmp, "copy.bin")
        subprocess.run(["cp", src, indep], capture_output=True)
        # `cp` on APFS may clone implicitly; force distinct blocks by rewriting.
        with open(indep, "r+b") as fh:
            fh.seek(0)
            fh.write(os.urandom(4 * 1024 * 1024))
            fh.flush()
            os.fsync(fh.fileno())
        distinct = devoffset(src) != devoffset(indep)
        print(f"{'PASS' if distinct else 'FAIL'}  rewritten copy -> DISTINCT "
              f"(src={devoffset(src)} copy={devoffset(indep)})")
        ok &= distinct

        # --- positive control 2: sparse file, logical >> allocated ---
        sparse = os.path.join(tmp, "sparse.img")
        with open(sparse, "wb") as fh:
            fh.truncate(8 * 1024 * 1024 * 1024)  # 8 GiB logical, ~0 allocated
        logical, allocated = alloc(sparse)
        sparse_ok = logical > allocated * 100
        print(f"{'PASS' if sparse_ok else 'FAIL'}  sparse detection "
              f"(logical={logical} allocated={allocated})")
        ok &= sparse_ok

        # --- negative control: a dense file must NOT look sparse ---
        logical, allocated = alloc(src)
        dense_ok = allocated >= logical
        print(f"{'PASS' if dense_ok else 'FAIL'}  dense file not flagged sparse "
              f"(logical={logical} allocated={allocated})")
        ok &= dense_ok

    print("SELFTEST " + ("PASS" if ok else "FAIL"))
    return 0 if ok else 1


if __name__ == "__main__":
    args = sys.argv[1:]
    if not args or args[0] in ("-h", "--help"):
        print(__doc__)
        sys.exit(0)
    if args[0] == "--selftest":
        sys.exit(selftest())
    if len(args) < 2:
        print("need a reference and at least one candidate", file=sys.stderr)
        sys.exit(2)
    compare(args[0], args[1:])
