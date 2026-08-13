#!/usr/bin/env python3
"""One-off: wire every margin term-gloss to the word it explains.

A margin note is only useful if the reader can see which word it belongs
to. This rewrites each gloss into an anchored pair:

    the [chain rule](#gloss-chain-rule){#term-chain-rule .term-ref} lets you

    ::: {#gloss-chain-rule .column-margin .term-gloss}
    **chain rule** -- ... [/](#term-chain-rule){.term-back}
    :::

so the term is visibly marked in the text, clicking it jumps to the note,
and the arrow in the note jumps back to where you were reading.

The anchor word is found in the prose next to the gloss. Anything inside
code spans, existing links, maths or table rows is off limits, and a gloss
whose term cannot be found safely is reported rather than guessed at.

    python3 scripts/link-glosses.py --dry-run
    python3 scripts/link-glosses.py --apply
"""

import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent

# A margin note floats beside the text that follows it, so the word it
# explains is much more likely to be below the note than above it.
# Both are counted in lines of prose, not lines of file.
FWD = 18
BACK = 5

GLOSS_OPEN = re.compile(r"^(:::+)\s*\{([^}]*\.term-gloss[^}]*)\}\s*$")
FENCE = re.compile(r"^(```|~~~)")
LEAD = re.compile(r"\*\*(.+?)\*\*")


def slug(term):
    s = term.lower()
    s = s.replace("&", " and ")
    s = re.sub(r"[^a-z0-9]+", "-", s)
    return s.strip("-")


# Head nouns a glossary entry carries for precision but prose drops:
# "held-out data" is written as "held-out reviews", "maximum likelihood
# estimation" as "the maximum-likelihood model".
GENERIC_TAIL = {"data", "set", "estimation", "score", "model"}


def variants(term):
    """Every way the prose might name this term, longest first."""
    vs = {term}
    m = re.match(r"^(.*?)\s*\(([^)]+)\)\s*$", term)
    if m:
        vs |= {m.group(1), m.group(2)}
    for v in list(vs):
        vs |= {p.strip() for p in v.split("/") if p.strip()}
    for v in list(vs):
        w = v.split()
        if len(w) > 1 and w[-1].lower() in GENERIC_TAIL:
            vs.add(" ".join(w[:-1]))
    return sorted({v for v in vs if v}, key=len, reverse=True)


def term_pattern(v):
    """Match the term allowing a hyphen wherever it is written with a space."""
    return re.compile(r"\b" + re.escape(v).replace(r"\ ", r"[\s\-]")
                      + r"(?:s|es)?\b", re.I)


def masked_spans(line):
    """Character ranges that must not be touched: code, links, maths."""
    spans = []
    # `[text]{.hl}` is already carrying a different signal, and wrapping a
    # link round it would nest the brackets, so it is off limits too.
    for pat in (r"`[^`]*`", r"\[[^\]]*\]\([^)]*\)", r"\[[^\]]*\]\{[^}]*\}",
                r"\$[^$]*\$", r"\{[^}]*\}", r"<[^>]*>"):
        spans += [m.span() for m in re.finditer(pat, line)]
    return spans


def find_anchor(lines, prose, lo, hi, term):
    """Return (line_index, match) for the best place to mark the term.

    A margin note floats beside the text that *follows* it, so the search
    runs forward first and only then looks back. Headings are never used --
    a link inside one collides with Quarto's own anchor and the contents
    list -- and table cells are a last resort.

    The window is measured in lines the reader actually reads, so a code
    block or a second gloss sitting between the note and its term does not
    push the term out of range.
    """
    def reach(rng, budget):
        out = []
        for i in rng:
            if prose[i] and lines[i].strip():
                out.append(i)
                if len(out) == budget:
                    break
        return out

    order = reach(range(hi + 1, len(lines)), FWD) + \
            reach(range(lo - 1, -1, -1), BACK)

    def scan(allow_table):
        for v in variants(term):
            pat = term_pattern(v)
            for i in order:
                if not prose[i]:
                    continue
                line = lines[i]
                stripped = line.lstrip()
                # A heading owns Quarto's own anchor, and a table caption is
                # not somewhere a reader looks for a definition.
                if stripped.startswith(("#", ":::", ": ")):
                    continue
                if stripped.startswith("|") != allow_table:
                    continue
                for m in pat.finditer(line):
                    if any(a <= m.start() < b for a, b in masked_spans(line)):
                        continue
                    return i, m
        return None, None

    i, m = scan(allow_table=False)
    if i is None:
        i, m = scan(allow_table=True)
    return i, m


def classify(lines):
    prose = [False] * len(lines)
    incode = ingloss = infm = False
    for i, l in enumerate(lines):
        s = l.strip()
        if i == 0 and s == "---":
            infm = True
            continue
        if infm:
            if s == "---":
                infm = False
            continue
        if FENCE.match(s):
            incode = not incode
            continue
        if incode:
            continue
        if GLOSS_OPEN.match(s):
            ingloss = True
            continue
        if ingloss:
            if re.match(r"^:::+\s*$", s):
                ingloss = False
            continue
        if s.startswith(("<", "aria-label")):
            continue
        prose[i] = True
    return prose


def gloss_blocks(lines):
    """(open_idx, close_idx, attrs) for every .term-gloss div."""
    out = []
    incode = False
    i = 0
    while i < len(lines):
        s = lines[i].strip()
        if FENCE.match(s):
            incode = not incode
        elif not incode:
            m = GLOSS_OPEN.match(s)
            if m:
                for j in range(i + 1, len(lines)):
                    if re.match(r"^:::+\s*$", lines[j].strip()):
                        out.append((i, j, m.group(2)))
                        i = j
                        break
        i += 1
    return out


def main():
    apply = "--apply" in sys.argv
    total = failed = 0
    for path in sorted((ROOT / "en" / "chapters").glob("0[1-6]*.qmd")):
        lines = path.read_text(encoding="utf-8").split("\n")
        prose = classify(lines)
        edits = []
        for lo, hi, attrs in gloss_blocks(lines):
            body = "\n".join(lines[lo + 1:hi])
            lead = LEAD.search(body)
            if not lead:
                continue
            term = lead.group(1).strip()
            total += 1
            if "#gloss-" in attrs:
                continue  # already wired; a second pass would double-link
            sl = slug(term)
            i, m = find_anchor(lines, prose, lo, hi, term)
            if i is None:
                print(f"  !! {path.name}: no safe anchor for {term!r}")
                failed += 1
                continue
            edits.append((lo, hi, attrs, sl, i, m))
            print(f"  {path.name:<24} {term:<34} -> L{i+1}: "
                  f"...{lines[i][max(0,m.start()-28):m.end()+22].strip()}...")

        if not apply:
            continue

        # Apply back to front so earlier line numbers stay valid.
        for lo, hi, attrs, sl, i, m in sorted(edits, key=lambda e: -e[4]):
            line = lines[i]
            lines[i] = (line[:m.start()]
                        + f"[{m.group(0)}](#gloss-{sl})"
                          f"{{#term-{sl} .term-ref}}"
                        + line[m.end():])
        for lo, hi, attrs, sl, i, m in sorted(edits, key=lambda e: -e[0]):
            if "#" not in attrs:
                lines[lo] = f"::: {{#gloss-{sl} {attrs.strip()}}}"
            lines[hi - 1] = (lines[hi - 1].rstrip()
                             + f" [↩](#term-{sl}){{.term-back}}")
        path.write_text("\n".join(lines), encoding="utf-8")

    print(f"\n{total} glosses, {failed} without a safe anchor"
          f"{' — nothing written (dry run)' if not apply else ' — written'}")
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
