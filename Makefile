# Applied NLP book — local workflow
# Requires: quarto (https://quarto.org), python deps from requirements.txt

.PHONY: preview preview-tr render serve glossary glossary-check check-links check-glossary-use readability check clean

## Rebuild the glossary tables from en/appendices/glossary.csv
glossary:
	python3 scripts/build-glossary.py

## Fail if the glossary tables are out of sync with the CSV
glossary-check:
	python3 scripts/build-glossary.py --check

## Fail on dead @sec- refs, unknown citations, or stale hard-coded chapter links
check-links:
	python3 scripts/check-links.py

## Fail if a margin term-gloss names a term the glossary does not carry
check-glossary-use:
	python3 scripts/check-glossary-use.py

## Report prose difficulty per chapter (advisory — never fails the build)
readability:
	python3 scripts/check-readability.py

## Every fast check CI runs, without the full render
check: glossary-check check-links check-glossary-use

## Live-preview the English edition (auto-reloads on save)
preview:
	quarto preview en

## Live-preview the Turkish edition
preview-tr:
	quarto preview tr

## Render both editions and assemble the combined site into ./site
render:
	quarto render en
	quarto render tr
	rm -rf site && mkdir -p site
	cp -r en/_book site/en
	cp -r tr/_book site/tr
	cp index.html site/index.html
	@echo "→ combined site in ./site (run 'make serve')"

## Serve the assembled site locally at http://localhost:4200
serve:
	python3 -m http.server 4200 -d site

clean:
	rm -rf en/_book tr/_book site public en/.quarto tr/.quarto
