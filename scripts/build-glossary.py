#!/usr/bin/env python3
"""Regenerate the glossary tables in c-glossary.qmd from glossary.csv.

The book has no executed cells: CI enforces that _freeze/ matches the source,
and contributors may not have Quarto locally, so a render-time cell would be
unbuildable. The tables are therefore generated ahead of time and committed.

    python3 scripts/build-glossary.py            # rewrite the .qmd
    python3 scripts/build-glossary.py --check    # fail if the .qmd is stale
"""

import argparse
import csv
import sys
from pathlib import Path

APPENDICES = Path(__file__).resolve().parent.parent / "en" / "appendices"
CSV_PATH = APPENDICES / "glossary.csv"
QMD_PATH = APPENDICES / "c-glossary.qmd"

BEGIN = "<!-- BEGIN GENERATED — edit glossary.csv, then run `make glossary`. -->"
END = "<!-- END GENERATED -->"

HEADERS = ("English", "Türkçe", "Notes")
COLWIDTHS = ': {tbl-colwidths="[35,35,30]"}'


def row(cells):
    return "|" + "|".join(f" {c} " if c else " " for c in cells) + "|"


def render(entries):
    out = []
    for group in dict.fromkeys(e["group"] for e in entries):
        out += [f"## {group}", "", row(HEADERS), "|---|---|---|"]
        out += [
            row((e["english"], e["turkish"], e["notes"]))
            for e in entries
            if e["group"] == group
        ]
        out += ["", COLWIDTHS, ""]
    return "\n".join(out[:-1])


def check_order(entries):
    """Groups must be contiguous and terms alphabetized within each group."""
    problems = []
    seen = []
    for i, e in enumerate(entries):
        if e["group"] not in seen:
            seen.append(e["group"])
        elif seen[-1] != e["group"]:
            problems.append(f"row {i + 2}: group {e['group']!r} is not contiguous")
        prev = entries[i - 1]
        if i and prev["group"] == e["group"]:
            if e["english"].casefold() < prev["english"].casefold():
                problems.append(
                    f"row {i + 2}: {e['english']!r} sorts before {prev['english']!r}"
                )
    return problems


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--check", action="store_true", help="verify without writing")
    args = ap.parse_args()

    with CSV_PATH.open(encoding="utf-8", newline="") as f:
        entries = list(csv.DictReader(f))

    if problems := check_order(entries):
        print(f"{CSV_PATH.name} is out of order:", file=sys.stderr)
        for p in problems:
            print(f"  {p}", file=sys.stderr)
        return 1

    current = QMD_PATH.read_text(encoding="utf-8")
    try:
        head, rest = current.split(BEGIN)
        _, tail = rest.split(END)
    except ValueError:
        print(f"{QMD_PATH.name}: missing BEGIN/END generated markers", file=sys.stderr)
        return 1

    updated = f"{head}{BEGIN}\n{render(entries)}\n\n{END}{tail}"

    if args.check:
        if updated != current:
            print(
                f"{QMD_PATH.name} is stale — run `make glossary` and commit.",
                file=sys.stderr,
            )
            return 1
        print(f"{QMD_PATH.name} is up to date ({len(entries)} terms).")
        return 0

    if updated == current:
        print(f"{QMD_PATH.name} already up to date ({len(entries)} terms).")
        return 0

    QMD_PATH.write_text(updated, encoding="utf-8")
    print(f"{QMD_PATH.name} regenerated ({len(entries)} terms).")
    return 0


if __name__ == "__main__":
    sys.exit(main())
