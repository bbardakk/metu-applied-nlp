#!/usr/bin/env python3
"""Measure how hard the English of each chapter actually is.

Most readers of this book are not native English speakers and are not
computer scientists, so the English itself is part of the difficulty, not
just the material. This script makes that measurable instead of a matter
of taste.

Two different problems come out of it, and they need opposite fixes:

  A. Technical terms  -- keep the word, explain it in a margin note.
     `perplexity` is the real name of the thing; a reader has to learn it.
  B. Fancy plain English -- rewrite the word, no explanation needed.
     `estimable` teaches nobody anything that `possible to estimate`
     does not.

Words are scored by Zipf frequency: 7 is *the*, 5 is common, 4 is
ordinary, below about 3.4 a competent non-native reader starts to stumble.
A word is filed under A rather than B if it turns up in code, in maths, or
in the glossary anywhere in the book.

IMPORTANT: the A/B split is advisory. It is a keyword heuristic and it
gets things wrong in both directions -- `matrices` and `backpropagation`
land in B, plain words occasionally land in A. Read the output as a list
of candidates for a human to judge, never as a worklist to apply blindly.
This script is deliberately not wired into `make check`.

Needs wordfreq, which is an authoring tool rather than a build dependency:

    pip install -r requirements-dev.txt

    python3 scripts/check-readability.py           # all chapters
    python3 scripts/check-readability.py 02 06     # only these
"""

import csv
import re
import sys
from collections import Counter
from pathlib import Path

try:
    from wordfreq import zipf_frequency
except ImportError:
    print("this script needs `wordfreq` (pip install wordfreq)",
          file=sys.stderr)
    raise SystemExit(2)

ROOT = Path(__file__).resolve().parent.parent
CHAPTERS = ROOT / "en" / "chapters"
CSV_PATH = ROOT / "en" / "appendices" / "glossary.csv"

HARD = 3.4          # below this, a non-native reader starts to stumble
WORD_RE = re.compile(r"[A-Za-z][A-Za-z'-]{2,}")
CODEISH_RE = re.compile(r"```.*?```|`[^`\n]+`|\$\$.*?\$\$|\$[^$\n]+\$", re.S)

# Stems that mark a word as an inflected form of a domain term even when
# that exact form never appears in code.
DOMAIN_STEMS = (
    "gram", "token", "embed", "corpus", "corpora", "vector", "matri",
    "annotat", "classif", "cluster", "regress", "softmax", "sigmoid",
    "perplex", "smooth", "backoff", "baseline", "dataset", "benchmark",
    "hyperparam", "pretrain", "finetun", "transformer", "attention",
    "neural", "gradient", "entropy", "probab", "distribut", "frequen",
    "logarithm", "denominat", "numerat", "cosine", "vocab", "seman",
)


def prose(text):
    """Strip everything that is not running prose.

    Readers do not struggle with the code listings, the SVG figures or
    the maths; those have their own conventions. Only the sentences count.
    """
    text = re.sub(r"^```.*?^```", " ", text, flags=re.S | re.M)
    text = re.sub(r"\$\$.*?\$\$", " ", text, flags=re.S)
    text = re.sub(r"\$[^$\n]+\$", " ", text)
    text = re.sub(r"`[^`\n]+`", " ", text)
    text = re.sub(r"\[([^\]]*)\]\([^)]*\)", r"\1", text)   # keep link labels
    text = re.sub(r"[@#]sec-[a-z0-9-]+", " ", text)
    text = re.sub(r"@[a-z]+[0-9]{4}[a-z]*", " ", text)
    text = re.sub(r"^:{3,}.*$", " ", text, flags=re.M)
    text = re.sub(r"\{[^}\n]*\}", " ", text)
    text = re.sub(r"^\|.*$", " ", text, flags=re.M)
    text = re.sub(r"^(:|---).*$", " ", text, flags=re.M)
    text = re.sub(r"<[^>\n]+>", " ", text)
    return text


def domain_lexicon():
    """Word forms used as code, maths or terminology anywhere in the book."""
    lex = set()
    for path in (ROOT / "en").rglob("*.qmd"):
        for chunk in CODEISH_RE.findall(path.read_text(encoding="utf-8")):
            lex.update(w.lower() for w in re.findall(r"[A-Za-z_]{3,}", chunk))
    with CSV_PATH.open(encoding="utf-8", newline="") as f:
        for row in csv.DictReader(f):
            lex.update(re.findall(r"[a-z]+", row["english"].lower()))
    return lex


def is_domain(word, lex):
    return word in lex or any(s in word for s in DOMAIN_STEMS)


def main():
    wanted = sys.argv[1:]
    paths = sorted(CHAPTERS.glob("*.qmd"))
    if wanted:
        paths = [p for p in paths if any(p.name.startswith(w) for w in wanted)]
    if not paths:
        print("no chapters matched", file=sys.stderr)
        return 1

    lex = domain_lexicon()
    technical, plain = Counter(), Counter()

    print(f"{'chapter':<30}{'words':>8}{'hard':>7}{'share':>8}")
    total_w = total_h = 0
    for path in paths:
        words = [w.lower().strip("'-")
                 for w in WORD_RE.findall(prose(path.read_text("utf-8")))]
        words = [w for w in words if len(w) > 2]
        hard = 0
        for w in words:
            z = zipf_frequency(w, "en")
            if z == 0 or z >= HARD:
                continue
            hard += 1
            (technical if is_domain(w, lex) else plain)[w] += 1
        total_w += len(words)
        total_h += hard
        share = 100 * hard / len(words) if words else 0
        print(f"{path.name:<30}{len(words):>8,}{hard:>7,}{share:>7.1f}%")
    share = 100 * total_h / total_w if total_w else 0
    print(f"{'TOTAL':<30}{total_w:>8,}{total_h:>7,}{share:>7.1f}%")

    print(f"\ncandidates to REWRITE — plain English that is merely hard "
          f"({len(plain):,} distinct)")
    for word, n in sorted(plain.items(), key=lambda t: (-t[1], t[0]))[:30]:
        print(f"  {word:<22}{n:>4}x  zipf {zipf_frequency(word, 'en'):.1f}")

    print(f"\ncandidates to EXPLAIN — technical terms ({len(technical):,} "
          f"distinct)")
    for word, n in sorted(technical.items(), key=lambda t: -t[1])[:20]:
        print(f"  {word:<22}{n:>4}x")

    print("\nboth lists are advisory: the split is a heuristic and it "
          "misfiles words in both directions.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
