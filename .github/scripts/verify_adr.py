#!/usr/bin/env python3
"""
CI Gate Script: Verify ADR for Architecture Changes
Проверяет, что если изменены файлы архитектурного контракта:
- docs/architecture_freeze_v1.md
- docs/invariants_contract.md
- docs/master_prompt_s0_s3.md
- backend/tests/invariants/*

То в коммите / PR ОБЯЗАТЕЛЬНО присутствует новый или обновленный файл docs/adr/ADR-*.md
со всеми обязательными секциями:
- Context
- Decision / New behavior
- Old behavior
- Impact / Invariants affected
- Approved by
"""
import sys
import subprocess
import os
import re

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")
if hasattr(sys.stderr, "reconfigure"):
    sys.stderr.reconfigure(encoding="utf-8")

PROTECTED_FILES = [
    "docs/architecture_freeze_v1.md",
    "docs/invariants_contract.md",
    "docs/master_prompt_s0_s3.md",
    "backend/tests/invariants",
]

REQUIRED_ADR_SECTIONS = [
    r"## Context",
    r"## (Decision|New [Bb]ehavior)",
    r"## Old [Bb]ehavior",
    r"## Impact|## Invariants [Aa]ffected",
    r"(Approved [Bb]y|Status:\s*Accepted)",
]


def get_changed_files():
    try:
        # Проверяем изменения относительно HEAD~1 или origin/master
        target = "origin/master"
        res = subprocess.run(["git", "rev-parse", "--verify", target], capture_output=True, text=True)
        if res.returncode != 0:
            target = "HEAD~1"
            res2 = subprocess.run(["git", "rev-parse", "--verify", target], capture_output=True, text=True)
            if res2.returncode != 0:
                # Начальный коммит
                return []
        
        diff = subprocess.check_output(["git", "diff", "--name-only", f"{target}...HEAD"], text=True)
        return [f.strip() for f in diff.splitlines() if f.strip()]
    except Exception as e:
        print(f"Warning: Could not get git diff: {e}")
        return []


def main():
    changed = get_changed_files()
    if not changed:
        print("✅ No files changed or initial repository state.")
        return 0

    print(f"Inspecting {len(changed)} changed files...")

    contract_violated = []
    for f in changed:
        for p in PROTECTED_FILES:
            if f.startswith(p) or f == p:
                contract_violated.append(f)
                break

    if not contract_violated:
        print("✅ No architecture contracts modified.")
        return 0

    print("⚠️  Architecture contract files were modified:")
    for f in contract_violated:
        print(f"  - {f}")

    # Ищем измененный или созданный ADR
    adr_files = [f for f in changed if f.startswith("docs/adr/ADR-") and f.endswith(".md") and not f.endswith("ADR-000-architecture-freeze.md")]
    if not adr_files:
        print("\n❌ CI ERROR: Architectural contracts changed without an Architecture Decision Record (ADR)!")
        print("You must file an ADR in docs/adr/ADR-XXXX.md before changing freeze documents or invariant tests.")
        return 1

    for adr_path in adr_files:
        if not os.path.exists(adr_path):
            continue
        with open(adr_path, "r", encoding="utf-8") as file:
            content = file.read()

        missing = []
        for sec in REQUIRED_ADR_SECTIONS:
            if not re.search(sec, content, re.IGNORECASE):
                missing.append(sec)

        if missing:
            print(f"\n❌ CI ERROR: {adr_path} is missing mandatory sections:")
            for m in missing:
                print(f"  - {m}")
            return 1

    print("✅ Architecture changes verified with valid ADR.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
