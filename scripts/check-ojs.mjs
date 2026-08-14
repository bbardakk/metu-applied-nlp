#!/usr/bin/env node
// Syntax-check every ```{ojs} cell in the book without needing Quarto.
//
// The widgets are the one part of this book that no other check looks at. A
// mistyped brace does not fail a build anybody sees locally -- it renders as a
// red error box on the published page, and only for the reader. The two ways
// that happens:
//
//   1. A cell that does not parse.
//   2. Two cells on one page defining the same name. OJS names are global per
//      page, so the second definition breaks the first, and the chapters are
//      long enough that a name gets reused by accident.
//
// Observable's dialect is JS plus cell-definition sugar: `name = expr`,
// `viewof name = expr`, `mutable name = expr`, or a bare expression. So strip
// the binding and check that what is left parses as a JS *expression*.
// Wrapping in parentheses is what makes a block-bodied `{...}` cell parse as a
// function body rather than an object literal, which is how Observable reads
// it too.
//
//     node scripts/check-ojs.mjs

import { readdirSync, readFileSync } from "node:fs";
import { dirname, join, relative } from "node:path";
import { fileURLToPath } from "node:url";
import vm from "node:vm";

const ROOT = dirname(dirname(fileURLToPath(import.meta.url)));
const EDITIONS = ["en", "tr"];

const FENCE_RE = /^```+\{ojs[^}]*\}[^\n]*\n([\s\S]*?)^```+[ \t]*$/gm;
// A cell binding at column 0. Continuation lines inside a call or an object
// are indented, so column 0 is what separates a new cell from the same one.
const BIND_RE = /^(?:(viewof|mutable)\s+)?([A-Za-z_$][\w$]*)\s*=(?![=>])([\s\S]*)$/;
const OPTION_RE = /^\s*\/\/\|/;

function chapters() {
  const files = [];
  for (const edition of EDITIONS) {
    const dir = join(ROOT, edition, "chapters");
    let names;
    try {
      names = readdirSync(dir);
    } catch {
      continue;
    }
    for (const name of names.sort()) {
      if (name.endsWith(".qmd")) files.push(join(dir, name));
    }
  }
  return files;
}

/** True for a run of lines carrying no code -- blank, or `//` and `//|`. */
function isBlank(lines) {
  return lines.every((l) => l.trim() === "" || l.trim().startsWith("//"));
}

/**
 * Compile one cell. Returns {name}, plus {line, message} if it does not
 * parse, where `line` is the line in the file, taken from V8's own report.
 */
function compile(lines, startLine, rel) {
  const bind = lines.join("\n").match(BIND_RE);
  // `viewof x` also defines `x`, and that is the name that can collide.
  const name = bind ? bind[2] : null;
  const expr = bind ? bind[3] : lines.join("\n");

  // The prefix stays on the first line, and the body is not reindented or
  // trimmed, so every line keeps the number it has in the file.
  const wrapped = /^\s*\{/.test(expr) ? `(function () ${expr})` : `(${expr})`;

  try {
    new vm.Script(wrapped, { filename: rel, lineOffset: startLine - 1 });
    return { name };
  } catch (e) {
    const at = e.stack.split("\n")[0].match(/:(\d+)$/);
    return {
      name,
      line: at ? Number(at[1]) : startLine,
      message: e.message,
    };
  }
}

/**
 * Split a fence body into cells and compile each.
 *
 * A single ```{ojs} fence may hold several cells -- three `viewof` inputs in a
 * row is the common case -- so a fence is not a cell. Cells are split at
 * column-0 bindings, then each candidate is grown to the next binding until it
 * parses. Growing is what keeps prose inside an html`...` or md`...` literal
 * from being mistaken for a binding: such a split cannot parse on its own, and
 * rejoining is the only reading that can.
 */
function cellsIn(body, fenceLine, rel, problems, names) {
  const lines = body.split("\n").map((l) => (OPTION_RE.test(l) ? "" : l));
  const starts = lines
    .map((l, i) => (i > 0 && BIND_RE.test(l) ? i : -1))
    .filter((i) => i >= 0);

  let count = 0;
  let i = 0;
  while (i < lines.length) {
    const bounds = [...starts.filter((s) => s > i), lines.length];
    let next = null;
    let firstError = null;

    for (const end of bounds) {
      const seg = lines.slice(i, end);
      if (isBlank(seg)) {
        next = { end, result: null };
        break;
      }
      const result = compile(seg, fenceLine + 1 + i, rel);
      if (!result.message) {
        next = { end, result };
        break;
      }
      firstError ??= result;
    }

    if (!next) {
      // Nothing starting here parses, however far it is grown. The tightest
      // candidate is the one that names the actual mistake.
      const which = firstError.name ? `cell '${firstError.name}'` : "ojs cell";
      problems.push(
        `${rel}:${firstError.line}: ${which} does not parse: ` +
          firstError.message,
      );
      i = bounds[0];
      continue;
    }

    if (next.result) {
      count++;
      const name = next.result.name;
      if (name) {
        const line = fenceLine + 1 + i;
        if (names.has(name)) {
          problems.push(
            `${rel}:${line}: cell '${name}' is defined again here ` +
              `(first at line ${names.get(name)}); ojs names are global ` +
              `per page, so the second definition breaks the first`,
          );
        } else {
          names.set(name, line);
        }
      }
    }
    i = next.end;
  }
  return count;
}

function main() {
  const problems = [];
  let cells = 0;
  let named = 0;
  let files = 0;

  for (const path of chapters()) {
    const rel = relative(ROOT, path);
    const src = readFileSync(path, "utf8");
    // Names are page-scoped, so the map resets for every chapter.
    const names = new Map();
    let found = 0;

    for (const m of src.matchAll(FENCE_RE)) {
      const fenceLine = src.slice(0, m.index).split("\n").length;
      found += cellsIn(m[1], fenceLine, rel, problems, names);
    }

    if (found) {
      files++;
      cells += found;
      named += names.size;
    }
  }

  if (problems.length) {
    console.error(`check-ojs: ${problems.length} problem(s)\n`);
    for (const p of problems) console.error(`  ${p}`);
    return 1;
  }

  console.log(
    `check-ojs: ${cells} ojs cells across ${files} chapters parse, ` +
      `${named} named, no duplicates`,
  );
  return 0;
}

process.exit(main());
