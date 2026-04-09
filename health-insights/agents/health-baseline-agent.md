---
name: health-baseline-agent
description: |
  Computes and updates personal health baselines from daily vault data.
  First run computes baselines from all available history; subsequent runs do rolling window updates.

model: sonnet
tools: [Read, Glob, Bash, Write]
color: blue
maxTurns: 20
---

# health-baseline-agent

Computes statistical baselines from daily vault data, or updates existing baselines with new data.

## Input

```yaml
input:
  action: "compute"              # "compute" (first ever) or "update" (incremental)
  metric_type: null             # null = all metrics; specific type = single metric
  vault_dir: "~/Obsidian/HealthVault"
```

## Output

```yaml
output:
  action: "update"
  baselines_updated:
    - metric: heart_rate
      status: updated
      data_points: 87
      mean: 63
      p5: 54
      p95: 73
      drift_detected: false
    - metric: hrv_sdnn
      status: updated
      data_points: 82
      mean: 44
      drift_detected: true    # > 10% shift from previous baseline
  errors: []
```

## Behavior

### First Run (`action: compute`)

1. For each metric type in `daily/`:
   - If `len(records) < 30`: skip with `status: insufficient_data`
   - Call `baseline.py --vault-dir <vault> --metric <type> --window-days 90 --save`
   - Write `baselines/{metric}.yaml`

### Incremental Run (`action: update`)

1. For each metric type:
   - Read existing `baselines/{metric}.yaml`
   - Collect new daily files since `computed_at` timestamp
   - Call `baseline.py --vault-dir <vault> --update --baseline baselines/{metric}.yaml --save`
   - Write updated `baselines/{metric}.yaml`
   - If `drift_detected: true`: flag for notification

### Requirements

- `baseline.py` implements rolling window statistics using Welford's online algorithm
- Minimum 30 data points required before computing any baseline
- Baseline file written to `vault/baselines/{metric}.yaml`
