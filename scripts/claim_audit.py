"""Extract every checkable numeric claim from a document, so drift is detectable.

**Why this exists.** Over one session this repository accumulated stale claims in six
places: four plan status rows marked `Partial`/`Todo` for work that was finished, a README
claiming `668 tests` and `17 CLI commands`, a website claiming `122 tests`, and a section
titled "Is 555 tests a lot?". Every one was written correctly when written, and every one
silently rotted as the code moved. Re-reading the prose more carefully does not fix that;
a parser does.

**What it does.** Pulls the specific claim *shapes* this project uses out of a text file
and prints them, so a reviewer can diff them against reality in one pass instead of
trusting that the last person re-read everything:

* test counts -- `1036 tests`, `122 tests`
* command counts -- `21 CLI commands`, `17 commands`
* line counts -- `15,351` / `15,351 lines`
* confidence markers the plan uses -- `[measured]`, `[verified]`, `[unverified]`

**What it deliberately does not do.** It does not decide whether a claim is *true* -- it
cannot know which number is the right one, and a tool that guessed would introduce exactly
the kind of confident-but-wrong output this project spends its effort avoiding. It reports
what the document asserts and what the repository currently measures, side by side, and
leaves the comparison to a human who can see both.

Usage::

    py scripts/claim_audit.py                # audit README.md and index.html
    py scripts/claim_audit.py FILE [FILE..]  # audit specific files
"""

from __future__ import annotations

import pathlib
import re
import subprocess
import sys

ROOT = pathlib.Path(__file__).resolve().parent.parent

#: Claim shapes worth flagging, with a human-readable label.
PATTERNS: tuple[tuple[str, str], ...] = (
    ("test count", r"\b(\d[\d,]*)\s+tests?\b"),
    ("command count", r"\b(\d[\d,]*)\s+(?:CLI\s+)?commands?\b"),
    ("protocol count", r"\b(\d[\d,]*)\s+protocols?\b"),
    ("module count", r"\b(\d[\d,]*)\s+modules?\b"),
    ("line count", r"\b(\d[\d,]{3,})\s+(?:source|test)?\s*lines?\b"),
)

#: Section markers the plan uses to separate verified from unverified statements.
MARKERS: tuple[str, ...] = ("[measured]", "[verified]", "[unverified]", "[superseded]")


def _measure_tests() -> str:
    """The current test count, from the suite itself.

    Run with ``--collect-only`` so the audit never executes a test: an audit that could
    fail because a test fails would conflate "the docs are stale" with "the code is
    broken", which are different findings.
    """
    try:
        result = subprocess.run(
            [sys.executable, "-m", "pytest", "-q", "--collect-only"],
            cwd=ROOT, capture_output=True, text=True, timeout=180)
    except (OSError, subprocess.SubprocessError) as exc:
        return f"unavailable ({type(exc).__name__})"
    match = re.search(r"(\d+) tests? collected", result.stdout)
    return match.group(1) if match else "unavailable"


def _measure_commands() -> str:
    try:
        result = subprocess.run(
            [sys.executable, "-m", "quantumnet", "--help"],
            cwd=ROOT, capture_output=True, text=True, timeout=120)
    except (OSError, subprocess.SubprocessError) as exc:
        return f"unavailable ({type(exc).__name__})"
    match = re.search(r"\{([a-z0-9,\-]+)\}", result.stdout)
    return str(len(match.group(1).split(","))) if match else "unavailable"


def _measure_lines(pattern: str) -> str:
    total = sum(len(f.read_text(encoding="utf-8", errors="replace").splitlines())
                for f in ROOT.glob(pattern))
    return f"{total:,}"


def measure_repository() -> dict[str, str]:
    """What the repository currently measures, for each claim shape."""
    return {
        "test count": _measure_tests(),
        "command count": _measure_commands(),
        "protocol count": str(len([p for p in (ROOT / "src/quantumnet/protocols").glob("*.py")
                                   if p.name != "__init__.py"])),
        "module count": str(len(list((ROOT / "src").rglob("*.py")))),
        "line count": f"{_measure_lines('src/**/*.py')} source, "
                      f"{_measure_lines('tests/**/*.py')} test",
    }


def extract(path: pathlib.Path) -> dict[str, list[tuple[int, str]]]:
    """Claim shape -> [(line number, matched text)] for one file."""
    found: dict[str, list[tuple[int, str]]] = {label: [] for label, _ in PATTERNS}
    text = path.read_text(encoding="utf-8", errors="replace")
    for number, line in enumerate(text.splitlines(), start=1):
        for label, pattern in PATTERNS:
            for match in re.finditer(pattern, line, re.IGNORECASE):
                found[label].append((number, match.group(0).strip()))
    return found


def marker_counts(path: pathlib.Path) -> dict[str, int]:
    text = path.read_text(encoding="utf-8", errors="replace")
    return {marker: text.count(marker) for marker in MARKERS}


def audit(paths: list[pathlib.Path]) -> int:
    measured = measure_repository()
    print("=" * 74)
    print("REPOSITORY MEASURES")
    print("=" * 74)
    for label, value in measured.items():
        print(f"  {label:<18} {value}")

    for path in paths:
        if not path.exists():
            print(f"\n  MISSING: {path}")
            continue
        print()
        print("=" * 74)
        print(f"CLAIMS IN {path.name}")
        print("=" * 74)
        found = extract(path)
        for label, entries in found.items():
            if not entries:
                continue
            print(f"\n  {label} (repository says: {measured.get(label, 'n/a')})")
            for number, text in entries:
                print(f"    L{number:<5} {text}")

        markers = marker_counts(path)
        present = {k: v for k, v in markers.items() if v}
        if present:
            print(f"\n  confidence markers: {present}")
            print("    (each is a claim about how well something was verified;")
            print("     an [unverified] marker that outlives its verification is a bug)")

    print()
    print("=" * 74)
    print("This tool does not decide truth. Compare the two columns by hand.")
    print("=" * 74)
    return 0


def main(argv: list[str]) -> int:
    if argv:
        paths = [pathlib.Path(a) for a in argv]
    else:
        paths = [ROOT / "README.md", ROOT / "index.html"]
    return audit(paths)


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
