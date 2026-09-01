/** Catches the two things most likely to slip past a manual review:
 *  an em dash (the classic AI tell) and an emoji used as an icon. */
import { readdirSync, readFileSync, statSync } from "node:fs";
import { join } from "node:path";

const EM_DASH = /\u2014/;
const EMOJI = /[\u{1F300}-\u{1FAFF}\u{2600}-\u{27BF}]/u;

function walk(dir) {
  return readdirSync(dir).flatMap((name) => {
    const path = join(dir, name);
    return statSync(path).isDirectory() ? walk(path) : [path];
  });
}

const failures = [];
for (const file of walk("src").filter((f) => /\.(tsx?|css)$/.test(f))) {
  readFileSync(file, "utf8")
    .split("\n")
    .forEach((line, index) => {
      if (EM_DASH.test(line)) failures.push(`${file}:${index + 1} em dash`);
      if (EMOJI.test(line)) failures.push(`${file}:${index + 1} emoji`);
    });
}

if (failures.length > 0) {
  console.error("Copy audit failed:\n" + failures.join("\n"));
  process.exit(1);
}
console.log("Copy audit passed.");
