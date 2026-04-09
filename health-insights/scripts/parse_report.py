#!/usr/bin/env python3
"""
Lab report / 体检报告 parser.
Supports PDF, image (OCR), and plain text formats.
Extracts text and outputs structured context for LLM metric extraction.

Usage:
    python parse_report.py --file <path> --vault-dir <dir> [--type pdf|image|text]
    python parse_report.py --file <path> --output-json <file>   # extract text only
"""

import argparse
import json
import re
import subprocess
import sys
import yaml
from datetime import datetime
from pathlib import Path


def extract_text_from_pdf(filepath: str) -> str:
    """Extract text from PDF using pdftotext."""
    try:
        result = subprocess.run(
            ["pdftotext", "-layout", filepath, "-"],
            capture_output=True, text=True, timeout=60
        )
        if result.returncode != 0:
            return f"[pdftotext error: {result.stderr}]"
        return result.stdout
    except FileNotFoundError:
        return "[Error: pdftotext not found — install poppler: brew install poppler]"
    except Exception as e:
        return f"[Error: {e}]"


def extract_text_from_image(filepath: str) -> str:
    """Extract text from image using tesseract OCR."""
    try:
        result = subprocess.run(
            ["tesseract", filepath, "stdout", "-l", "chi+eng"],
            capture_output=True, text=True, timeout=120
        )
        if result.returncode != 0:
            return f"[tesseract error: {result.stderr}]"
        return result.stdout
    except FileNotFoundError:
        return "[Error: tesseract not found — install: brew install tesseract]"
    except Exception as e:
        return f"[Error: {e}]"


def extract_text_from_file(filepath: str, file_type: str) -> str:
    """Extract raw text from file based on type."""
    if file_type == "pdf":
        return extract_text_from_pdf(filepath)
    elif file_type == "image":
        return extract_text_from_image(filepath)
    elif file_type == "text":
        with open(filepath, "r", errors="ignore") as f:
            return f.read()
    else:
        return "[Error: unknown file type]"


def detect_report_date(text: str) -> str | None:
    """Try to detect report date from text."""
    patterns = [
        r"(\d{4}[-/]\d{1,2}[-/]\d{1,2})",
        r"(\d{4}年\d{1,2}月\d{1,2}日)",
    ]
    for pattern in patterns:
        m = re.search(pattern, text)
        if m:
            date_str = m.group(1)
            try:
                if "年" in date_str:
                    parts = re.findall(r'\d+', date_str)
                    return f"{parts[0]}-{int(parts[1]):02d}-{int(parts[2]):02d}"
                else:
                    return date_str.replace("/", "-")
            except (ValueError, IndexError):
                continue
    return None


def detect_hospital(text: str) -> str | None:
    """Try to detect hospital name from text."""
    hospitals = ["和睦家", "协和", "瑞金", "华山", "中山医院", "第一医院", "人民医院"]
    for h in hospitals:
        if h in text:
            return h
    return None


def build_extraction_prompt(raw_text: str) -> str:
    """Build the LLM metric extraction prompt."""
    return f"""你是一个医疗报告数据提取专家。从以下体检报告文本中提取所有可测量的健康指标。

报告文本：
---
{raw_text[:8000]}
---

请以JSON格式返回，结构如下：
{{
  "metrics": [
    {{
      "name": "指标名称（如：LDL胆固醇）",
      "metric_key": "blood_glucose",
      "value": 数值,
      "unit": "单位（如：mmol/L）",
      "reference_range": "参考范围（如：0-3.37）",
      "status": "normal|low|high|unknown",
      "context": "fasting|post_meal|random|unknown"
    }}
  ],
  "key_findings": ["主要发现列表"],
  "follow_up_required": [
    {{ "item": "复查项目", "reason": "原因" }}
  ],
  "summary": "一句话总结"
}}

如果没有检测到有效指标，返回空的metrics数组。"""


def main():
    parser = argparse.ArgumentParser(description="Parse lab/health reports — extract text and build LLM context")
    parser.add_argument("--file", required=True, help="Report file path")
    parser.add_argument("--vault-dir", help="HealthVault directory (for baseline comparison)")
    parser.add_argument("--type", choices=["pdf", "image", "text"], help="File type (auto-detected from ext if not given)")
    parser.add_argument("--output-json", help="Output JSON file")
    parser.add_argument("--output-context", help="Output LLM context YAML file")
    args = parser.parse_args()

    filepath = Path(args.file).expanduser()
    vault_dir = Path(args.vault_dir).expanduser() if args.vault_dir else None

    # Detect file type
    if args.type:
        file_type = args.type
    else:
        ext = filepath.suffix.lower()
        type_map = {".pdf": "pdf", ".jpg": "image", ".jpeg": "image", ".png": "image", ".txt": "text"}
        file_type = type_map.get(ext, "text")

    print(f"Extracting text from {file_type}: {filepath}", file=sys.stderr)
    raw_text = extract_text_from_file(str(filepath), file_type)

    if raw_text.startswith("[Error"):
        print(raw_text, file=sys.stderr)
        sys.exit(1)

    report_date = detect_report_date(raw_text)
    hospital = detect_hospital(raw_text)
    report_date_str = report_date or datetime.now().strftime("%Y-%m-%d")

    print(f"Report detected: hospital={hospital}, date={report_date}", file=sys.stderr)

    # Build context for LLM
    context = {
        "type": "report",
        "source": "lab_report",
        "date": report_date_str,
        "hospital": hospital,
        "file": str(filepath),
        "generated_at": datetime.now().isoformat(),
        "raw_text_preview": raw_text[:500],
        "extraction_prompt": build_extraction_prompt(raw_text),
    }

    # If vault_dir given, enrich with baseline deviation
    if vault_dir and vault_dir.exists():
        baselines_dir = vault_dir / "baselines"
        if baselines_dir.exists():
            baselines = {}
            for bl_file in baselines_dir.glob("*.yaml"):
                try:
                    content = bl_file.read_text()
                    parts = content.split("---\n")
                    for part in parts:
                        part = part.strip()
                        if not part:
                            continue
                        data = yaml.safe_load(part)
                        if data:
                            baselines[bl_file.stem] = data
                except:
                    continue
            if baselines:
                context["baselines_available"] = list(baselines.keys())

    if args.output_context:
        out_path = Path(args.output_context)
        out_path.parent.mkdir(parents=True, exist_ok=True)
        with open(out_path, "w") as f:
            f.write("---\n")
            yaml.dump(context, f, allow_unicode=True, sort_keys=False)
        print(f"Context written: {out_path}")

    if args.output_json:
        with open(args.output_json, "w") as f:
            json.dump(context, f, ensure_ascii=False, indent=2)
        print(f"JSON written: {args.output_json}")

    if not (args.output_json or args.output_context):
        print(yaml.dump(context, allow_unicode=True, sort_keys=False))


if __name__ == "__main__":
    main()
