# review-before-commit validation

## 2026-11-09: evidence calibration

Added `03-evidence-calibration` to distinguish platform support from repository policy, a static scanner omission from successful runtime dispatch, a conditional fallback failure from the working package path, and a renamed function's real broken consumer.

Verified without model calls:

- The fixture's committed baseline finds `helper` and returns checkout total `6`.
- Its modified state still returns `runtime-ok`, while the scanner returns `[]`.
- The package path succeeds; selecting the machine-specific fallback raises `FileNotFoundError`.
- The unchanged checkout consumer raises `ImportError` after the producer rename.
- The selected eval cases load with the required scaffold and tool grants at a zero-dollar ceiling. Exit 2 is the expected cost-ceiling result, with no case-load errors.
- The existing 13 review contract checks pass; the classifier's Return block is unchanged and the static invocation edge remains present. These checks do not prove model behavior.

The owner authorized one pilot with `--case evidence-calibration --runs 1 --ablation none --scaffold --allow-tools Bash Write Edit --trust-plugin --no-publish --keep-temp`. It stopped before model execution with `Not logged in · Please run /login`, cost `$0.00`, and partial reason `authentication failed`. Its report and aggregate JSON are under `evals/results/2026-11-08T23-29-27-500Z/` (ignored local artifacts). The missing report and zero tool counts are consequences of that startup failure, not measured skill regressions.

Read-only `claude auth status --json` checks inside and outside the filesystem sandbox both returned `loggedIn: false`, `authMethod: none`, `apiProvider: firstParty`. No supported authentication environment variable was present in the calling process. Credentials and login settings were not changed. Behavioral acceptance requires a successful authenticated pilot; no score or improvement claim is supported by this attempt.
