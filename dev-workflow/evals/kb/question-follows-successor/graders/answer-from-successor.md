---
type: llm
focus: last_message
---
PASS only if both hold:
1. The answer tells the user to spawn or resolve the system `claude` binary (from PATH or an override variable) as the executable.
2. The answer cites `2026-05-17-sdk-no-longer-bundles-cli` as a source.
