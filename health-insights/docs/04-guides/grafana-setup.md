# Grafana Cloud Setup Guide

## 1. Create Account

1. Go to https://grafana.com/products/cloud/
2. Sign up for free tier (10K metrics, 50GB logs, 14-day retention)
3. Note your Grafana Cloud URL: `https://<your-stack>.grafana.net`

## 2. Add MongoDB Data Source

1. In Grafana: **Connections** > **Add new connection** > search "MongoDB"
2. Install the MongoDB data source plugin if not already present
3. Configure:
   - **Connection string**: same as `MDB_MCP_CONNECTION_STRING` (from `~/.bash_profile`)
   - **Database**: `health`
   - **Auth**: included in connection string (user: `mcp`)
4. Click **Save & Test** — verify "Data source is working"

## 3. Create Dashboard

Create a new dashboard with these 5 panels:

### Panel 1: Heart Rate (7 days)
- Type: Time series
- Query: `health.metrics` where `metadata.metric = "heart_rate"`, last 7 days
- Y-axis: Value (bpm)
- Display: Line, fill below

### Panel 2: HRV Trend (30 days)
- Type: Time series
- Query: `health.metrics` where `metadata.metric = "hrv_sdnn"`, last 30 days
- Y-axis: Value (ms)
- Thresholds: green > 40, yellow 30-40, red < 30

### Panel 3: Sleep Duration Heatmap
- Type: Heatmap
- Query: `health.metrics` where `metadata.metric = "sleep_duration"`, last 90 days
- X-axis: Week
- Y-axis: Day of week
- Color: Hours of sleep

### Panel 4: Baseline Deviation Gauge
- Type: Gauge (repeat for each metric)
- Query: Latest value from `health.metrics` vs `health.baselines` mean
- Display: % deviation, green/yellow/red zones

### Panel 5: Active Alerts
- Type: Stat
- Query: `health.alerts` where `status = "active"`, count
- Color: red if > 0, green if 0

## 4. Configure Alerting

Add alert rules that complement `predict.py`:

| Rule | Condition | For | Severity |
|------|-----------|-----|----------|
| HRV Low | avg(hrv_sdnn, 3d) < baseline * 0.7 | 1h | moderate |
| Resting HR High | last(resting_heart_rate) > baseline * 1.15 | 30m | moderate |
| Sleep Debt | avg(sleep_duration, 5d) < 6 | 1h | mild |

Notification channel: configure webhook to Adam's `/webhooks/grafana` endpoint for WeChat delivery.

## 5. Embed in Notion

For annual report pages, embed Grafana panel links:
- Share panel > Copy embed URL
- Paste in Notion page as bookmark/embed block

## MongoDB Collection Reference

| Collection | Fields | Use |
|-----------|--------|-----|
| `metrics` | timestamp, metadata.metric, value | All time-series panels |
| `baselines` | metric, mean, std, p25, p75 | Deviation gauges |
| `alerts` | status, severity, rule_id, date | Alert stat panel |
