# Scoring & Weighting

> Used by the skill orchestrator to compute weighted totals and compare products. Not needed by individual dimension evaluators.

## Default Weights

All dimensions weighted equally by default:

| Dimension | Default Weight |
|-----------|---------------|
| Demand Authenticity | 1.0 |
| Journey Completeness | 1.0 |
| Market Space | 1.0 |
| Business Viability | 1.0 |
| Moat | 1.0 |
| Execution Quality | 1.0 |

## Weight Presets

**Validation phase** (idea stage, pre-build):
| Dimension | Weight |
|-----------|--------|
| Demand Authenticity | 2.0 |
| Market Space | 1.5 |
| Business Viability | 1.5 |
| Moat | 0.5 |
| Journey Completeness | 0.5 |
| Execution Quality | 0.0 |

**Growth phase** (launched, seeking traction):
| Dimension | Weight |
|-----------|--------|
| Business Viability | 2.0 |
| Moat | 1.5 |
| Demand Authenticity | 1.0 |
| Market Space | 1.0 |
| Journey Completeness | 1.0 |
| Execution Quality | 0.5 |

**Maintenance phase** (established, sustaining):
| Dimension | Weight |
|-----------|--------|
| Execution Quality | 2.0 |
| Moat | 1.5 |
| Business Viability | 1.0 |
| Demand Authenticity | 1.0 |
| Journey Completeness | 1.0 |
| Market Space | 0.5 |

## Weighted Score Formula

```
Weighted Total = Sum(dimension_score * weight) / Sum(weight)
```

Result is a 1.0-5.0 scale. Display as one decimal place (e.g., 3.7).

## Significance Threshold

When comparing products, a weighted total difference <= 0.5 is not meaningful. Mark such pairs as "difference not significant -- compare individual dimensions."

Do not recommend Focus/Maintain/Stop based solely on total score when the gap between two products is <= 0.5.

## Comparison Ranking

When comparing multiple products:
1. Compute weighted total for each product
2. Rank by total score (highest first)
3. Apply significance threshold -- flag pairs within 0.5 of each other
4. Flag any product with a dimension scored <=2 (potential kill criteria trigger)
5. Provide Focus / Maintain / Stop recommendation for each (respecting significance threshold)
