#!/usr/bin/env node

import fs from "node:fs";
import os from "node:os";
import path from "node:path";
import process from "node:process";
import { execFileSync } from "node:child_process";

const DEFAULT_URL =
  "https://www.minimaxi.com/v1/api/openplatform/coding_plan/remains";
const DEFAULT_COOKIE_FILE = path.join(
  os.homedir(),
  ".config",
  "minimax",
  "hertz-session.txt",
);

function main() {
  const args = parseArgs(process.argv.slice(2));
  const groupId = args.groupId ?? process.env.MINIMAX_GROUP_ID;

  if (!groupId) {
    fail(
      "MINIMAX_GROUP_ID is required. Pass --group-id or set MINIMAX_GROUP_ID.",
    );
  }

  const cookieFile =
    args.cookieFile ?? process.env.MINIMAX_COOKIE_FILE ?? DEFAULT_COOKIE_FILE;
  const sessionCommand = process.env.MINIMAX_SESSION_COMMAND;
  const outputJson = args.json || process.env.MINIMAX_OUTPUT === "json";

  let session =
    args.session ?? process.env.MINIMAX_HERTZ_SESSION ?? readSession(cookieFile);
  let sessionSource = session ? "env-or-file" : "missing";

  if (!session && sessionCommand) {
    session = runSessionCommand(sessionCommand);
    sessionSource = "session-command";
    saveSession(cookieFile, session);
  }

  if (!session) {
    fail(
      [
        "No MiniMax session found.",
        `Set MINIMAX_HERTZ_SESSION, or write HERTZ-SESSION to ${cookieFile}.`,
        "Optional: set MINIMAX_SESSION_COMMAND to a command that prints a fresh session.",
      ].join("\n"),
    );
  }

  let payload = fetchRemains(groupId, session);

  if (isMissingCookie(payload) && sessionCommand) {
    const refreshed = runSessionCommand(sessionCommand);
    if (!refreshed) {
      fail("MINIMAX_SESSION_COMMAND ran but did not return HERTZ-SESSION.");
    }

    session = refreshed;
    sessionSource = "session-command";
    saveSession(cookieFile, session);
    payload = fetchRemains(groupId, session);
  }

  if (isMissingCookie(payload)) {
    fail(
      [
        "MiniMax session is invalid.",
        "Server returned: cookie is missing, log in again.",
        "Refresh HERTZ-SESSION in your env or cookie file.",
      ].join("\n"),
      2,
    );
  }

  if (!isSuccess(payload)) {
    fail(`MiniMax returned non-success payload:\n${safeJson(payload)}`, 3);
  }

  if (outputJson) {
    process.stdout.write(`${safeJson(payload)}\n`);
    return;
  }

  printSummary(groupId, payload);
}

function parseArgs(argv) {
  const args = {
    groupId: undefined,
    cookieFile: undefined,
    session: undefined,
    json: false,
  };

  for (let index = 0; index < argv.length; index += 1) {
    const value = argv[index];

    if (value === "--group-id") {
      args.groupId = argv[index + 1];
      index += 1;
      continue;
    }

    if (value === "--cookie-file") {
      args.cookieFile = argv[index + 1];
      index += 1;
      continue;
    }

    if (value === "--session") {
      args.session = argv[index + 1];
      index += 1;
      continue;
    }

    if (value === "--json") {
      args.json = true;
      continue;
    }

    if (value === "--help" || value === "-h") {
      printHelp();
      process.exit(0);
    }

    fail(`Unknown argument: ${value}`);
  }

  return args;
}

function printHelp() {
  process.stdout.write(
    [
      "Usage: minimax-coding-plan.mjs [options]",
      "",
      "Options:",
      "  --group-id <id>      Override MINIMAX_GROUP_ID",
      "  --cookie-file <path> Override MINIMAX_COOKIE_FILE",
      "  --session <value>    Override MINIMAX_HERTZ_SESSION",
      "  --json               Print raw JSON response",
      "",
      "Environment:",
      "  MINIMAX_GROUP_ID         Required when --group-id is omitted",
      "  MINIMAX_HERTZ_SESSION    Browser session cookie value",
      "  MINIMAX_COOKIE_FILE      File containing HERTZ-SESSION",
      "  MINIMAX_SESSION_COMMAND  Command that prints a fresh HERTZ-SESSION",
      "  MINIMAX_OUTPUT=json      Same as --json",
    ].join("\n"),
  );
}

