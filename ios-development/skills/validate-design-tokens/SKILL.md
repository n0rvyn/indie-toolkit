---
name: validate-design-tokens
description: Validate SwiftUI code compliance with Design Token standards
---

# Validate Design Tokens Skill

Check SwiftUI code for Design Token compliance.

## Input Parameters

- `filePaths`: List of View files to check

## Validation Rules

### 1. Spacing Compliance

**Search for**:
- `.padding(N)` where N is not 8pt multiple
- `.spacing(N)` where N is not 8pt multiple
- Hardcoded frame sizes

**Valid patterns**:
- `.padding(AppSpacing.md)`
- `.padding(16)`  // 8pt multiple
- `.spacing(AppSpacing.xs)`

**Invalid patterns**:
- `.padding(15)`  // Not 8pt multiple
- `.padding(10)`  // Not 8pt multiple

### 2. Color Compliance

**Search for**:
- `Color(hex:)`
- `Color(red:green:blue:)`
- Hardcoded `Color.blue`, `Color.red` (should use semantic)

**Valid patterns**:
- `Color.appPrimary`
- `Color.appBackground`
- System semantic colors: `Color.primary`, `Color.secondary`

**Invalid patterns**:
- `Color(hex: "#FF0000")`
- `Color.blue`  // Should be `Color.appPrimary` if brand color

### 3. Typography Compliance

**Search for**:
- `.font(.system(size:))`

**Valid patterns**:
- `.font(.body)`
- `.font(.headline)`
- `.font(.largeTitle)`

**Invalid patterns**:
- `.font(.system(size: 17))`  // Should use `.font(.body)`

### 4. Corner Radius Compliance

**Search for**:
- `cornerRadius(N)` where N is hardcoded

**Valid patterns**:
- `.cornerRadius(AppCornerRadius.medium)`
- `.cornerRadius(12)`  // If matches AppCornerRadius.medium

**Invalid patterns**:
- `.cornerRadius(15)`  // Not in standard set

### 5. Shadow Compliance

**Search for**:
- `.shadow(color:radius:x:y:)` with `opacity > 0.08`

**Valid patterns**:
- `.appShadow(.subtle)`
- `.shadow(color: .black.opacity(0.04), ...)`

**Invalid patterns**:
- `.shadow(color: .black.opacity(0.5), ...)`  // Too heavy

## Output Format

```
🔴 Must Fix:
- HomeView.swift:42 - Hardcoded spacing .padding(15)
  Suggestion: Use .padding(AppSpacing.sm)

- CardView.swift:18 - Hardcoded color Color(hex: "#FF0000")
  Suggestion: Define as semantic color Color.appError

🟡 Consider:
- ProfileView.swift:67 - System color Color.blue
  Suggestion: If brand color, use Color.appPrimary

✅ Compliant:
- SettingsView.swift - All spacing uses Design Token
- DashboardView.swift - All colors use semantic tokens
```

## Success Criteria

- All hardcoded spacing/colors/fonts are detected
- Suggestions include exact token names
- Output grouped by severity
