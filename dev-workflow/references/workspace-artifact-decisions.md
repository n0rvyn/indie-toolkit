# Workspace artifact decisions

Use Git state and evidence from the current task to establish who owns each file, what produced it, and what still needs it. Inspect relevant references and build or test inputs. An extension, age, or size alone does not establish that a file is disposable.

| Decision | Evidence |
| --- | --- |
| Commit | The file is an authorized source change, test, fixture, documentation, configuration, or required release/build input. A binary can be a required input. |
| Ignore | An untracked local file is intended to remain on disk and outside Git. A shared generated output belongs in a narrow project rule. Private or machine-specific material belongs in a local rule. |
| Clean up | An untracked file is a verified one-shot output or a superseded, reproducible binary with no current consumer. Identify the exact file and its producer or replacement before considering removal. Removing it requires cleanup authorization. |
| Preserve | Performance baselines, reproduction inputs, failure evidence, checkpoints, test results needed later, active run artifacts, and files with uncertain ownership, value, or dependencies. |

For example, a throwaway debug log with a known producer can be a cleanup candidate. The only log from a profiling comparison stays available as evidence. An old binary used by a build, fixture, or release remains protected.