function fetchRemains(groupId, session) {
  const url = new URL(DEFAULT_URL);
  url.searchParams.set("GroupId", groupId);

  const command = [
    "-sS",
    "-m",
    "15",
    url.toString(),
    "-H",
    "accept: application/json, text/plain, */*",
    "-H",
    "origin: https://platform.minimaxi.com",
    "-H",
    "referer: https://platform.minimaxi.com/",
    "-H",
    "user-agent: Mozilla/5.0",
    "-b",
    `HERTZ-SESSION=${session}`,
  ];

  let raw;
  try {
    raw = execFileSync("curl", command, {
      encoding: "utf8",
      stdio: ["ignore", "pipe", "pipe"],
    });
  } catch (error) {
    const stderr = error.stderr ? String(error.stderr).trim() : "";
    fail(
      [
        "Failed to reach MiniMax remains endpoint.",
        stderr || String(error.message ?? error),
        "Check network, proxy, or DNS. The request has a 15s timeout.",
      ].join("\n"),
      5,
    );
  }

  try {
    return JSON.parse(raw);
  } catch (error) {
    fail(
      `Failed to parse MiniMax response as JSON.\n${String(error)}\n${raw}`,
      4,
    );
  }
}

function readSession(cookieFile) {
  try {
    const raw = fs.readFileSync(cookieFile, "utf8").trim();
    return extractSession(raw);
  } catch {
    return undefined;
  }
}

function saveSession(cookieFile, session) {
  fs.mkdirSync(path.dirname(cookieFile), { recursive: true });
  fs.writeFileSync(cookieFile, `HERTZ-SESSION=${session}\n`, "utf8");
}

function runSessionCommand(command) {
  const raw = execFileSync("/bin/zsh", ["-lc", command], {
    encoding: "utf8",
    stdio: ["ignore", "pipe", "pipe"],
  }).trim();

  return extractSession(raw);
}

function extractSession(raw) {
  if (!raw) {
    return undefined;
  }

  const direct = raw.match(/(?:^|[;\s])HERTZ-SESSION=([^;\r\n]+)/);
  if (direct) {
    return direct[1];
  }

  const netscape = raw
    .split(/\r?\n/)
    .map((line) => line.trim())
    .filter(Boolean)
    .find((line) => {
      const columns = line.split("\t");
      return columns.length >= 7 && columns[5] === "HERTZ-SESSION";
    });

  if (netscape) {
    return netscape.split("\t")[6];
  }

  if (!raw.includes("=") && !raw.includes("\t") && !raw.includes(" ")) {
    return raw;
  }

  return undefined;
}

function isMissingCookie(payload) {
  return payload?.base_resp?.status_code === 1004;
}

function isSuccess(payload) {
  return payload?.base_resp?.status_code === 0;
}

function printSummary(groupId, payload) {
  const rows = Array.isArray(payload.model_remains) ? payload.model_remains : [];
  const relevant = [...rows].sort(
    (left, right) => modelRank(left.model_name) - modelRank(right.model_name),
  );

  process.stdout.write(`MiniMax coding plan remains for GroupId ${groupId}\n`);
  process.stdout.write("model\tinterval\tweekly\n");

  for (const row of relevant) {
    const interval = `${row.current_interval_usage_count}/${row.current_interval_total_count}`;
    const weekly = `${row.current_weekly_usage_count}/${row.current_weekly_total_count}`;
    process.stdout.write(`${row.model_name}\t${interval}\t${weekly}\n`);
  }
}

function modelRank(modelName) {
  if (typeof modelName !== "string") {
    return 9;
  }

  if (modelName.startsWith("coding-plan")) {
    return 0;
  }

  if (modelName.startsWith("MiniMax-M")) {
    return 1;
  }

  return 2;
}

function safeJson(value) {
  return JSON.stringify(value, null, 2);
}

function fail(message, code = 1) {
  process.stderr.write(`${message}\n`);
  process.exit(code);
}

main();
