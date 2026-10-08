"""Repair the encoding damage in QEL-MASTER-PLAN.md.

**What broke.** The file was appended to from PowerShell with ``Set-Content`` without an
encoding argument, which on Windows PowerShell uses the legacy ANSI code page (cp1252).
Characters I inserted -- em dashes and section signs -- were written as single cp1252
bytes instead of UTF-8 sequences, while the rest of the file (written by tools that do
emit UTF-8) stayed valid UTF-8. The result is a file with **mixed encoding**: valid UTF-8
multi-byte sequences interleaved with stray cp1252 bytes.

Consequence: the file no longer decodes as UTF-8, so ``read`` refuses it and any tool that
assumes UTF-8 will fail or silently mangle it. This is my defect, introduced while
appending sections 3.12-3.25 with ``Set-Content $path $string``.

**The repair.** Walk the file and mark every byte that is part of a *valid* UTF-8
sequence. Bytes outside such a sequence are the mangled ones; each is decoded as cp1252
and re-emitted as UTF-8. Neither step touches the already-valid text, so the repair cannot
double-mangle.

**Safety.** The script writes to the target only when every stray byte maps to a defined
cp1252 character, and it prints a before/after count so the change is auditable. Run with
``--check`` to report without writing.
"""
from __future__ import annotations

import sys
from pathlib import Path

TARGET = Path(__file__).resolve().parent.parent / "QEL-MASTER-PLAN.md"


def mark_valid_utf8(raw: bytes) -> bytearray:
    """1 for every byte inside a valid multi-byte UTF-8 sequence, else 0.

    A byte below 0x80 is always valid. Otherwise the longest decodable sequence of
    continuation bytes starting here is marked, which leaves genuine cp1252 punctuation
    (which cannot begin a valid UTF-8 sequence) unmarked.
    """
    valid = bytearray(len(raw))
    i = 0
    while i < len(raw):
        byte = raw[i]
        if byte < 0x80:
            valid[i] = 1
            i += 1
            continue
        for length in (2, 3, 4):
            chunk = raw[i:i + length]
            if len(chunk) != length:
                continue
            try:
                chunk.decode("utf-8")
            except UnicodeDecodeError:
                continue
            if all(c >= 0x80 for c in chunk):
                for k in range(i, i + length):
                    valid[k] = 1
                i += length
                break
        else:
            i += 1
    return valid


def repair(raw: bytes) -> tuple[bytes, dict[int, int]]:
    """Return the repaired bytes and a count of each stray byte replaced."""
    valid = mark_valid_utf8(raw)
    out = bytearray()
    counts: dict[int, int] = {}
    for index, byte in enumerate(raw):
        if byte < 0x80 or valid[index]:
            out.append(byte)
            continue
        try:
            replacement = bytes([byte]).decode("cp1252").encode("utf-8")
        except UnicodeDecodeError as exc:
            raise SystemExit(
                f"byte 0x{byte:02x} at offset {index} is not valid cp1252; "
                f"refusing to guess. Context: "
                f"{raw[max(0, index - 40):index + 20]!r}") from exc
        out.extend(replacement)
        counts[byte] = counts.get(byte, 0) + 1
    return bytes(out), counts


def main() -> int:
    raw = TARGET.read_bytes()
    fixed, counts = repair(raw)

    print(f"target            {TARGET.name}")
    print(f"size before       {len(raw)} bytes")
    print(f"size after        {len(fixed)} bytes")
    print(f"stray bytes fixed {sum(counts.values())}")
    for byte, count in sorted(counts.items()):
        char = bytes([byte]).decode("cp1252")
        print(f"   0x{byte:02x} x{count:<5d} -> U+{ord(char):04X} {char!r}")

    try:
        fixed.decode("utf-8")
    except UnicodeDecodeError as exc:  # pragma: no cover
        raise SystemExit(f"repair produced invalid utf-8: {exc}")

    if "--check" in sys.argv[1:]:
        print("\n--check: not writing")
        return 0

    TARGET.write_bytes(fixed)
    print("\nrepaired and written")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
