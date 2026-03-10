# update-asc-docs Eval

## Trigger Tests
<!-- Prompts that SHOULD trigger this skill -->
- "Update my App Store Connect documents"
- "Audit my code for privacy policy updates"
- "准备 ASC 提交文档"
- "Generate terms of use from my code"
- "Update legal docs for submission"

## Negative Trigger Tests
<!-- Prompts that should NOT trigger this skill -->
- "Review my code"
- "Write a plan"
- "Fix this bug"

## Output Assertions
<!-- What must be true in the skill's output -->
- [ ] Output audits codebase for: data collection (HealthKit, Location, Contacts), permissions (Info.plist), local storage, network requests
- [ ] Output identifies third-party services and SDK integrations
- [ ] Output scans for consent/agree flows in code
- [ ] Output checks subscription code (StoreKit) for terms-of-use
- [ ] Output compares audit results with existing docs and lists differences
- [ ] Output updates 4 documents: privacy-policy.md, terms-of-use.md, support-page.md, market.md
- [ ] Output produces difference report showing what changed and why

## Redundancy Risk
Baseline comparison: Base model cannot systematically audit codebase for privacy frameworks and auto-generate compliant legal documents
Last tested model: Opus 4.6
Last tested date: 2026-03-08
Verdict: essential
