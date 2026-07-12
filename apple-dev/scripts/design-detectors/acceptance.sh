#!/usr/bin/env bash
# acceptance.sh v2 — the gate on the design-detector toolchain, carried BY this repo.
#
# v1 lived in the experiment repo, hardcoded a worktree path, and needed the run2
# corpus — its 6/6 PASS was machine-local evidence. v1's "wired" predicate was a
# text grep, which is structurally blind to the one failure it existed to prevent:
# an invocation path that does not resolve where the skill actually runs. That
# exact bug (bare `apple-dev/scripts/…` paths, dead in any installed plugin)
# shipped straight through v1.
#
# v2 therefore proves three different things, all from repo contents alone:
#   A. BEHAVIOR   — every code detector fires on the committed known-defective
#                   fixture, stays silent on the known-clean one, and exits 2
#                   (never 0) when it could not look.
#   B. SYNC       — the design-handoff vendored copy is byte-identical to apple-dev's.
#   C. DEPLOYMENT — the command lines are EXTRACTED FROM THE SKILL TEXT VERBATIM
#                   and executed in a simulated install: plugin dir copied to a
#                   temp root, CWD = a foreign scratch project. If text and
#                   behavior drift, this section goes red.
#
# Exit 0 = all green. Exit 1 = something failed. Exit 2 = the gate could not run.
#
# Honest limits, so nobody reads more into a PASS than it proves:
#   · n5/n6 eat renders; their behavior is NOT validated here (needs an image
#     corpus). Here they get existence + reference checks only.
#   · "root-cause closed" checks are schema greps, not behavior validations.
#   · The simulation copies the plugin dir; it does not drive a live Claude session.

set -u

TK="$(cd "$(dirname "$0")/../../.." && pwd)"
DET_AD="$TK/apple-dev/scripts/design-detectors"
DET_DH="$TK/design-handoff/scripts/design-detectors"
FIX="$DET_AD/fixtures"

pass=0; fail=0
red()   { printf '\033[31m%s\033[0m' "$*"; }
green() { printf '\033[32m%s\033[0m' "$*"; }
dim()   { printf '\033[2m%s\033[0m' "$*"; }

say_ok()  { printf '  %s %s\n' "$(green ✓)" "$1"; pass=$((pass+1)); }
say_bad() { printf '  %s %s\n' "$(red ✗)" "$1"; fail=$((fail+1)); }

# expect <want-exit> <label> <cmd...>
expect() {
  local want="$1" label="$2"; shift 2
  "$@" >/dev/null 2>&1
  local got=$?
  if [ "$got" -eq "$want" ]; then say_ok "$label $(dim "(exit $got)")"
  else say_bad "$label — wanted exit $want, got $got"; fi
}

[ -d "$DET_AD" ] || { echo "✖ detectors missing at $DET_AD" >&2; exit 2; }
[ -d "$FIX/arms/leaky" ] || { echo "✖ fixtures missing" >&2; exit 2; }

printf '\n\033[1mA · Detector behavior on committed fixtures\033[0m\n'
EMPTY="$(mktemp -d)"
expect 1 "n1 fires on leaky"            python3 "$DET_AD/n1_paradigm.py" --contract "$FIX/arms/contract" --arm "$FIX/arms/leaky"
expect 0 "n1 silent on clean (icon Path present — false-positive guard)" \
                                        python3 "$DET_AD/n1_paradigm.py" --contract "$FIX/arms/contract" --arm "$FIX/arms/clean"
expect 2 "n1 refuses without --contract" python3 "$DET_AD/n1_paradigm.py" --arm "$FIX/arms/leaky"
expect 2 "n1 refuses an empty target"    python3 "$DET_AD/n1_paradigm.py" --contract "$FIX/arms/contract" --arm "$EMPTY"
expect 1 "n2 fires on leaky"             python3 "$DET_AD/n2_dead_state.py" --arm "$FIX/arms/leaky"
expect 0 "n2 silent on clean"            python3 "$DET_AD/n2_dead_state.py" --arm "$FIX/arms/clean"
expect 2 "n2 refuses without --arm"      python3 "$DET_AD/n2_dead_state.py"
expect 1 "n3 fires on leaky"             python3 "$DET_AD/n3_scaffold_leak.py" --arm "$FIX/arms/leaky"
expect 0 "n3 silent on clean"            python3 "$DET_AD/n3_scaffold_leak.py" --arm "$FIX/arms/clean"
expect 2 "n3 refuses an empty target"    python3 "$DET_AD/n3_scaffold_leak.py" --arm "$EMPTY"
expect 1 "n4 fires on dirty-contract"    python3 "$DET_AD/n4_contract_lint.py" "$FIX/dirty-contract"
expect 0 "n4 silent on clean-contract"   python3 "$DET_AD/n4_contract_lint.py" "$FIX/clean-contract"
expect 2 "n4 refuses a missing dir"      python3 "$DET_AD/n4_contract_lint.py" "$EMPTY/nope"
rmdir "$EMPTY"

