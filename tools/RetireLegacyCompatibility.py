#!/usr/bin/env python3
"""Audit and optionally retire Inventory Toolkit legacy config compatibility.

Default mode is read-only. ``--apply`` removes compatibility hooks after a
strict preflight audit and validates the resulting repository. ``--commit``
adds an atomic Git commit after successful validation.
"""

from __future__ import annotations

import argparse
import json
import re
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
PROFILES_ROOT = ROOT / "profiles"
CURRENT_CONFIG_VERSION = 3
AUTHOR = "FPSensor <gkartyt@gmail.com>"
COMMIT_MESSAGE = "refactor: retire legacy configuration compatibility"

LEGACY_FILES = (
    "general/settings.json",
    "general/databases.json",
    "general/stores.json",
    "general/familias.json",
    "general/schema.json",
    "stock_processing/cleaning.json",
    "stock_processing/pricing.json",
    "cross_check/cross_check_settings.json",
    "yoy_reports/reports.json",
)
CURRENT_CONFIGS = (
    "general/catalog.json",
    "general/families.json",
    "general/network.json",
    "stock_processing/settings.json",
    "cross_check/settings.json",
    "yoy_reports/settings.json",
)
LEGACY_API_NAMES = (
    "familias",
    "stores",
    "databases",
    "settings",
    "cleaning",
    "pricing",
    "cross_check_settings",
    "reports",
)

COMPATIBILITY_MODULES = (
    Path("core/compatibility.py"),
    Path("core/legacy_config.py"),
    Path("core/legacy_profile_migration.py"),
)
RETIRE_WITH_COMPATIBILITY = (
    Path("tests/test_compatibility.py"),
    Path("docs/legacy_compatibility.md"),
    Path("tools/RetireLegacyCompatibility.py"),
)
MARKER_FILES = (
    Path("core/configuration_manager.py"),
    Path("core/profile_config.py"),
    Path("cli/menu.py"),
    Path("cli/config_menu.py"),
    Path("cli/wizard.py"),
    Path("tests/test_config.py"),
    Path("docs/core.md"),
    Path("docs/profiles.md"),
)
COMPATIBILITY_SOURCE_FILES = {
    Path("core/compatibility.py"),
    Path("core/legacy_config.py"),
    Path("core/legacy_profile_migration.py"),
}

ALLOWED_LEGACY_IMPORT_FILES = {
    Path("core/configuration_manager.py"),
    Path("core/profile_config.py"),
    Path("cli/menu.py"),
    Path("cli/config_menu.py"),
    Path("cli/wizard.py"),
    Path("tests/test_config.py"),
    Path("tests/test_compatibility.py"),
}

BEGIN_MARKERS = ("# BEGIN LEGACY_COMPATIBILITY", "<!-- BEGIN LEGACY_COMPATIBILITY -->")
END_MARKERS = ("# END LEGACY_COMPATIBILITY", "<!-- END LEGACY_COMPATIBILITY -->")


def run_git(*args: str, check: bool = True) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        ["git", "-C", str(ROOT), *args],
        check=check,
        text=True,
        capture_output=True,
    )


def git_is_clean() -> bool:
    result = run_git("status", "--porcelain")
    return not result.stdout.strip()


def audit_profiles() -> list[str]:
    problems: list[str] = []
    if not PROFILES_ROOT.exists():
        return problems

    for profile_dir in sorted(path for path in PROFILES_ROOT.iterdir() if path.is_dir()):
        configs = profile_dir / "configs"
        if not configs.exists():
            continue

        active_legacy = [rel for rel in LEGACY_FILES if (configs / rel).exists()]
        if active_legacy:
            problems.append(
                f"profile '{profile_dir.name}' still has active legacy files: "
                + ", ".join(active_legacy)
            )

        for relative_path in CURRENT_CONFIGS:
            path = configs / relative_path
            if not path.exists():
                problems.append(
                    f"profile '{profile_dir.name}' is missing current config: {relative_path}"
                )
                continue
            try:
                payload = json.loads(path.read_text(encoding="utf-8"))
            except (OSError, json.JSONDecodeError) as exc:
                problems.append(f"cannot read {path.relative_to(ROOT)}: {exc}")
                continue
            version = payload.get("version")
            if version != CURRENT_CONFIG_VERSION:
                problems.append(
                    f"{path.relative_to(ROOT)} has schema version {version!r}; "
                    f"expected {CURRENT_CONFIG_VERSION}"
                )
    return problems


def audit_source_consumers() -> list[str]:
    problems: list[str] = []
    legacy_api_pattern = re.compile(
        r"\.get_config\(\s*['\"](" + "|".join(map(re.escape, LEGACY_API_NAMES)) + r")[\"']"
    )
    legacy_import_pattern = re.compile(
        r"(?:from|import)\s+core\.(?:legacy_config|legacy_profile_migration|compatibility)\b"
    )

    for path in sorted(ROOT.rglob("*.py")):
        relative = path.relative_to(ROOT)
        if any(part in {".git", "__pycache__"} for part in relative.parts):
            continue
        if relative == Path("tools/RetireLegacyCompatibility.py") or relative in COMPATIBILITY_SOURCE_FILES:
            continue
        text = path.read_text(encoding="utf-8", errors="replace")

        if relative != Path("tests/test_compatibility.py"):
            for match in legacy_api_pattern.finditer(text):
                problems.append(
                    f"deprecated get_config('{match.group(1)}') consumer remains in {relative}"
                )

        if legacy_import_pattern.search(text) and relative not in ALLOWED_LEGACY_IMPORT_FILES:
            problems.append(f"unexpected legacy compatibility import remains in {relative}")
    return problems


