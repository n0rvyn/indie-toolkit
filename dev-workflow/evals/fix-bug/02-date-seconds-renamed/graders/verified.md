---
type: llm
focus: last_message
weight: 0.5
---
The final message tells the user how the fix was verified, and that verification is concrete:
- It names what was run after the fix (a command, script, or function call) AND states the post-fix output (e.g. the corrected value).
- "It compiles", "should work now", or describing the code change alone does NOT count.
PASS only if both hold.
