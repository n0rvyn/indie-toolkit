#!/usr/bin/env bash
# flow-coverage.sh — the script the FLOW.md contract promises.
#
# `flow-navigation-contract`'s description says completeness is "answered by a script,
# not by an agent's say-so." Until now that script did not exist: the SKILL.md carried
# pseudocode in a fenced block and `handoff-manifest` referenced `{./flow-coverage.sh}`
# as a placeholder. An agent asked "is it done?" answered from its own judgment — which
# is exactly what this contract exists to prevent.
#
#   ./flow-coverage.sh <FLOW.md> <sources-dir>
#
#   exit 0 — gate green
#   exit 1 — gate red: a real defect was found
#   exit 2 — the script could not run (bad input, broken parse, missing detector)
#
# ── The three exit codes are not decoration ──────────────────────────────────────
# A checker that returns "nothing found" when it *failed to look* is worse than no
# checker: its silence reads as a pass. So this script separates "I looked and found
# nothing" (0) from "I found something" (1) from "I could not look" (2), and it proves
# it can see before it reports green:
#
#   * it refuses to run if it parsed 0 nodes out of FLOW.md (an empty node list would
#     make every check below trivially pass);
#   * it treats a non-zero exit from a sub-detector as a *finding*, and a crash of that
#     detector as an *error* — those are different facts;
#   * it never pipes a command into `wc -l` with stderr discarded, because that turns
#     "command failed" into "count = 0".
#
# Portability: no GNU-only syntax. `\b` word boundaries do not exist in BSD sed, and
# `find -newermt '-N seconds'` does not exist outside GNU find. Both silently produce
# empty output on macOS rather than erroring loudly — the exact failure this script is
# written to avoid.

set -uo pipefail

FLOW="${1:-}"
SRC="${2:-}"

die()  { printf '\033[31m✖ %s\033[0m\n' "$*" >&2; exit 2; }
fail() { printf '\033[31m🔴 %s\033[0m\n' "$*"; }
ok()   { printf '\033[32m✓ %s\033[0m\n' "$*"; }
warn() { printf '\033[33m⚠ %s\033[0m\n' "$*"; }
info() { printf '  %s\n' "$*"; }

[ -n "$FLOW" ] && [ -f "$FLOW" ] || die "FLOW.md not found: '${FLOW}'   (usage: $0 <FLOW.md> <sources-dir>)"
[ -n "$SRC" ]  && [ -d "$SRC" ]  || die "sources dir not found: '${SRC}'"

printf '\n\033[1mFLOW coverage\033[0m  %s  ⟶  %s\n' "$FLOW" "$SRC"
printf '%s\n' "──────────────────────────────────────────────────────────────────────"

# ── Parse the node list ──────────────────────────────────────────────────────────
# Node lines:  - { id: today.root, type: screen, a11y: today_root, ..., status: implemented }
NODE_LINES=$(grep -E '^[[:space:]]*-[[:space:]]*\{.*id:' "$FLOW" || true)

# All declared node ids (the edge targets must resolve into this set).
ALL_IDS=$(printf '%s\n' "$NODE_LINES" | sed -nE 's/^.*[{,][[:space:]]*id:[[:space:]]*([A-Za-z0-9_.]+).*$/\1/p' | sort -u)
N_IDS=$(printf '%s\n' "$ALL_IDS" | grep -c . || true)

# The self-check that makes a green gate mean anything.
[ "${N_IDS:-0}" -gt 0 ] || die "parsed 0 node ids out of $FLOW.
   Either the parser is broken or this is not a FLOW contract. An empty node list makes
   every check below pass trivially, so reporting green here would be a lie. Refusing."

N_SCREENS=$(printf '%s\n' "$NODE_LINES" | grep -c 'type:[[:space:]]*screen' || true)
info "parsed $N_IDS node id(s), $N_SCREENS of type screen"

RC=0

# ── 1. Every `status: implemented` node has an implementing view ──────────────────
# The a11y id is the join key — the contract requires it to be present in both the
# graph and the built view, precisely so this can be checked mechanically.
MISSING=0
N_IMPL=0
while IFS= read -r node; do
  [ -n "$node" ] || continue
  case "$node" in *"status: implemented"*) ;; *) continue ;; esac
  N_IMPL=$((N_IMPL + 1))
  id=$(printf '%s\n'   "$node" | sed -nE 's/^.*[{,][[:space:]]*id:[[:space:]]*([A-Za-z0-9_.]+).*$/\1/p')
  a11y=$(printf '%s\n' "$node" | sed -nE 's/^.*[,][[:space:]]*a11y:[[:space:]]*([A-Za-z0-9_]+).*$/\1/p')
  if [ -z "$a11y" ]; then
    fail "node '$id' is status:implemented but declares no a11y id — nothing to join on"
    MISSING=$((MISSING + 1)); continue
  fi
  if ! grep -rq -- "$a11y" "$SRC" 2>/dev/null; then
    fail "node '$id' claims status:implemented, but its a11y id '$a11y' appears nowhere in the sources"
    MISSING=$((MISSING + 1))
  fi
