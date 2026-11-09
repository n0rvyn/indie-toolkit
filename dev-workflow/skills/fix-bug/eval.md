# fix-bug Eval

Cases: `evals/fix-bug/` — historical cases 01–09 and current diagnosis/batch contract cases 10–12. For the scaffolded cases, native plugin eval needs `--scaffold --allow-tools Bash Write Edit`; use a zero-dollar load check first. See `evals/fix-bug/FINDINGS.md` for historical limits and current Codex CLI evidence. This file holds no assertions that the cases cover.

The fixture and prompt files can also be exercised by Codex CLI against the current source skill. Codex execution receipts are distinct from native Claude tool-name grader results and from a with/without comparison. Case 12 uses only its local `bin/gh` replacement, which must be selected explicitly or placed first on PATH; it never requires real GitHub credentials.

## Output Assertions
Not observable: interactive, cross-plugin
- [ ] When a reported symptom has two materially different readings, the user resolves the ambiguity before a repair is chosen
- [ ] A large, architectural or design-replacing repair waits for the user's plan approval; it does not treat merely touching multiple files as sufficient reason to plan
- [ ] Swift/Apple repairs load apple-dev:apple-swift-context before source changes

## Live integration
Not observable: host-env, interactive
- [ ] Real GitHub closure uses the authorized issue and repository, reads back its actual state, and requests only missing authorization; synthetic case 12 covers the local decision logic, not this authenticated integration
