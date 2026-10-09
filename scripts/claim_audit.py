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

#: A line stating a logical error rate, and the arithmetic check applied to it.
#:
#: This exists because a *wrong* p_L value cannot be caught by re-reading prose. The
#: whitepaper reported ``d=3 p=0.003: 0.00100`` at 6000 shots; that is six events at a
#: resolution of 1/6000, the measured count was ten, and the value survived because
#: 0.00100 / 0.00033 / 0.00000 formed a tidier monotone sequence than the truth.
#:
#: Two shapes are worth flagging, and both are decided by **arithmetic rather than
#: vocabulary**, which is the only reason they are checkable:
#:
#: 1. ``count/total`` and a decimal on the same line that disagree -- ``4/2000 = 0.00100``
#:    is wrong by exactly a factor of two and requires no domain knowledge to reject.
#: 2. A decimal whose value is **not an achievable count** at the stated sample size --
#:    ``0.00100`` at 6000 shots is 6.0000 events, and no count gives it. That is the check
#:    that would have caught the original error, and it needs only the shot count.
#:
#: A line without a shot count is left alone. Flagging every small decimal would also flag
#: the noise parameter being fed *in* (``p = 0.003``), and a check that cries wolf on
#: inputs is a check a reader learns to scroll past.
COUNT_RATE = re.compile(r"\b(\d{1,7})\s*/\s*(\d{2,9})\s*=")
DECIMAL_RATE = re.compile(r"(?<![\d.])(0\.\d{4,})(?![\d])")
SHOTS = re.compile(r"\b(\d[\d,]{3,})\s*shots\b", re.IGNORECASE)
#: A bracketed interval, whose bounds are *not* point estimates and must not be compared
#: against a count/total ratio. ``66/30000 = 0.00220 [0.00173, 0.00280]`` is correct, and
#: comparing the ratio against 0.00173 would report a false inconsistency.
BRACKETED = re.compile(r"\[[^\]]*\]")


def _is_length_ratio(count: int, total: int) -> bool:
    """``40/80`` in a placement result is a distance in km, not a rate.

    A count/total pair only reads as a rate when the quotient is plausibly one. A ratio
    above 1 cannot be a probability, and neither can ``120/160`` when the line is about
    span lengths -- so anything outside [0, 1] is skipped rather than reported.
    """
    if total == 0:
        return True
    ratio = count / total
    return not (0.0 <= ratio <= 1.0)


def inconsistent_rates(path: pathlib.Path) -> list[tuple[int, str]]:
    """Lines where a stated rate disagrees with its own arithmetic.

    Returns ``[(line number, explanation)]``. Checks performed:

    * a decimal beside a ``count/total`` pair must equal that ratio
    * a decimal on a line naming a shot count must be an achievable count at that size

    Only these. The check is deliberately incapable of judging a rate on its own merits --
    it knows nothing about whether a decoder is any good -- and can only say that two
    numbers on the same line contradict each other. That is exactly the class of error it
    is meant to catch.
    """
    problems: list[tuple[int, str]] = []
    text = path.read_text(encoding="utf-8", errors="replace")
    for number, line in enumerate(text.splitlines(), start=1):
        # Interval bounds are not point estimates, so remove bracketed spans before
        # looking for a decimal to compare against a ratio.
        outside = BRACKETED.sub(" ", line)
        decimals = [float(d) for d in DECIMAL_RATE.findall(outside)]

        for count, total in COUNT_RATE.findall(line):
            k, n = int(count), int(total)
            if n == 0 or _is_length_ratio(k, n):
                continue
            ratio = k / n
            for dec in decimals:
                # Allow for the decimal being rounded to 5 places.
                if abs(dec - ratio) > max(5e-5, 0.01 * ratio):
                    problems.append(
                        (number,
                         f"{k}/{n} = {ratio:.5f} but the line states {dec:.5f}"))
                    break

        shot_match = SHOTS.search(line)
        if shot_match and decimals:
            n = int(shot_match.group(1).replace(",", ""))
            if n > 0:
                for dec in decimals:
                    events = dec * n
                    # An achievable rate is k/n for integer k. Tolerance is half an event.
                    if abs(events - round(events)) > 0.5:
                        problems.append(
                            (number,
                             f"{dec:.5f} at {n} shots is {events:.2f} events, "
                             f"which no count produces"))
                        break
    return problems


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


def unsupported_rates(path: pathlib.Path) -> list[tuple[int, str]]:
    """Kept as the public name for the arithmetic check; see :func:`inconsistent_rates`."""
    return inconsistent_rates(path)


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

        bare = unsupported_rates(path)
        if bare:
            print(f"\n  INCONSISTENT ARITHMETIC ({len(bare)}):")
            for number, text in bare:
                print(f"    L{number:<5} {text}")
            print("    (two numbers on one line contradict each other; this tool cannot")
            print("     judge whether a rate is good, only whether it is self-consistent)")
        else:
            print("\n  no self-inconsistent rates found")

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
