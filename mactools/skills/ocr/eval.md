# ocr Eval

## Trigger Tests
<!-- Prompts that SHOULD trigger this skill -->
- "Extract text from this screenshot"
- "OCR this image"
- "识别图片中的文字"
- "Read text from this scanned PDF"
- "What does this sign say in Chinese?"

## Negative Trigger Tests
<!-- Prompts that should NOT trigger this skill -->
- "Fix this image"
- "Create a new file"
- "Search my files"

## Output Assertions
<!-- What must be true in the skill's output -->
- [ ] Output uses ocr.swift or compiled ocr binary from skills/ocr/scripts/
- [ ] Output compiles ocr.swift to binary on first use via build_ocr.sh
- [ ] Output supports multiple languages (Chinese, English, etc.)
- [ ] Output handles image formats: png, jpg, jpeg, and scanned PDFs
- [ ] Output uses macOS Vision framework for OCR
- [ ] Output returns extracted text with confidence info

## Redundancy Risk
Baseline comparison: Base model cannot process local image files; this skill provides macOS Vision framework OCR
Last tested model: Opus 4.6
Last tested date: 2026-03-08
Verdict: essential
