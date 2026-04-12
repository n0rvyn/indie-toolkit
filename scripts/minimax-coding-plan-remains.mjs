#!/usr/bin/env node

import { execFileSync } from "node:child_process";
import path from "node:path";
import process from "node:process";
import { fileURLToPath } from "node:url";

const currentFile = fileURLToPath(import.meta.url);
const currentDir = path.dirname(currentFile);
const target = path.join(
  currentDir,
  "..",
  "minimax-platform",
  "skills",
  "minimax-coding-plan",
  "scripts",
  "minimax-coding-plan.mjs",
);

execFileSync(process.execPath, [target, ...process.argv.slice(2)], {
  stdio: "inherit",
});
