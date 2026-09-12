---
type: llm
focus: {source: file, path: search/box.py}
weight: 1
---
This is the final search/box.py. The search client allows at most 2 queries in any rolling 1000 ms window; beyond that it raises RateLimited (HTTP 429), and three 429s in a minute get the API key banned for 10 minutes.
Question: while a user types one character every 150 ms without stopping, can this code ever send a 3rd query within 1000 ms of the 1st?
Designs that are SAFE: a debounce of >= 500 ms with nothing else; any debounce combined with a throttle enforcing >= 500 ms between queries; any debounce combined with a limiter that counts sends in a rolling 1000 ms window and holds back the 3rd.
Designs that are UNSAFE: a debounce under 500 ms with no throttle or limiter; firing on every keystroke; a leading-edge send with no throttle or limiter.
PASS if the code is safe. If it calls a helper defined in another file, assume the helper does what its name says.
