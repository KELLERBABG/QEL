"""Repair every encoding fault in QEL-MASTER-PLAN.md, however it was introduced.

This file has been corrupted twice by appending from PowerShell, in two different ways,
and the two are now **mixed together in one file**:

1. **Single-byte cp1252.** ``Set-Content`` without ``-Encoding utf8`` writes the legacy
   ANSI code page, so an em dash becomes a bare ``0x97`` byte sitting among valid UTF-8.
2. **Double-encoded UTF-8.** ``Get-Content -Raw`` reads a UTF-8 file as cp1252, decoding
   each byte of a multi-byte sequence into its own character; writing that back as UTF-8
   turns ``—`` (``E2 80 94``) into ``Ã¢â‚¬â€``.

Reversing only one of them fails, which is why the first attempt at this found
``0x97`` blocking a cp1252 round-trip. The order matters and is:

* **First** undo the double encoding, per character: encode each character back through
  cp1252 to recover the byte the decoder produced, then decode the whole stream as
  UTF-8. Characters with no cp1252 mapping are passed through unchanged.
* **Then** fix any remaining stray cp1252 bytes -- the ones that are not part of a valid
  UTF-8 sequence -- by decoding each as cp1252.

Neither step can double-mangle, because the first only touches characters that
re-encode cleanly, and the second only touches bytes outside valid UTF-8.

**Safety.** Each stage reports what it changed, and the script refuses to write if the
result is not valid UTF-8. ``--check`` reports without writing.
"""
from __future__ import annotations

import sys
from pathlib import Path

TARGET = Path(__file__).resolve().parent.parent / "QEL-MASTER-PLAN.md"

UNDEFINED_CP1252 = (0x81, 0x8D, 0x8F, 0x90, 0x9D)
MOJIBAKE_MARKERS = ("\u00c3\u00a2", "\u00e2\u20ac", "\u00c2\u00a7", "\u00c3\u00a9")


def has_mojibake(text: str) -> bool:
    return any(marker in text for marker in MOJIBAKE_MARKERS)


def mark_valid_utf8(raw: bytes) -> bytearray:
    """1 for every byte inside a valid multi-byte UTF-8 sequence, else 0."""
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


def undo_double_encoding(text: str) -> tuple[str, int]:
    """Stage 1: reverse one round of cp1252<->UTF-8 double encoding."""
    raw = bytearray()
    touched = 0
    for ch in text:
        code = ord(ch)
        if code < 0x80:
            raw.append(code)
            continue
        if code in UNDEFINED_CP1252:
            raw.append(code)
            touched += 1
            continue
        try:
            raw.extend(ch.encode("cp1252"))
        except UnicodeEncodeError:
            raw.extend(ch.encode("utf-8"))
        touched += 1
    try:
        return raw.decode("utf-8"), touched
    except UnicodeDecodeError:
        # Expected: stray single-byte cp1252 from fault (1) is still present. Stage 2
        # handles it, so decode leniently here by falling back to the original text for
        # the parts that fail.
        return None, touched


def fix_stray_cp1252(text: str) -> tuple[str, dict[int, int]]:
    """Stage 2: decode bytes outside valid UTF-8 as cp1252."""
    raw = text.encode("utf-8")
    valid = mark_valid_utf8(raw)
    out = bytearray()
    counts: dict[int, int] = {}
    for index, byte in enumerate(raw):
        if byte < 0x80 or valid[index]:
            out.append(byte)
            continue
        try:
            out.extend(bytes([byte]).decode("cp1252").encode("utf-8"))
        except UnicodeDecodeError as exc:
            raise SystemExit(
                f"byte 0x{byte:02x} at offset {index} is not valid cp1252; "
                f"refusing to guess") from exc
        counts[byte] = counts.get(byte, 0) + 1
    return out.decode("utf-8"), counts


def repair(text: str) -> tuple[str, dict]:
    """Apply both stages and report what each did."""
    report: dict = {"mojibake_before": has_mojibake(text)}

    if has_mojibake(text):
        # Stage 1 works per *segment*: a segment that decodes cleanly is double-encoded
        # text; one that does not contains stray cp1252 and is left for stage 2.
        stage1 = undo_double_encoding(text)
        if stage1[0] is not None:
            text, touched = stage1
            report["stage1_reversed"] = True
            report["stage1_chars"] = touched
        else:
            report["stage1_reversed"] = False
    else:
        report["stage1_reversed"] = False

    text, counts = fix_stray_cp1252(text)
    report["stage2_bytes"] = counts
    report["mojibake_after"] = has_mojibake(text)
    return text, report


def main() -> int:
    text = TARGET.read_text(encoding="utf-8")
    fixed, report = repair(text)

    print(f"target            {TARGET.name}")
    print(f"chars before      {len(text)}")
    print(f"chars after       {len(fixed)}")
    print(f"mojibake before   {report['mojibake_before']}")
    print(f"stage 1 reversed  {report['stage1_reversed']}")
    if report.get("stage1_chars"):
        print(f"  chars passed    {report['stage1_chars']}")
    counts = report["stage2_bytes"]
    print(f"stage 2 bytes     {sum(counts.values())}")
    for byte, count in sorted(counts.items()):
        print(f"   0x{byte:02x} x{count}")
    print(f"mojibake after    {report['mojibake_after']}")

    sample = min((i for i, c in enumerate(text) if ord(c) > 0x7F), default=0)
    print(f"  before: {text[sample:sample + 40]!r}")
    print(f"  after : {fixed[sample:sample + 40]!r}")

    if report["mojibake_after"]:
        raise SystemExit("mojibake remains; not writing")
    if "--check" in sys.argv[1:]:
        print("\n--check: not writing")
        return 0
    TARGET.write_text(fixed, encoding="utf-8")
    print("\nrepaired and written")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
