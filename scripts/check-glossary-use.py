#!/usr/bin/env python3
"""Enforce the margin term-gloss contract.

The book explains a technical term the first time a chapter leans on it,
in a margin note. Those notes are written by hand, in context, because a
gloss that fits the sentence beats a generic definition. What must not
drift is the *terminology*: a margin note may not invent a term that the
glossary does not carry, or the appendix and the chapters slowly stop
agreeing.

The convention:

    the [perplexity](#gloss-perplexity){#term-perplexity .term-ref} of a

    ::: {#gloss-perplexity .column-margin .term-gloss}
    **perplexity** — how many words the model is effectively choosing
    between at each step. [↩](#term-perplexity){.term-back}
    :::

This script checks that

  1. every .term-gloss leads with a bolded term,
  2. that term appears in en/appendices/glossary.csv,
  3. no chapter glosses the same term twice,
  4. no chapter exceeds the per-chapter budget, because a page of margin
     notes is as unreadable as no notes at all,
  5. every gloss is wired to the word it explains: the note carries the
     matching id, the body marks the term exactly once, and each end
     links back to the other.

Rule 5 is the one that rots silently. Half a link still renders as clean
prose -- a term marked in the body whose note has lost its id just scrolls
nowhere, and a note whose term was reworded out of the sentence leaves an
arrow pointing at nothing. Neither is visible in a rendered page.

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
    r"^:::+\s*\{([^}]*\.term-gloss[^}]*)\}\s*$(.*?)^:::+\s*$",
    re.M | re.S,
)
LEAD_RE = re.compile(r"\*\*(.+?)\*\*")
# The body-side mark, as scripts/link-glosses.py writes it.
REF_RE = re.compile(
    r"\[[^\]]*\]\(#gloss-([a-z0-9-]+)\)\{#term-([a-z0-9-]+) \.term-ref\}")


def slug(term):
    """The id both ends of a link are built from. Must match link-glosses.py."""
    s = term.lower().replace("&", " and ")
    return re.sub(r"[^a-z0-9]+", "-", s).strip("-")


def turkish_terms():
    """What the Turkish edition may call a glossary entry.

    The Turkish chapters keep the English gloss *id* -- #gloss-span-level-f1
    -- because the id is what links the two editions to one appendix. The
    bolded term is whatever that chapter calls the thing, which is the
    English headword when the book keeps it English and the CSV's Turkish
    column when it does not. Both are allowed; anything else is drift.
    """
    terms = set()
    with CSV_PATH.open(encoding="utf-8", newline="") as f:
        for row in csv.DictReader(f):
            for col in ("english", "turkish"):
                head = row[col].replace("\u25c6", "").strip()
                variants = {head}
                m = re.match(r"^(.*?)\s*\(([^)]+)\)\s*$", head)
                if m:
                    variants |= {m.group(1), m.group(2)}
                for v in list(variants):
                    variants |= {p.strip() for p in v.split("/") if p.strip()}
                terms |= {v.casefold() for v in variants if v}
    return terms


def known_slugs():
    """Every #gloss- id the appendix can be linked to.

    The id is built from the English headword and is the same in both
    editions, because it is what ties a Turkish margin note to the one
    shared appendix. A chapter may shorten "byte-pair encoding (BPE)" to
    byte-pair-encoding, so the parenthetical-stripped form counts too.
    """
    slugs = set()
    with CSV_PATH.open(encoding="utf-8", newline="") as f:
        for row in csv.DictReader(f):
            head = row["english"]
            variants = {head}
            m = re.match(r"^(.*?)\s*\(([^)]+)\)\s*$", head)
            if m:
                variants |= {m.group(1), m.group(2)}
            for v in list(variants):
                variants |= {p.strip() for p in v.split("/") if p.strip()}
            slugs |= {slug(v) for v in variants if v}
    return slugs


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
    term_sets = {"en": known_terms(), "tr": turkish_terms()}
    slugs = known_slugs()
    problems = []
    counts = {}

    paths = [(ed, p) for ed in ("en", "tr")
             for p in sorted((ROOT / ed / "chapters").glob("*.qmd"))]
    for edition, path in paths:
        terms = term_sets[edition]
        rel = path.relative_to(ROOT)
        text = path.read_text(encoding="utf-8")
        seen = {}
        refs = {}
        for m in REF_RE.finditer(text):
            line = text[: m.start()].count("\n") + 1
            refs.setdefault(m.group(1), []).append((line, m.group(2)))

        for m in GLOSS_RE.finditer(text):
            line = text[: m.start()].count("\n") + 1
            attrs, body = m.group(1), m.group(2).strip()
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

            # 5. the gloss and the word it explains must point at each other.
            # Keyed on the id in the attrs, not on the bolded term: the
            # Turkish edition keeps the English id and translates the term.
            id_m = re.search(r"#gloss-([a-z0-9-]+)", attrs)
            if not id_m:
                problems.append(
                    f"{rel}:{line}: '{term}' has no {{#gloss-...}} id, so "
                    f"nothing can link to it")
                continue
            sl = id_m.group(1)
            if sl not in slugs:
                problems.append(
                    f"{rel}:{line}: #gloss-{sl} is not a glossary entry — "
                    f"add it to glossary.csv, or use the entry's id")
            if f"](#term-{sl}){{.term-back}}" not in body:
                problems.append(
                    f"{rel}:{line}: '{term}' has no [↩](#term-{sl})"
                    f"{{.term-back}}, so the reader cannot get back")
            here = refs.pop(sl, [])
            if not here:
                problems.append(
                    f"{rel}:{line}: '{term}' is glossed but never marked in "
                    f"the prose; run scripts/link-glosses.py, or move the "
                    f"gloss to a paragraph that uses the word")
            elif len(here) > 1:
                at = ", ".join(f"line {n}" for n, _ in here)
                problems.append(
                    f"{rel}:{line}: '{term}' is marked {len(here)} times "
                    f"({at}); mark it once, at first use")
            for n, back in here:
                if back != sl:
                    problems.append(
                        f"{rel}:{n}: mark for '{term}' returns to "
                        f"#term-{back}, but the note links to #term-{sl}")

        for sl, here in sorted(refs.items()):
            for n, _ in here:
                problems.append(
                    f"{rel}:{n}: .term-ref points at #gloss-{sl}, which no "
                    f"margin note in this chapter defines")

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