def audit_markers() -> list[str]:
    problems: list[str] = []
    for relative in MARKER_FILES:
        path = ROOT / relative
        if not path.exists():
            problems.append(f"retirement marker file is missing: {relative}")
            continue
        text = path.read_text(encoding="utf-8")
        begin_count = sum(text.count(marker) for marker in BEGIN_MARKERS)
        end_count = sum(text.count(marker) for marker in END_MARKERS)
        if begin_count != end_count or begin_count == 0:
            problems.append(
                f"retirement markers are missing/unbalanced in {relative} "
                f"({begin_count} begin, {end_count} end)"
            )
    return problems


def audit_repository() -> list[str]:
    return audit_profiles() + audit_source_consumers() + audit_markers()


def strip_compatibility_blocks(text: str, path: Path) -> str:
    output: list[str] = []
    in_block = False
    blocks = 0
    for line in text.splitlines(keepends=True):
        stripped = line.strip()
        if stripped in BEGIN_MARKERS:
            if in_block:
                raise RuntimeError(f"nested compatibility marker in {path}")
            in_block = True
            blocks += 1
            continue
        if stripped in END_MARKERS:
            if not in_block:
                raise RuntimeError(f"orphan compatibility end marker in {path}")
            in_block = False
            continue
        if not in_block:
            output.append(line)
    if in_block:
        raise RuntimeError(f"unterminated compatibility marker in {path}")
    if not blocks:
        raise RuntimeError(f"no compatibility blocks found in {path}")
    return "".join(output)


def update_readme_tree() -> None:
    path = ROOT / "README.md"
    lines = path.read_text(encoding="utf-8").splitlines(keepends=True)
    retired_names = {item.name for item in (*COMPATIBILITY_MODULES, *RETIRE_WITH_COMPATIBILITY)}
    filtered = [line for line in lines if not any(name in line for name in retired_names)]
    path.write_text("".join(filtered), encoding="utf-8")


def clean_test_imports() -> None:
    path = ROOT / "tests/test_config.py"
    text = path.read_text(encoding="utf-8")
    if "json." not in text and "json.dumps" not in text and "json.loads" not in text:
        text = text.replace("import json\n\n", "")
    path.write_text(text, encoding="utf-8")


def apply_retirement() -> None:
    for relative in MARKER_FILES:
        path = ROOT / relative
        path.write_text(
            strip_compatibility_blocks(path.read_text(encoding="utf-8"), relative),
            encoding="utf-8",
        )

    for relative in (*COMPATIBILITY_MODULES, *RETIRE_WITH_COMPATIBILITY):
        path = ROOT / relative
        if path.exists():
            path.unlink()

    update_readme_tree()
    clean_test_imports()


def validate_tree() -> None:
    commands = (
        [sys.executable, "-m", "compileall", "-q", "core", "cli", "engine", "gui", "tools", "tests"],
        [sys.executable, "-m", "pytest", "-q"],
        [sys.executable, "tools/IntegrityCheck.py"],
    )
    for command in commands:
        print("  $", " ".join(command))
        subprocess.run(command, cwd=ROOT, check=True)


def restore_worktree() -> None:
    subprocess.run(
        ["git", "-C", str(ROOT), "restore", "--staged", "--worktree", "."],
        check=False,
    )


def commit_retirement() -> None:
    run_git("add", "-A")
    subprocess.run(
        [
            "git",
            "-C",
            str(ROOT),
            "commit",
            "--author",
            AUTHOR,
            "-m",
            COMMIT_MESSAGE,
        ],
        check=True,
    )


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--apply",
        action="store_true",
        help="remove compatibility hooks after a clean audit and validate the tree",
    )
    parser.add_argument(
        "--commit",
        action="store_true",
        help="commit the retirement after successful --apply validation",
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    if args.commit and not args.apply:
        print("ERROR: --commit requires --apply.", file=sys.stderr)
        return 2

    print("Inventory Toolkit legacy compatibility retirement audit")
    print(f"Repository: {ROOT}")

    problems = audit_repository()
    if problems:
        print("\nNOT READY:")
        for problem in problems:
            print(f"  - {problem}")
        print("\nMigrate/update the items above and run the audit again.")
        return 1

    print("\nREADY: no active legacy profiles or unexpected compatibility consumers found.")
    if not args.apply:
        print("Read-only audit complete. Use --apply when you decide to retire compatibility.")
        return 0

    if not git_is_clean():
        print("ERROR: Git worktree must be clean before --apply.", file=sys.stderr)
        return 2

    print("\nApplying compatibility retirement...")
    try:
        apply_retirement()
        validate_tree()
    except Exception as exc:
        print(f"\nERROR: retirement validation failed: {exc}", file=sys.stderr)
        print("Restoring the clean pre-retirement worktree...", file=sys.stderr)
        restore_worktree()
        return 1

    if args.commit:
        commit_retirement()
        print(f"\nCommitted: {COMMIT_MESSAGE}")
    else:
        print("\nRetirement validated successfully; changes are left uncommitted for review.")
        print("Run with --apply --commit from a clean tree when you want the atomic commit.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
