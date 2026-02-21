# Feature Necessity Audit

**Purpose:** "Strip down to what minimum, and the product still works?" -- identify the features one person can realistically maintain.

**Constraint:** Only available for local projects (requires code access). Skip for external evaluations.

## Methodology

1. List all user-facing features (from code analysis, not documentation claims)
2. For each feature, assess:
   - Does it serve the core JTBD? (Yes = must keep)
   - Can it be simplified without losing core value? (Yes = simplify)
   - Would removing it reduce maintenance burden significantly? (Yes = candidate for cutting)
3. Check dependency graph: does cutting feature X break feature Y?

## Output Format

```markdown
## Feature Necessity Audit

| Feature | Verdict | Reasoning |
|---------|---------|-----------|
| [feature name] | Must keep | [why it serves core JTBD] |
| [feature name] | Simplify | [what to simplify + maintenance cost] |
| [feature name] | Cut | [maintenance cost vs. value delivered] |
```
