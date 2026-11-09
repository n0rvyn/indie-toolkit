---
type: llm
focus: {source: file, path: .claude/reviews/review-before-commit-2026-11-09-000000.md}
---
Grade the report against this synthetic fixture's actual behavior. PASS only if all four distinctions and their evidence are present:

1. task.json's inline model is supported by the current FixtureHost 1.0 contract in docs/vendor-platform.md. The report identifies a repository-rule violation using CLAUDE.md, and separates it from platform support. Effort is optional under the vendor contract. The stated consequence stays within the demonstrated scope of the local convention.
2. scanner.py changed its recognized spelling from invoke to dispatch, so it omits runner.py's existing invoke("helper"). The report identifies a static scanner limitation, and states the independent runtime result `runtime-ok` as evidence that the helper still runs.
3. launcher.py's package path succeeds (`package-ok`). The machine-specific fallback is evaluated only when package_available=False; it then fails because /opt/fixture-machine-only/packaged.py is absent. The report describes that conditional portability failure and both branch results.
4. pricing.py renamed calculate to calculate_total while checkout.py still imports calculate. The report preserves this as a confirmed high or medium runtime/breaking risk, names the affected consumer, and cites the observed ImportError. It supplies the trigger, consequence and verification status with code locations for its risk entries; any severity correction has an explicit reason.

FAIL if any distinction is absent, the local convention is reported as unsupported platform syntax, the graph omission is called a runtime dispatch failure, every installation is said to fail on the fallback, or the real checkout failure is dismissed as informational. The fixture's task settings and scanner are synthetic; judge against the bundled vendor contract rather than outside platform knowledge.
