#!/usr/bin/env python3
"""Fixture tests for project_health_scan.py."""

from __future__ import annotations

import json
import pathlib
import subprocess
import sys
import tempfile


ROOT = pathlib.Path(__file__).resolve().parents[2]
SCRIPT = pathlib.Path(__file__).with_name("project_health_scan.py")
HOOK = ROOT / "dev-workflow" / "hooks" / "suggest-skills.sh"


def run(*args: str, cwd: pathlib.Path | None = None, stdin: str | None = None) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [sys.executable, str(SCRIPT), *args],
        cwd=cwd,
        input=stdin,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        check=False,
    )


def main() -> int:
    with tempfile.TemporaryDirectory() as tmp:
        project = pathlib.Path(tmp) / "Demo"
        project.mkdir()
        (project / "CLAUDE.md").write_text("# Rules\n", encoding="utf-8")
        (project / "app.py").write_text("print('x')\n", encoding="utf-8")
        (project / ".claude").mkdir()
        (project / ".claude" / "dev-workflow-health.json").write_text("{bad json", encoding="utf-8")

        bad = run("--project-root", str(project / "missing"))
        assert bad.returncode != 0
        assert "--project-root is not a directory" in bad.stderr

        timeout = run("--project-root", str(project), "--max-ms", "0", "--format", "json")
        assert timeout.returncode == 0
        timeout_data = json.loads(timeout.stdout)
        assert timeout_data["warnings"]
        assert "timeout warning" in timeout_data["warnings"][0]

        corrupt = run("--project-root", str(project), "--mode", "light", "--format", "json")
        assert corrupt.returncode == 0
        corrupt_data = json.loads(corrupt.stdout)
        assert any("state-parse warning" in w for w in corrupt_data["warnings"])

        state_path = project / ".claude" / "dev-workflow-health.json"
        state_path.unlink()
        write = run("--project-root", str(project), "--write-state", "--format", "json")
        assert write.returncode == 0
        assert state_path.exists()
        # Defensive: confirm the renamed file did not leak into a hardcoded historical path elsewhere on disk
        assert not pathlib.Path("/Users/norvyn/.adam/dev-workflow-health.json").exists()

    hook = subprocess.run(
        ["bash", str(HOOK)],
        cwd=ROOT,
        input='{"prompt":"write a plan for this change"}',
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        check=False,
    )
    assert hook.returncode == 0, hook.stderr
    health_lines = [line for line in hook.stdout.splitlines() if line.startswith("[health-hint]")]
    assert len(health_lines) <= 1

    print("project-health-scan-fixtures-ok")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
