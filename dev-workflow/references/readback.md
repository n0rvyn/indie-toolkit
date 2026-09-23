# Readback: say back what you understood, when it matters

A readback is a short plain-language restatement of what the user asked, so a misunderstanding surfaces before work is built on it. It is a judgment call, not a checkpoint. A readback that fires when nothing is unclear interrupts the user and teaches them to skip it. A readback that is missing when the request was ambiguous lets both sides build on different pictures.

## When to read back

- The request has two or more reasonable readings, and they lead to different work (which screen, which "that color", fix the symptom or replace the design).
- You are about to do something large, destructive, or hard to undo that the user did not spell out.
- You are adding scope the user did not ask for.
- The user just corrected your understanding. Restate the corrected picture once, so both sides confirm it is now shared.

## When not to

- The instruction is clear and the next step follows from it. Just do the work.
- The user already told this session to run on its own (`/loop`, `/afk`, `/goal`, "你自己跑", "别问我"). Write the readback into your reply as a record and keep going.

## Shape

Three short parts, in the user's own vocabulary:

- **What's happening / what you asked**: the situation in the user's terms.
- **What I'll do**: the approach in plain action verbs.
- **What you'll see when it's done**: an outcome the user can check.

Rules for the wording:

- A technical name is never the subject of a sentence. Write "切到云端模式时，账单导入会先报错（出在 `BillImportService.parse()`）", not "`BillImportService.parse()` 在云端模式下抛错". Code names go in parentheses at the end.
- Reuse the user's words. If they said "账单导入", do not translate it to "Bill Import".
- Mark scope you added on its own line: `⚠️ AI 补充: …`.
- Keep it short. If it runs past a few sentences per part, you are explaining, not restating.

## After the readback

Stop and wait only when the readings really diverge and a wrong guess would waste the work. In every other case, give the readback and continue. A clear request does not need confirmation.
