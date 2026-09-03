#!/bin/sh
# Print the sanctioned Turkish term for every glossed term in an English chapter.
# Run before translating, so term-ref link text matches glossary.csv.
f="$1"; g="$(dirname "$0")/../en/appendices/glossary.csv"
grep -oE '#gloss-[a-z0-9-]+' "$f" | sed 's/#gloss-//' | sort -u | while read slug; do
  python3 - "$g" "$slug" <<'PY'
import csv, sys, re
g, slug = sys.argv[1], sys.argv[2]
for row in csv.reader(open(g, encoding="utf-8")):
    if len(row) < 3: continue
    if re.sub(r"[^a-z0-9]+", "-", row[1].lower()).strip("-") == slug:
        print(f"  {slug:<28} EN {row[1]:<26} TR {row[2]}"); break
else:
    print(f"  {slug:<28} *** NOT IN GLOSSARY — add it or reuse an existing term ***")
PY
done
