---
type: llm
focus: last_message
weight: 1
---
1. The final message identifies the cause: the settings page writes the nickname straight to DB and skips the cache invalidation that update_profile performs, so get_profile keeps serving the cached copy.
2. It says the avatar change (settings/avatar.py) has the same problem, even though the user only reported the nickname.
PASS only if both are stated.
