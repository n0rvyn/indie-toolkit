# Fixture contract — the smallest DESIGN.md N1 can compile a rule from

This file exists so the acceptance gate can prove N1 *sees*: it must fire on
`arms/leaky` and stay silent on `arms/clean`. It is not a real contract.

## Platform Mapping

| Web / CSS (prototype) | SwiftUI (idiomatic) |
|---|---|
| `Spark` / `MiniBars` sparkline chart | **Swift Charts** `Chart` + `LineMark` — never a hand-rolled `Path` |

## Do's and Don'ts

- **Don't** hand-roll charts with `Path`; charts use Swift Charts.
