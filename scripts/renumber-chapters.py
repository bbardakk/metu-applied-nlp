#!/usr/bin/env python3
"""Keep chapter numbers in step with the outline in _quarto.yml.

The outline in `book: chapters:` is the only place chapter order is decided.
The `NN-` prefix on a filename is a *derived* fact, and so is every "14. bölüm"
that appears in prose next to a link. This script derives both, so that
inserting a chapter in the middle of a part stays a one-line edit instead of a
day of find-and-replace.

    python3 scripts/renumber-chapters.py --check    # CI: fail on drift
    python3 scripts/renumber-chapters.py --dry-run  # show the plan
    python3 scripts/renumber-chapters.py            # rename and rewrite

WHAT IT REWRITES
  1. The files themselves, with `git mv` so history follows the rename.
  2. Every `chapters/NN-slug.qmd|.html` path in any .qmd/.yml/.md/.html of
     either edition — including the tr → en cross-edition links.
  3. A chapter number written inside the *text* of a link that points at that
     chapter: `[17. bölümde](../../en/chapters/17-rag.html)` becomes
     `[20. bölümde](../../en/chapters/20-rag.html)`. The number is only touched
     when it already matches the link target, so prose that merely happens to
     start with a digit is never damaged.

ADDING A CHAPTER
  Give the new file any free two-digit prefix (90-, 91-, … are conventional
  here), list it in _quarto.yml at the position you want, then run this script.
  It assigns the real numbers to everything, new file included.

WHAT IT DELIBERATELY DOES NOT TOUCH
  `@sec-` cross-references. Those are anchors, not numbers, which is why
  renumbering this book is safe at all — check-links.py guards them instead.
"""

import argparse
import re
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
EDITIONS = ("en", "tr")

TEXT_SUFFIXES = {".qmd", ".yml", ".yaml", ".md", ".html"}
SKIP_DIRS = {"_book", "_freeze", ".git", "site", "public",
             "node_modules", ".quarto", "__pycache__"}

CHAPTER_PATH = re.compile(r"chapters/(\d{2})-([a-z0-9-]+)\.qmd")

# One combined pattern, substituted in a single left-to-right pass. That pass
# never re-examines text it has already written, which is what makes a shifting
# rename (14→17 while 17→20) safe: no occurrence can be rewritten twice.
#
# Three shapes, because the book uses all three: a markdown link to a chapter
# (any depth of ../ in front), a path with an explicit chapters/ directory,
# and a bare sibling filename — chapter 1's OJS table links its rows as
# "14-prompting.html", with no directory at all.
REFERENCE = re.compile(
    r"\[(?P<text>[^\]\n]*)\]\("
    r"(?P<pre>[^)\s]*?)(?P<lnum>\d{2})-(?P<lslug>[a-z0-9-]+)"
    r"\.(?P<lext>qmd|html|ipynb)(?P<post>[^)\s]*)\)"
    r"|chapters/(?P<num>\d{2})-(?P<slug>[a-z0-9-]+)\.(?P<ext>qmd|html|ipynb)"
    r"|(?<![\w/.-])(?P<bnum>\d{2})-(?P<bslug>[a-z0-9-]+)\.(?P<bext>qmd|html|ipynb)"
)


def read_outline(edition):
    """Chapter (number, slug) pairs in the order _quarto.yml lists them.

    Parsed line by line rather than with a YAML library on purpose: this file
    is also rewritten in place, and the comments explaining the structure to a
    human editor are worth more than the convenience of a round-trip loader.
    """
    path = ROOT / edition / "_quarto.yml"
    if not path.exists():
        return path, []

    order, inside = [], False
    for line in path.read_text(encoding="utf-8").split("\n"):
        if re.match(r"^  chapters:\s*$", line):
            inside = True
            continue
        if inside and re.match(r"^  \S", line):  # next key at book: depth
            break
        if inside:
            found = CHAPTER_PATH.search(line)
            if found:
                order.append((found.group(1), found.group(2)))
    return path, order


def build_table():
    """slug → (edition, current number, number its position implies)."""
    table, problems = {}, []
    for edition in EDITIONS:
        _, order = read_outline(edition)
        for position, (num, slug) in enumerate(order, 1):
            if slug in table:
                problems.append(
                    f"slug '{slug}' is listed in more than one edition; "
                    f"slugs must be unique so references can be resolved")
                continue
            table[slug] = (edition, num, f"{position:02d}")
    return table, problems


def orphans(table):
    """Chapter files on disk that no _quarto.yml lists — they never render."""
    listed = set(table)
    found = []
    for edition in EDITIONS:
        directory = ROOT / edition / "chapters"
        if not directory.is_dir():
            continue
        for path in sorted(directory.glob("*.qmd")):
            match = re.fullmatch(r"(\d{2})-([a-z0-9-]+)", path.stem)
            if not match:
                found.append(f"{path.relative_to(ROOT)}: name is not NN-slug")
            elif match.group(2) not in listed:
                found.append(
                    f"{path.relative_to(ROOT)}: not listed in "
                    f"{edition}/_quarto.yml, so it never renders")
    return found


def renumber_label(text, old, new):
    """Rewrite a chapter number inside link text, but only if it matches.

    Turkish prose numbers the chapter it links to ("17. bölümde"), English
    sometimes does too ("Chapter 17"). Both have to move with the target. The
    guard is that the number must already equal the link's current chapter, so
    a link whose text starts with an unrelated figure is left untouched.
    """
    old, new = old.lstrip("0"), new.lstrip("0")
    if old == new:
        return text
    text = re.sub(rf"^{old}(?=\.)", new, text)
    text = re.sub(rf"\bChapter {old}\b", f"Chapter {new}", text)
    return text


