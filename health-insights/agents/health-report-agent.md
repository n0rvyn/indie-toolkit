---
name: health-report-agent
description: |
  Parses体检报告/lab reports (PDF, image, or text) and extracts structured health metrics.
  Compares extracted metrics against personal baselines and writes structured records.

model: sonnet
tools: [Read, Glob, Bash, Write]
color: blue
maxTurns: 25
---

# health-report-agent

Parses uploaded lab/health reports and creates structured vault entries.

## Input

```yaml
input:
  file_path: "/Users/norvyn/Downloads/lab-results-2026-04-09.pdf"
  file_type: "pdf"           # "pdf" | "image" | "text"
  hospital: null              # auto-detected or null
  report_date: null         # auto-detected or null
  vault_dir: "~/Obsidian/HealthVault"
```

## Output

```yaml
output:
  file_path: "reports/2026-04-09和睦家-n.md"
  yaml_written: "reports/2026-04-09和睦家-n.yaml"
  metrics_extracted: 14
  key_findings:
    - "LDL偏高 (+31%)，建议减少饱和脂肪摄入"
    - "空腹血糖正常"
  follow_up_required:
    - date: "2026-07-09"
      item: "LDL复查"
  notion_reports_record_id: "abc123"
  notion_lab_results_record_ids: ["lr1", "lr2"]
```

## Behavior

1. Detect `file_type` from extension if not provided
2. Call `parse_report.py`:
   - PDF: `pdftotext` → extract raw text
   - Image: `tesseract` OCR → extract raw text
   - Text: use directly
3. Send extracted text to Sonnet with structured extraction prompt
4. For each metric extracted:
   - Compare against `baselines/{metric}.yaml`
   - Calculate `deviation_pct` and `trend` string
5. Write `reports/YYYY-MM-DD-{hospital}-{n}.yaml` (structured)
6. Write `reports/YYYY-MM-DD-{hospital}-{n}.md` (human-readable)
7. Sync to Notion:
   - Reports DB (one record per report)
   - Lab Results DB (one record per individual metric)
