# Conventional Commits Reference

Full specification: https://www.conventionalcommits.org/

## Type → Semver Bump Mapping

| Type | Bump | When |
|------|------|------|
| `feat` | minor | New feature |
| `fix` | patch | Bug fix |
| `docs` | patch | Documentation only |
| `refactor` | patch | Code change that neither fixes a bug nor adds a feature |
| `perf` | patch | Performance improvement |
| `test` | patch | Adding or correcting tests |
| `chore` | patch | Build process, auxiliary tools, or dependency updates |
| `feat!` or body contains `BREAKING CHANGE` | major | Breaking change |

## Commit Format

```
type(scope): description

[optional body]

[optional footer]
```

## Scope

Scope should reference the plugin or concern being changed:
- `feat(dev-workflow):`, `fix(apple-dev):`, `docs(mactools):`
- For changes spanning multiple plugins: `chore(release):`, `docs:`

## BREAKING CHANGE

Breaking changes are signaled in two ways:
1. Append `!` to the type: `feat!(pkos): change inbox routing`
2. Add `BREAKING CHANGE:` in the commit body:

```
feat(pkos): change inbox routing to require explicit destination

BREAKING CHANGE: inbox key renamed from `route` to `destination`
```

## auto-version Integration

`.github/workflows/auto-version.yml` detects the highest bump type from commit messages since the last tag and bumps:
- Each changed plugin's `version` in `plugin.json`
- The marketplace `metadata.version` (highest bump among changed plugins)

Commits from `github-actions[bot]` are excluded from bump detection.

## Example Commit Messages

```
feat(domain-intel): add GitHub API rate limit handling
fix(apple-dev): correct SwiftData migration guide for iOS 26
docs: update wechat-bridge README with new auth flow
feat!(pkos): change inbox routing to require explicit destination
chore: bump dependencies across all plugins
refactor(dev-workflow): extract bump detection into reusable function
perf(readback): reduce plugin scan time by caching manifest
test(commit): add audit gate coverage for secret patterns
```