printf '\n\033[1mB · Vendored copy in sync (design-handoff ↔ apple-dev)\033[0m\n'
for f in common.py n1_paradigm.py n2_dead_state.py n3_scaffold_leak.py n4_contract_lint.py; do
  if cmp -s "$DET_AD/$f" "$DET_DH/$f"; then say_ok "byte-identical: $f"
  else say_bad "copies differ: $f — re-sync design-handoff/scripts/design-detectors/"; fi
done

printf '\n\033[1mC · Deployment simulation — commands taken from the skill text, run from a foreign CWD\033[0m\n'
SIM="$(mktemp -d)"; PROJ="$SIM/scratch-project"; mkdir -p "$PROJ"

# C1: handoff-manifest Step 1b, design-handoff plugin root.
cp -R "$TK/design-handoff" "$SIM/dh-root"
MANIFEST="$SIM/dh-root/skills/handoff-manifest/SKILL.md"
LINE="$(grep -m1 -F 'python3 "${CLAUDE_PLUGIN_ROOT}/scripts/design-detectors/n4_contract_lint.py"' "$MANIFEST" || true)"
if [ -z "$LINE" ]; then
  say_bad "handoff-manifest Step 1b: documented n4 command line not found in skill text"
else
  export CLAUDE_PLUGIN_ROOT="$SIM/dh-root"
  ( cd "$PROJ" && eval "${LINE/<contract-dir>/$FIX/dirty-contract}" >/dev/null 2>&1 ); c_dirty=$?
  ( cd "$PROJ" && eval "${LINE/<contract-dir>/$FIX/clean-contract}" >/dev/null 2>&1 ); c_clean=$?
  [ "$c_dirty" -eq 1 ] && say_ok "Step 1b line, verbatim, foreign CWD: dirty → exit 1" \
                       || say_bad "Step 1b verbatim on dirty: wanted 1, got $c_dirty"
  [ "$c_clean" -eq 0 ] && say_ok "Step 1b line, verbatim, foreign CWD: clean → exit 0" \
                       || say_bad "Step 1b verbatim on clean: wanted 0, got $c_clean"
  unset CLAUDE_PLUGIN_ROOT
fi

# C2: design-parity-build Step 0, apple-dev plugin root. DET line + n1 line, verbatim.
cp -R "$TK/apple-dev" "$SIM/ad-root"
PARITY="$SIM/ad-root/skills/design-parity-build/SKILL.md"
DET_LINE="$(grep -m1 '^DET="\${CLAUDE_PLUGIN_ROOT}' "$PARITY" || true)"
N1_LINE="$(grep -m1 'n1_paradigm\.py.*--contract <contract-dir> --arm <target>' "$PARITY" || true)"
if [ -z "$DET_LINE" ] || [ -z "$N1_LINE" ]; then
  say_bad "design-parity-build Step 0: documented DET/n1 lines not found in skill text"
else
  export CLAUDE_PLUGIN_ROOT="$SIM/ad-root"
  N1_CMD="${N1_LINE/<contract-dir>/$FIX/arms/contract}"
  ( cd "$PROJ" && eval "$DET_LINE" && eval "${N1_CMD/<target>/$FIX/arms/leaky}" >/dev/null 2>&1 ); c_leaky=$?
  ( cd "$PROJ" && eval "$DET_LINE" && eval "${N1_CMD/<target>/$FIX/arms/clean}" >/dev/null 2>&1 ); c_clean=$?
  [ "$c_leaky" -eq 1 ] && say_ok "Step 0 DET+n1 lines, verbatim, foreign CWD: leaky → exit 1" \
                       || say_bad "Step 0 verbatim on leaky: wanted 1, got $c_leaky"
  [ "$c_clean" -eq 0 ] && say_ok "Step 0 DET+n1 lines, verbatim, foreign CWD: clean → exit 0" \
                       || say_bad "Step 0 verbatim on clean: wanted 0, got $c_clean"
  unset CLAUDE_PLUGIN_ROOT
