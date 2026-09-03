#!/usr/bin/env python3
"""Regenerate both editions' glossary tables from glossary.csv.

The book has no executed cells: CI enforces that _freeze/ matches the source,
and contributors may not have Quarto locally, so a render-time cell would be
unbuildable. The tables are therefore generated ahead of time and committed.

    python3 scripts/build-glossary.py            # rewrite both .qmd files
    python3 scripts/build-glossary.py --check    # fail if either is stale
"""

import argparse
import csv
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
CSV_PATH = ROOT / "en" / "appendices" / "glossary.csv"

BEGIN = "<!-- BEGIN GENERATED — edit glossary.csv, then run `make glossary`. -->"
END = "<!-- END GENERATED -->"

COLWIDTHS = ': {tbl-colwidths="[35,35,30]"}'

# The Turkish edition prints the same rows under Turkish headings. The map is
# here rather than in the CSV because the group name is a section title in two
# languages, not a datum about a term.
TR_GROUPS = {
    "Text, tokens, and morphology": "Metin, token'lar ve biçimbilim",
    "Representing text as vectors": "Metni vektör olarak temsil etmek",
    "Models and architecture": "Modeller ve mimari",
    "Modelling, training, and statistics": "Modelleme, eğitim ve istatistik",
    "Language modelling": "Dil modelleme",
    "Prompting and generation": "Promptlama ve üretim",
    "Prompting practice": "Promptlama pratiği",
    "Decoding and structured output": "Çözümleme ve yapılandırılmış çıktı",
    "Retrieval": "Erişim",
    "RAG": "RAG",
    "Retrieval, agents, and tools": "Erişim, ajanlar ve araçlar",
    "Annotation and data quality": "Etiketleme ve veri kalitesi",
    "Sequence labeling and extraction": "Dizi etiketleme ve çıkarım",
    "Summarization and generation": "Özetleme ve üretim",
    "Machine translation": "Makine çevirisi",
    "Turkish and morphology": "Türkçe ve biçimbilim",
    "Evaluation and serving": "Değerlendirme ve servis",
    "Multimodal": "Çok modlu",
    "Evaluation": "Değerlendirme",
    "Agents": "Ajanlar",
}

TARGETS = (
    {
        "path": ROOT / "en" / "appendices" / "c-glossary.qmd",
        "headers": ("English", "Türkçe", "Notes"),
        "group": lambda g: g,
        "notes": "notes",
    },
    {
        "path": ROOT / "tr" / "appendices" / "c-sozluk.qmd",
        "headers": ("İngilizce", "Türkçe", "Notlar"),
        "group": lambda g: TR_GROUPS[g],
        "notes": "notes_tr",
    },
)


def row(cells):
    return "|" + "|".join(f" {c} " if c else " " for c in cells) + "|"


def render(entries, headers, group_name, notes_key):
    out = []
    for group in dict.fromkeys(e["group"] for e in entries):
        out += [f"## {group_name(group)}", "", row(headers), "|---|---|---|"]
        out += [
            row((e["english"], e["turkish"], e[notes_key]))
            for e in entries
            if e["group"] == group
        ]
        out += ["", COLWIDTHS, ""]
    return "\n".join(out[:-1])


def check_order(entries):
    """Groups contiguous, terms alphabetized, and every note translated.

    The Turkish page prints notes_tr, so a term added with an English note
    and no Turkish one would render a blank cell in a published edition
    rather than fail anywhere visible.
    """
    problems = []
    for i, e in enumerate(entries):
        if e["notes"].strip() and not e.get("notes_tr", "").strip():
            problems.append(f"row {i + 2}: {e['english']!r} has no notes_tr")
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
        print(f"{CSV_PATH.name} needs fixing:", file=sys.stderr)
        for p in problems:
            print(f"  {p}", file=sys.stderr)
        return 1

    status = 0
    for target in TARGETS:
        qmd = target["path"]
        current = qmd.read_text(encoding="utf-8")
        try:
            head, rest = current.split(BEGIN)
            _, tail = rest.split(END)
        except ValueError:
            print(f"{qmd.name}: missing BEGIN/END generated markers", file=sys.stderr)
            status = 1
            continue

        body = render(entries, target["headers"], target["group"], target["notes"])
        updated = f"{head}{BEGIN}\n{body}\n\n{END}{tail}"

        if args.check:
            if updated != current:
                print(
                    f"{qmd.name} is stale — run `make glossary` and commit.",
                    file=sys.stderr,
                )
                status = 1
            else:
                print(f"{qmd.name} is up to date ({len(entries)} terms).")
            continue

        if updated == current:
            print(f"{qmd.name} already up to date ({len(entries)} terms).")
            continue

        qmd.write_text(updated, encoding="utf-8")
        print(f"{qmd.name} regenerated ({len(entries)} terms).")
    return status


if __name__ == "__main__":
    sys.exit(main())
