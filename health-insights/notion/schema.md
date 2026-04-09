# Health Insights — Notion Schema

Independent Notion workspace: **Health**

## Database 1: Trends

Purpose: Time-series numeric records for all health metrics.

| Field | Type | Description |
|-------|------|-------------|
| Date | date | Record date |
| Metric Type | select | heart_rate / hrv_sdnn / vo2max / resting_heart_rate / sleep_duration / sleep_quality / step_count / active_energy / basal_energy / distance / vo2max / blood_glucose_fasting / blood_glucose_post / bp_sys / bp_dia / spo2 / resp_rate / body_mass / bmi / body_fat_pct / etc. |
| Value | number | Numeric value |
| Unit | text | bpm / ms / mL/kg/min / hours / kcal / km / mmol/L / mmHg / % / kg |
| Source | select | apple_health_export / icloud_delta / manual_entry / lab_report |
| Notes | text | Brief AI commentary |
| Is Baseline Update | checkbox | True if this record represents a baseline recomputation event |

## Database 2: Alerts

Purpose: Early warning events triggered by the predict agent.

| Field | Type | Description |
|-------|------|-------------|
| Date | date | Alert date |
| Alert Type | select | hrv_low / resting_hr_high / sleep_debt / blood_glucose_high / overtraining / weight_anomaly |
| Severity | select | mild / moderate / severe |
| Triggered By | text | e.g. "HRV 38ms vs baseline 58ms (-34%) for 3 consecutive days" |
| Status | select | active / acknowledged / resolved |
| Action Taken | text | User notes on what they did in response |
| Vault Link | url | Link to `alerts/YYYY-MM-DD-{rule-id}.md` in HealthVault |

## Database 3: Reports

Purpose: Parsed体检报告 / lab reports.

| Field | Type | Description |
|-------|------|-------------|
| Date | date | Date of the report |
| Hospital | text | Institution name |
| Report Type | select | annual / quarterly / specialty / emergency / other |
| Key Metrics | json | Structured JSON of extracted metrics (LDL, fasting glucose, etc.) |
| Status | select | pending_review / reviewed / follow_up_required |
| Follow-up Date | date | If follow-up is required |
| Vault Link | url | Link to `reports/YYYY-MM-DD-{hospital}-{n}.md` in HealthVault |

## Database 4: Lab Results

Purpose: Individual lab test results from reports or manual entry.

| Field | Type | Description |
|-------|------|-------------|
| Date | date | Test date |
| Test Type | select | blood_glucose / lipid_panel / liver_function / thyroid / blood_count / vitamin_d / iron / etc. |
| Subtype | text | Specific metric (e.g. "LDL", "HDL", "HbA1c") |
| Value | number | Numeric value |
| Unit | text | mmol/L / mg/dL / g/dL |
| Reference Range | text | e.g. "0-3.37" |
| Context | select | fasting / post_meal / morning / evening / random |
| Status | select | normal / borderline / abnormal |
| Source | select | manual_entry / lab_report |
| Report ID | text | Link to parent Reports DB record |

## Workspace Pages

```
Health (workspace)
├── Trends 📈
│   ├── [Trends DB]
│   └── Weekly Summary (grouped by week)
├── Alerts 🚨
│   ├── Active Alerts
│   └── Alert History
├── Reports 📋
│   ├── Pending Review
│   └── Follow-up Due
└── Lab Results 🧪
    └── By Test Type
```
