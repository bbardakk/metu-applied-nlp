#!/usr/bin/env python3
"""Keep the two editions' stylesheets from drifting apart.

The English and Turkish editions are separate Quarto projects, so each
needs its own theme/ directory — Quarto resolves `theme:` relative to the
project root and will not follow a path out of it the way `bibliography:`
does. That leaves the same SCSS duplicated twice, with nothing tying the
copies together.

It drifted. The Turkish copies were missing the whole `.anlp-fig` block:
every hand-authored SVG in the Turkish edition rendered as unstyled black
text at the browser default size, and every [...]{.pro} / [...]{.con}
verdict mark lost its colour. Nothing failed — the pages built fine and
looked wrong, in 11 chapters, for as long as it took a reader to notice.

So: the files must be byte-identical. English is the source of truth
because that is where the design work happens; a change there is copied
across, not reimplemented. If a future edition genuinely needs its own
rule, add it under a body class rather than forking the file.

Exit status is 1 if any pair differs, so `make check` and CI catch it.
"""

from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SOURCE_EDITION = "en"
MIRROR_EDITIONS = ["tr"]
STYLESHEETS = ["custom-light.scss", "custom-dark.scss"]


def main() -> int:
    problems: list[str] = []
    checked = 0

    for name in STYLESHEETS:
        source = ROOT / SOURCE_EDITION / "theme" / name
        if not source.exists():
            problems.append(f"missing source stylesheet: {source.relative_to(ROOT)}")
            continue

        for edition in MIRROR_EDITIONS:
            mirror = ROOT / edition / "theme" / name
            rel = mirror.relative_to(ROOT)

            if not mirror.exists():
                problems.append(f"{rel}: missing (expected a copy of {SOURCE_EDITION}/theme/{name})")
                continue

            checked += 1
            if mirror.read_bytes() == source.read_bytes():
                continue

            src_lines = source.read_text().splitlines()
            dst_lines = mirror.read_text().splitlines()
            only_in_source = set(src_lines) - set(dst_lines)
            # Report the missing selectors, not a full diff: the useful
            # question is "which rules does the mirror not have?"
            selectors = sorted(
                line.strip() for line in only_in_source
                if line.strip().startswith((".", "#", "$")) and "{" in line
            )
            detail = f" — {len(selectors)} rule(s) missing, e.g. {selectors[0]!r}" if selectors else ""
            problems.append(
                f"{rel}: differs from {SOURCE_EDITION}/theme/{name}{detail}\n"
                f"    fix with: cp {SOURCE_EDITION}/theme/{name} {rel}"
            )

    if problems:
        for problem in problems:
            print(f"check-themes: {problem}", file=sys.stderr)
        return 1

    print(f"check-themes: {checked} stylesheet(s) identical across editions")
    return 0


if __name__ == "__main__":
    sys.exit(main())