fi

# C3: the vendored-gates path a handed-off PROJECT keeps forever (Step 2a + Done-gate).
export CLAUDE_PLUGIN_ROOT="$SIM/dh-root"
( cd "$PROJ" && mkdir -p scripts/design-gates && \
  cp "$CLAUDE_PLUGIN_ROOT"/scripts/design-detectors/{common.py,n1_paradigm.py,n2_dead_state.py,n3_scaffold_leak.py,n4_contract_lint.py} scripts/design-gates/ )
unset CLAUDE_PLUGIN_ROOT
GATE_LINE="$(grep -m1 -oE 'python3 scripts/design-gates/n4_contract_lint\.py <contract-dir>' "$MANIFEST" || true)"
if [ -z "$GATE_LINE" ]; then
  say_bad "Build Contract Done-gate: project-local n4 line not found in skill text"
else
  ( cd "$PROJ" && eval "${GATE_LINE/<contract-dir>/$FIX/dirty-contract}" >/dev/null 2>&1 ); c_dirty=$?
  [ "$c_dirty" -eq 1 ] && say_ok "vendored Done-gate line, verbatim, project CWD, NO plugin root set: dirty → exit 1" \
                       || say_bad "vendored Done-gate on dirty: wanted 1, got $c_dirty"
fi
rm -rf "$SIM"

printf '\n\033[1mD · Wires (repo greps — v1 checks, kept)\033[0m\n'
w() { if eval "$2"; then say_ok "$1"; else say_bad "$1"; fi }
w "design-drift-auditor extracts from ## Build Contract" \
  "grep -q '## Build Contract' '$TK/dev-workflow/agents/design-drift-auditor.md'"
w "ui-reviewer reads design-rules.md" \
  "grep -q 'design-rules.md' '$TK/apple-dev/agents/ui-reviewer.md'"
w "flow-tracer has field-never-written" \
  "grep -q 'field-never-written' '$TK/dev-workflow/agents/flow-tracer.md'"
w "flow-coverage.sh exists and is executable" \
  "[ -x '$TK/design-handoff/skills/flow-navigation-contract/flow-coverage.sh' ]"
w "no phantom 'run-phase auto-routes' claims" \
  "! grep -qE '^\s*-.*\(run-phase auto-routes\)' '$TK/apple-dev/skills/generate-design-system/SKILL.md'"
w "F1 regression guard: zero bare 'python3 apple-dev/scripts' invocations anywhere" \
  "! grep -rq 'python3 apple-dev/scripts' '$TK/apple-dev' '$TK/dev-workflow' '$TK/design-handoff' --include='*.md'"

printf '\n\033[1mE · Root-cause closed — schema greps, NOT behavior validations\033[0m\n'
w "materials tint is light+dark paired in the contract schema" \
  "grep -q 'dark:' '$TK/design-handoff/skills/design-spec-contract/SKILL.md'"
w "## Screen Composition is in the enforced section order" \
  "grep -q '## Screen Composition' '$TK/design-handoff/skills/design-spec-contract/SKILL.md'"
w "generate-design-system emits appGlassTint (D3 upstream root cause)" \
  "grep -q 'appGlassTint' '$TK/apple-dev/skills/generate-design-system/SKILL.md'"
w "n5/n6 exist + are referenced (behavior NOT validated here — needs a render corpus)" \
  "[ -f '$DET_AD/n5_block_layout.py' ] && [ -f '$DET_AD/n6_surface_color.py' ] && grep -rq 'n5_block_layout' '$TK/apple-dev/skills' && grep -rq 'n6_surface_color' '$TK/apple-dev/skills'"

printf '\n────────────────────────────────────────────────────────────\n'
if [ "$fail" -eq 0 ]; then
  printf '\033[32m\033[1mPASS — %d checks green\033[0m\n\n' "$pass"
  exit 0
fi
printf '\033[31m\033[1mFAIL — %d green · %d red\033[0m\n\n' "$pass" "$fail"
exit 1
