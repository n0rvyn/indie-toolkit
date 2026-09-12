---
type: llm
focus: last_message
weight: 0.5
---
1. The final message names the cause: legacy_upload is registered for /upload after upload_v2 and replaces it, so the new handler never runs.
2. It mentions the `handler=legacy_upload` log line, either as the evidence or as the reproduced output.
PASS only if both hold.
