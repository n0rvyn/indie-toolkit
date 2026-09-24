# setup-ci-cd — 退役于 2026-09-24

**当初要解决什么**：首次给 iOS 项目配 CI/CD——GitHub Actions 按 conventional commit 自动 bump `MARKETING_VERSION`，Xcode Cloud 的 `ci_post_clone.sh` 设置 build number，外加版本一致性修复。

**为什么退役**：用户一直直接在 Xcode App 里配置 Xcode Cloud，比 skill 直接；GitHub 侧给 Swift 项目做版本 bump 的 CI 不需要。60 天记录内调用 0 次。

- 来源：session_01WHz4QdvADFm4LqjfETYqn5 用户原话「setup这个是用来给 Xcode 配置CICD的，但其实通过 Xcode App直接来配置更直接（我一直在用），如果CC自己可以做得更好则保留，如果它做的是GitHub上配置 Swift类似的CI CD，我觉得直接退」

**当时怎么做的**：检测项目环境 → 修版本一致性 → 选触发分支 → 写 GitHub Actions auto-version workflow 和 `ci_post_clone.sh` → 验证 → 输出 Xcode Cloud 指引。`git show 4583a9f:apple-dev/skills/setup-ci-cd/SKILL.md`

**再做的话要不同在哪**：先问清用户实际在哪配 CI。Xcode Cloud 的配置入口在 Xcode App 里，CC 能多做的只有仓库里的脚本；值不值得一个 skill，要看这部分是否反复出现。

**如果要重做，形态应该是**：reference（`ci_post_clone.sh` 模板 + 版本号规则），挂进 `apple-swift-context` 的 Topic Router，而不是 skill。
