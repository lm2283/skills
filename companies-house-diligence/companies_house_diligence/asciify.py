"""Rewrite text files as plain ASCII.

The profile and its edits should be ASCII-only so they never trip a Windows
console / cp1252 pipe. ``brief.py`` already writes ASCII by default, but after
you hand-edit ``brief.md`` (transcribing figures, rewriting the ownership
section) you may reintroduce a pound sign, an em dash or an accented name. Run
this as the final step, before building the ``.docx``:

    python -m companies_house_diligence.asciify path/to/brief.md

Each file is read as UTF-8, transliterated to ASCII (pound -> 'GBP', dashes ->
'-', smart quotes -> straight, accents flattened) and written back in place.
"""

from __future__ import annotations

from pathlib import Path

from . import plain


def asciify_file(path) -> int:
    """ASCII-normalise one file in place; return the count of bytes changed."""
    p = Path(path)
    original = p.read_text(encoding="utf-8", errors="replace")
    cleaned = plain.asciify(original)
    if cleaned != original:
        p.write_text(cleaned, encoding="utf-8")
    return sum(1 for a, b in zip(original, cleaned) if a != b) + abs(
        len(original) - len(cleaned))


def main(argv=None):
    import argparse
    plain.configure_stdout()
    ap = argparse.ArgumentParser(
        description="Rewrite text files as plain ASCII (in place).")
    ap.add_argument("files", nargs="+", help="files to normalise (e.g. brief.md)")
    args = ap.parse_args(argv)
    for f in args.files:
        try:
            changed = asciify_file(f)
        except OSError as e:
            print(f"skip {f}: {e}")
            continue
        print(f"asciified {f}" + (" (no change)" if not changed else ""))


if __name__ == "__main__":
    main()
