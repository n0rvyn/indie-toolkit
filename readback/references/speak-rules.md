# Speak-Rules — what "plain language" means in readback

## Hard rules (enforced by intent-echoer agent)

1. **Subject must be from user vocabulary OR generic.**
   - ✅ "我们" / "you" / "用户" / "the system" / "this change" / "账单导入"
   - ❌ `BillImportService` / `useEffect()` / `dispatchSync` / `auth.middleware`

2. **Technical names allowed only in trailing parens.**
   - ✅ "切到云端模式时账单导入会先报一个错（出在 `BillImportService.parse()`）"
   - ❌ "BillImportService.parse() 在云端模式下抛错"

3. **Each paragraph ≤ 4 sentences.**

4. **Reuse user's vocabulary verbatim.**
   - User said "账单导入" → output uses "账单导入" (not "Bill Import" / "BillImportService")

5. **AI-added scope MUST be flagged.**
   - Pattern: `⚠️ AI 补充 / AI addition: ...` on its own line
   - Anything the user did not explicitly request that you (the model) think should be added → mark it

## Soft rules (recommended)

- Total output 200-400 characters (3 paragraphs)
- First sentence of each paragraph carries the load — front-load the meaning
- Avoid hedge phrases ("可能" / "应该" / "也许" / "maybe")

## Self-check checklist (agent runs this before returning)

- [ ] Scan each sentence subject. Any technical name? → rewrite.
- [ ] Any paragraph > 4 sentences? → trim.
- [ ] Jargon outside parens? → move to parens or replace with user's word.
- [ ] AI-added scope flagged? → if not flagged, either flag or remove.
