#!/usr/bin/env python3
"""Enforce the margin term-gloss contract.

The book explains a technical term the first time a chapter leans on it,
in a margin note. Those notes are written by hand, in context, because a
gloss that fits the sentence beats a generic definition. What must not
drift is the *terminology*: a margin note may not invent a term that the
glossary does not carry, or the appendix and the chapters slowly stop
agreeing.

The convention:

    ::: {.column-margin .term-gloss}
    **perplexity** — how many words the model is effectively choosing
    between at each step.
    :::

This script checks that

  1. every .term-gloss leads with a bolded term,
  2. that term appears in en/appendices/glossary.csv,
  3. no chapter glosses the same term twice,
  4. no chapter exceeds the per-chapter budget, because a page of margin
     notes is as unreadable as no notes at all.

    python3 scripts/check-glossary-use.py
"""

import csv
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
CSV_PATH = ROOT / "en" / "appendices" / "glossary.csv"

# Above this many per chapter the margin stops being a help and becomes
# a second column of text competing with the first.
BUDGET = 10

GLOSS_RE = re.compile(
    r"^:::+\s*\{[^}]*\.term-gloss[^}]*\}\s*$(.*?)^:::+\s*$",
    re.M | re.S,
)
LEAD_RE = re.compile(r"\*\*(.+?)\*\*")


def known_terms():
    """Every form a chapter may legitimately use to name a glossary entry.

    The CSV writes headwords the way the appendix should print them --
    "maximum likelihood estimation (MLE)", "n-gram / bigram" -- but prose
    names them one at a time, so each alternative and each parenthetical
    abbreviation counts as a match.
    """
    terms = set()
    with CSV_PATH.open(encoding="utf-8", newline="") as f:
        for row in csv.DictReader(f):
            head = row["english"]
            variants = {head}
            # "maximum likelihood estimation (MLE)" -> both halves
            m = re.match(r"^(.*?)\s*\(([^)]+)\)\s*$", head)
            if m:
                variants |= {m.group(1), m.group(2)}
            # "n-gram / bigram" -> each alternative
            for v in list(variants):
                variants |= {p.strip() for p in v.split("/") if p.strip()}
            terms |= {v.casefold() for v in variants if v}
    return terms


def main():
    terms = known_terms()
    problems = []
    counts = {}

    for path in sorted((ROOT / "en" / "chapters").glob("*.qmd")):
        rel = path.relative_to(ROOT)
        text = path.read_text(encoding="utf-8")
        seen = {}
        for m in GLOSS_RE.finditer(text):
            line = text[: m.start()].count("\n") + 1
            body = m.group(1).strip()
            lead = LEAD_RE.search(body)
            if not lead:
                problems.append(
                    f"{rel}:{line}: .term-gloss does not lead with a "
                    f"**bolded term**")
                continue
            term = lead.group(1).strip()
            key = term.casefold()
            if key not in terms:
                problems.append(
                    f"{rel}:{line}: '{term}' is not in glossary.csv — add "
                    f"it there, or name the term the way the glossary does")
            if key in seen:
                problems.append(
                    f"{rel}:{line}: '{term}' already glossed at line "
                    f"{seen[key]}; gloss a term once, at first use")
            else:
                seen[key] = line
        if seen:
            counts[rel] = len(seen)
            if len(seen) > BUDGET:
                problems.append(
                    f"{rel}: {len(seen)} term glosses exceeds the budget of "
                    f"{BUDGET}; the margin is not a second chapter")

    if problems:
        print(f"check-glossary-use: {len(problems)} problem(s)\n",
              file=sys.stderr)
        for p in problems:
            print(f"  {p}", file=sys.stderr)
        return 1

    total = sum(counts.values())
    print(f"check-glossary-use: {total} term glosses across "
          f"{len(counts)} chapters, all resolve")
    return 0


if __name__ == "__main__":
    sys.exit(main())
