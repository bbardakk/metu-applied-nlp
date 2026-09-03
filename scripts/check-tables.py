#!/usr/bin/env python3
"""Check the table conventions the book relies on, in both editions.

Three things go wrong silently in a Quarto pipeline, and all three render
as a page that looks fine until someone reads it closely:

  1. A column-width list that does not sum to 100. The book writes these
     as percentages, so an 88 is an arithmetic slip rather than a choice,
     and it makes one table narrower than its neighbours for no reason.
  2. A width list with the wrong number of entries for its table.
  3. A caption line glued to the table with no blank line between them.

Also reported: rows in one table with different cell counts, which
pandoc will silently pad or truncate.

    python3 scripts/check-tables.py
"""

import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
WIDTHS = re.compile(r'\{tbl-colwidths="\[([0-9,\s]+)\]"\}')


def cells(line):
    s = line.strip()
    if s.startswith("|"):
        s = s[1:]
    if s.endswith("|"):
        s = s[:-1]
    return len(s.split("|"))


def check(path):
    problems = []
    lines = path.read_text(encoding="utf-8").split("\n")
    rel = path.relative_to(ROOT)

    in_fence = False
    block, block_start = [], 0
    for i, line in enumerate(lines):
        if line.startswith("```"):
            in_fence = not in_fence
            continue
        if in_fence:
            continue

        is_row = line.strip().startswith("|") and line.strip().endswith("|")
        if is_row:
            if not block:
                block_start = i + 1
            block.append(line)
            continue

        if block:
            widths = {cells(r) for r in block}
            if len(widths) > 1:
                problems.append(
                    f"{rel}:{block_start}: rows have {sorted(widths)} cells")
            # the caption may be this line or the blank-separated next one
            for j in range(i, min(i + 3, len(lines))):
                m = WIDTHS.search(lines[j])
                if not m:
                    continue
                if j == i:
                    problems.append(
                        f"{rel}:{j + 1}: caption needs a blank line above it")
                nums = [int(x) for x in m.group(1).split(",")]
                if sum(nums) != 100:
                    problems.append(
                        f"{rel}:{j + 1}: widths sum to {sum(nums)}, not 100")
                if len(nums) != cells(block[0]):
                    problems.append(
                        f"{rel}:{j + 1}: {len(nums)} widths for "
                        f"{cells(block[0])} columns")
                break
            block = []
    return problems


def main():
    problems = []
    for edition in ("en", "tr"):
        for path in sorted((ROOT / edition).rglob("*.qmd")):
            problems += check(path)
    if problems:
        print("table problems:", file=sys.stderr)
        for p in problems:
            print(f"  {p}", file=sys.stderr)
        return 1
    print("check-tables: every table's caption, widths and rows are consistent")
    return 0


if __name__ == "__main__":
    sys.exit(main())