done <<EOF
$NODE_LINES
EOF

if [ "$MISSING" -eq 0 ]; then
  ok "implemented nodes: $N_IMPL/$N_SCREENS — each one's a11y id is present in the sources"
else
  RC=1
fi

# ── 2. FLOW-STUB sentinels ───────────────────────────────────────────────────────
# "not built yet" and "deliberately blank" are different facts. Count them apart, or a
# repo full of intentional placeholders reads as a repo full of unfinished screens.
STUB_HITS=$(grep -rn 'FLOW-STUB' "$SRC" 2>/dev/null | grep -v 'FLOW-INTENTIONAL-STUB' || true)
N_STUB=$(printf '%s\n' "$STUB_HITS" | grep -c . || true)
N_INTENT=$(grep -rl 'FLOW-INTENTIONAL-STUB' "$SRC" 2>/dev/null | grep -c . || true)
if [ "$N_STUB" -eq 0 ]; then
  ok "FLOW-STUB sentinels: 0   (deliberate placeholders: $N_INTENT — excluded by design)"
else
  fail "FLOW-STUB sentinels: $N_STUB — screens still unbuilt"
  printf '%s\n' "$STUB_HITS" | sed 's/^/     /'
  RC=1
fi

# ── 3. Dead edges ────────────────────────────────────────────────────────────────
TARGETS=$(grep -oE '[,{][[:space:]]*to:[[:space:]]*[A-Za-z0-9_.]+' "$FLOW" \
          | sed -nE 's/.*to:[[:space:]]*([A-Za-z0-9_.]+)$/\1/p' | sort -u || true)
N_DEAD=0
while IFS= read -r t; do
  [ -n "$t" ] || continue
  printf '%s\n' "$ALL_IDS" | grep -qx -- "$t" || { fail "dead edge: '→ $t' resolves to no declared node"; N_DEAD=$((N_DEAD + 1)); }
done <<EOF
$TARGETS
EOF
if [ "$N_DEAD" -eq 0 ]; then
  ok "dead edges: 0   ($(printf '%s\n' "$TARGETS" | grep -c .) distinct edge targets, all resolve)"
else
  RC=1
fi

# ── 4. State liveness — the sentinel the contract never asked for ────────────────
# A screen can exist, be reachable, and carry no stub, and still be dead: a @State that
# nothing ever writes renders its default branch forever. Every check above passes on
# it. This one does not.
HERE=$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)
DETECT="$HERE/../../../apple-dev/scripts/design-detectors/n2_dead_state.py"
if [ ! -f "$DETECT" ]; then
  warn "state-liveness check SKIPPED — detector not found at $DETECT"
  info "This is not a pass. The check did not run."
  [ "$RC" -eq 0 ] && RC=2
else
  OUT=$(python3 "$DETECT" --arm "$(cd -- "$SRC/.." && pwd)" 2>&1)
  DRC=$?
  case "$DRC" in
    0) ok "state liveness: every @State / @Published has ≥ 1 write" ;;
    1) fail "state liveness: DEAD-STATE — a property is declared and read but never written"
       printf '%s\n' "$OUT" | sed 's/^/     /'
       RC=1 ;;
    *) warn "state-liveness detector ERRORED (exit $DRC) — this is not a pass, the check did not run"
       printf '%s\n' "$OUT" | sed 's/^/     /'
       [ "$RC" -eq 0 ] && RC=2 ;;
  esac
fi

printf '%s\n' "──────────────────────────────────────────────────────────────────────"
case "$RC" in
  0) printf '\033[32m\033[1mDONE — coverage gate green (decided by this script, not by an agent)\033[0m\n\n' ;;
  1) printf '\033[31m\033[1mNOT DONE — a real defect was found\033[0m\n\n' ;;
  *) printf '\033[33m\033[1mINCONCLUSIVE — a check could not run. This is NOT a pass.\033[0m\n\n' ;;
esac
exit "$RC"
