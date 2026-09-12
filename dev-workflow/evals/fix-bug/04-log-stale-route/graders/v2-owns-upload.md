---
type: llm
focus: {source: file, path: server.py}
weight: 1
---
This is the final server.py. `register(path, handler)` stores handler in a dict, so a later registration for the same path replaces an earlier one. upload_v2 straightens photos; legacy_upload does not.
PASS if, after this file's registrations run, "/upload" maps to upload_v2 (legacy_upload is no longer registered for "/upload").
FAIL if legacy_upload is still the last handler registered for "/upload".
