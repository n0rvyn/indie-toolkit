---
type: llm
focus: last_message
weight: 1
---
1. The final message tells the user WHY results were slow: the box waits for typing to pause (debounce) so it does not exceed the search service's rate limit (2 per second, 429s, key ban).
2. It either shortens the wait after the last keystroke while staying within that limit, or explains concretely why the wait cannot go lower.
PASS only if both hold.
