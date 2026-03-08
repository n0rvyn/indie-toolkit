# setup-ci-cd Eval

## Trigger Tests
<!-- Prompts that SHOULD trigger this skill -->
- "Set up CI/CD for my iOS project"
- "Configure Fastlane and GitHub Actions"
- "配置自动上传 TestFlight"
- "Automate my build and release process"
- "Set up CI for my Xcode project"

## Negative Trigger Tests
<!-- Prompts that should NOT trigger this skill -->
- "Write a plan"
- "Review my code"
- "Fix this build error"

## Output Assertions
<!-- What must be true in the skill's output -->
- [ ] Output confirms project root and Xcode Scheme name before configuration
- [ ] Output creates fastlane/Fastfile with release lane for TestFlight upload
- [ ] Output creates fastlane/Gemfile with fastlane gem dependency
- [ ] Output configures match for certificate management
- [ ] Output sets up GitHub Actions workflow triggered by tag
- [ ] Output explains required secret configuration (MATCH_PASSWORD, APP_STORE_CONNECT_API_KEY, etc.)

## Redundancy Risk
Baseline comparison: Base model can write CI scripts but lacks project-specific interactive configuration flow
Last tested model: Opus 4.6
Last tested date: 2026-03-08
Verdict: essential
