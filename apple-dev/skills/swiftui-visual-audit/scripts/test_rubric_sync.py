#!/usr/bin/env python3
"""Rubric drift test: render-auditor embeds refactoring-ui Part B.

`apple-dev/agents/render-auditor.md` carries its own copy of the Part B rule IDs
(H/S/T/C/D/F), reworded as visible symptoms because the agent sees pixels, not
code. The source of truth is `dev-workflow/references/refactoring-ui.md` Part B.
If a rule is added, renamed or removed there and not here (or the reverse), this
test goes red. Zero IDs on either side is also red, never "clean".

Run: python3 apple-dev/skills/swiftui-visual-audit/scripts/test_rubric_sync.py
"""
import re
import unittest
from pathlib import Path

REPO = Path(__file__).resolve().parents[4]
RUBRIC = REPO / "dev-workflow/references/refactoring-ui.md"
AGENT = REPO / "apple-dev/agents/render-auditor.md"
ID = re.compile(r"\b([HSTCDF][0-9]+)\b")


def part_b(text: str) -> str:
    start = text.index("## Part B")
    end = text.find("\n## Part C", start)
    return text[start:end if end != -1 else None]


class RubricSync(unittest.TestCase):
    def test_ids_match(self):
        src = set(ID.findall(part_b(RUBRIC.read_text())))
        emb = set(ID.findall(AGENT.read_text()))
        self.assertTrue(src, "no rule IDs found in refactoring-ui.md Part B")
        self.assertTrue(emb, "no rule IDs found in render-auditor.md")
        self.assertEqual(
            src, emb,
            f"missing in render-auditor: {sorted(src - emb)}; "
            f"not in Part B: {sorted(emb - src)}",
        )


if __name__ == "__main__":
    unittest.main()
