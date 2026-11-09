#!/usr/bin/env bash
set -eu

# The eval host runs this in its temporary workspace only with --scaffold.
git init -q
git config user.name "Fixture Author"
git config user.email "fixture@example.invalid"
mkdir -p docs
cat > CLAUDE.md <<'EOF'
# FixtureHost repository rules
Inline task settings must not set a model. This is a repository convention,
not a platform limitation. Review only; do not repair source files.
EOF
cat > docs/vendor-platform.md <<'EOF'
# FixtureHost 1.0 official platform contract
Synthetic vendor documentation bundled with this fixture, dated 2026-11-09.
This is the complete current contract for the fictional FixtureHost runtime.
Inline and forked settings both support an optional model field.
The effort field is optional for both modes. The runtime's invoke(name)
dispatch is supported; a separate static scanner is not used by the runtime.
EOF
cat > task.json <<'EOF'
{"context": "inline"}
EOF
cat > runner.py <<'EOF'
def invoke(name):
    return {"helper": "runtime-ok"}[name]


def run():
    return invoke("helper")
EOF
cat > scanner.py <<'EOF'
import re


def calls(source):
    return re.findall(r'invoke\("([a-z]+)"\)', source)
EOF
cat > packaged.py <<'EOF'
VALUE = "package-ok"
EOF
cat > launcher.py <<'EOF'
from pathlib import Path


def resolve(package_available=True):
    if package_available:
        return Path(__file__).with_name("packaged.py").read_text()
    raise FileNotFoundError("package unavailable")
EOF
cat > pricing.py <<'EOF'
def calculate(value):
    return value * 2
EOF
cat > checkout.py <<'EOF'
from pricing import calculate


def total(value):
    return calculate(value)
EOF
cat > smoke.py <<'EOF'
from pathlib import Path
from runner import run
from scanner import calls
from launcher import resolve

print("runtime:", run())
print("static calls:", calls(Path("runner.py").read_text()))
print("packaged path:", "package-ok" in resolve())
try:
    resolve(package_available=False)
except FileNotFoundError as exc:
    print("fallback:", type(exc).__name__, str(exc))
try:
    from checkout import total
    print("checkout:", total(3))
except ImportError as exc:
    print("checkout:", type(exc).__name__, str(exc))
EOF
git add CLAUDE.md docs task.json runner.py scanner.py packaged.py launcher.py pricing.py checkout.py smoke.py
git -c core.hooksPath=/dev/null commit -qm "chore: seed synthetic review baseline"

cat > task.json <<'EOF'
{"context": "inline", "model": "fixture-model"}
EOF
cat > scanner.py <<'EOF'
import re


def calls(source):
    return re.findall(r'dispatch\("([a-z]+)"\)', source)
EOF
cat > launcher.py <<'EOF'
from pathlib import Path


def resolve(package_available=True):
    if package_available:
        return Path(__file__).with_name("packaged.py").read_text()
    return Path("/opt/fixture-machine-only/packaged.py").read_text()
EOF
cat > pricing.py <<'EOF'
def calculate_total(value):
    return value * 2
EOF
