---
type: llm
focus: last_message
weight: 1
---
1. The answer explains that DEBOUNCE_MS makes the box wait until typing has paused for 600 ms before sending a query, and only the latest text is sent.
2. It connects the delay to the search client's rate limit (2 queries per second, 429, key ban).
Pointing out other risks in the code is fine. PASS only if both hold.