def rewrite(body, table):
    def target(slug, current):
        entry = table.get(slug)
        return entry[2] if entry else current

    def replace(match):
        if match.group("lslug") is not None:
            slug, old, ext = match.group("lslug", "lnum", "lext")
            new = target(slug, old)
            label = renumber_label(match.group("text"), old, new)
            return (f"[{label}]({match.group('pre')}{new}-{slug}"
                    f".{ext}{match.group('post')})")
        if match.group("slug") is not None:
            slug, old, ext = match.group("slug", "num", "ext")
            return f"chapters/{target(slug, old)}-{slug}.{ext}"
        # A bare "14-prompting.html" carries no directory to confirm it is a
        # chapter at all, so it is only rewritten when the slug is one we
        # know. Anything else is left exactly as found.
        slug, old, ext = match.group("bslug", "bnum", "bext")
        if slug not in table:
            return match.group(0)
        return f"{table[slug][2]}-{slug}.{ext}"

    return REFERENCE.sub(replace, body)


def text_files():
    for path in sorted(ROOT.rglob("*")):
        if (path.is_file() and path.suffix in TEXT_SUFFIXES
                and not SKIP_DIRS & set(path.parts)):
            yield path


def dangling(table):
    """References that name a chapters/ path no edition defines.

    Deliberately limited to references that spell out the chapters/ directory.
    A bare "14-prompting.html" could be any file, and check-links.py already
    resolves those against the filesystem, which is the stronger test.
    """
    known, bad = set(table), []
    for path in text_files():
        for num, line in enumerate(path.read_text(encoding="utf-8").split("\n"), 1):
            for match in REFERENCE.finditer(line):
                if match.group("slug") is not None:
                    slug = match.group("slug")
                elif (match.group("lslug") is not None
                      and match.group("pre").endswith("chapters/")):
                    slug = match.group("lslug")
                else:
                    continue
                if slug not in known:
                    bad.append(f"{path.relative_to(ROOT)}:{num}: "
                               f"chapters/…-{slug} — no such chapter")
    return bad


def git_mv(src, dst):
    result = subprocess.run(["git", "-C", str(ROOT), "mv", str(src), str(dst)],
                            capture_output=True, text=True)
    if result.returncode != 0:
        src.rename(dst)  # not tracked by git yet; a plain rename is correct


def main():
    parser = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    parser.add_argument("--check", action="store_true",
                        help="report drift and exit 1; changes nothing")
    parser.add_argument("--dry-run", action="store_true",
                        help="print the plan without touching anything")
    args = parser.parse_args()

    table, problems = build_table()
    problems += orphans(table) + dangling(table)

    moves = sorted((edition, old, new, slug)
                   for slug, (edition, old, new) in table.items() if old != new)

    if args.check:
        for edition, old, new, slug in moves:
            problems.append(
                f"{edition}/chapters/{old}-{slug}.qmd: _quarto.yml puts this "
                f"chapter at position {int(new)}, so it should be "
                f"{new}-{slug}.qmd")
        if problems:
            print(f"renumber-chapters: {len(problems)} problem(s)\n",
                  file=sys.stderr)
            for problem in problems:
                print(f"  {problem}", file=sys.stderr)
            print("\nrun: python3 scripts/renumber-chapters.py",
                  file=sys.stderr)
            return 1
        print("renumber-chapters: every chapter number matches its position "
              "in _quarto.yml")
        return 0

    # Problems that renumbering cannot fix must not be papered over by it.
    blocking = [p for p in problems if "no such chapter" not in p]
    if blocking:
        print("renumber-chapters: fix these first\n", file=sys.stderr)
        for problem in blocking:
            print(f"  {problem}", file=sys.stderr)
        return 1

    for edition, old, new, slug in moves:
        print(f"  {edition}/chapters/{old}-{slug}.qmd → {new}-{slug}.qmd")

    if args.dry_run:
        print(f"\n{len(moves)} file(s) would move (dry run; nothing changed)")
        return 0

    # Two phases, because a shifting block collides with itself: moving
    # 14 → 17 before 17 → 20 would overwrite a chapter. Parking every mover
    # under a temporary name first makes the order irrelevant.
    for edition, old, _, slug in moves:
        source = ROOT / edition / "chapters" / f"{old}-{slug}.qmd"
        git_mv(source, source.with_name(f"renumbering-{slug}.qmd"))
    for edition, _, new, slug in moves:
        parked = ROOT / edition / "chapters" / f"renumbering-{slug}.qmd"
        git_mv(parked, parked.with_name(f"{new}-{slug}.qmd"))

    # Always run, even when nothing moved: a reference can be stale while every
    # filename is already correct, and that case has to be repairable too.
    touched = 0
    for path in text_files():
        before = path.read_text(encoding="utf-8")
        after = rewrite(before, table)
        if after != before:
            path.write_text(after, encoding="utf-8")
            touched += 1

    if not moves and not touched:
        print("renumber-chapters: already in step with _quarto.yml")
    else:
        print(f"\n{len(moves)} file(s) renamed, {touched} file(s) rewritten")
    return 0


if __name__ == "__main__":
    sys.exit(main())
