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
| Any type with `!` (e.g., `fix!`, `chore(api)!`) or body contains `BREAKING CHANGE` | major | Breaking change |

Note: `style` is NOT part of this project's type list. The auto-version workflow does not produce a special bump for it (defaults to patch via the catch-all branch in `bump_level()`), so its use is discouraged.

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

Breaking changes are signaled in two ways. **Order matters**: the `!` must come after the optional `(scope)`, not before it — the auto-version regex is `^[a-z]+(\(.+\))?!:` and rejects `<type>!(scope):` form.

1. Append `!` after the type (and after `(scope)` if present): `feat(pkos)!: change inbox routing`
   - With no scope: `fix!: drop deprecated env var support`
2. Add `BREAKING CHANGE:` in the commit body:

```
feat(pkos): change inbox routing to require explicit destination

BREAKING CHANGE: inbox key renamed from `route` to `destination`
```

The `!` form and the `BREAKING CHANGE:` footer can both be used together for emphasis.

## auto-version Integration

`.github/workflows/auto-version.yml` detects the highest bump type from commit messages since the last tag and bumps:
- Each changed plugin's `version` in `plugin.json`
- The marketplace `metadata.version` (highest bump among changed plugins)

Commits from `github-actions[bot]` are excluded from bump detection.

The bump-detection regex in workflow:
- Major trigger: `^[a-z]+(\(.+\))?!:` (any type with `!`, scope optional) OR commit body contains `BREAKING CHANGE`
- Minor trigger: `^feat(\(.+\))?:` (only `feat` produces minor, scope optional)
- Otherwise: patch

## Example Commit Messages

```
feat(domain-intel): add GitHub API rate limit handling
fix(apple-dev): correct SwiftData migration guide for iOS 26
docs: update wechat-bridge README with new auth flow
feat(pkos)!: change inbox routing to require explicit destination
chore: bump dependencies across all plugins
refactor(dev-workflow): extract bump detection into reusable function
perf(readback): reduce plugin scan time by caching manifest
test(commit): add audit gate coverage for secret patterns
fix!: drop Node 16 support (no scope, breaking)
```
