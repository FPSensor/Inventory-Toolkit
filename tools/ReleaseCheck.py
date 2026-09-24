#!/usr/bin/env python3
"""Reproducible pre-release verification for Inventory Toolkit.

Modes:

* default: fast repository gate (compile, tests, integrity, profiles)
* ``--demo``: fast gate plus end-to-end smoke runs for all three workflows
* ``--release``: full release certification against committed golden masters
* ``--update-reference``: deliberately regenerate the approved golden masters

Every workflow runs in an isolated Python subprocess. Generated workbooks live
inside a temporary directory and are deleted automatically after the run.
"""

from __future__ import annotations

import argparse
import concurrent.futures
import os
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path
from types import SimpleNamespace

ROOT = Path(__file__).resolve().parents[1]
PROFILES_ROOT = ROOT / "profiles"
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from core.logger import (  # noqa: E402
    debug_level_from_environment,
    log_debug_event,
    setup_logger,
)
from tools.release_reference import (  # noqa: E402
    REFERENCE_MANIFEST_PATH,
    REFERENCE_WORKBOOK_ROOT,
    build_manifest,
    compare_fixture_fingerprint,
    compare_workbooks,
    format_differences,
    load_manifest,
    reference_workbook_path,
    verify_reference_files,
    write_manifest,
)

WORKFLOWS = ("stock", "cross", "yoy")


def _run(command: list[str]) -> None:
    print("  $", " ".join(command), flush=True)
    log_debug_event("release_subprocess_start", command=command, cwd=str(ROOT))
    try:
        subprocess.run(command, cwd=ROOT, check=True)
    except subprocess.CalledProcessError as exc:
        log_debug_event(
            "release_subprocess_finish",
            command=command,
            returncode=exc.returncode,
        )
        raise
    else:
        log_debug_event("release_subprocess_finish", command=command, returncode=0)


def _quick_gate() -> None:
    _run([
        sys.executable,
        "-m",
        "compileall",
        "-q",
        "core",
        "cli",
        "engine",
        "gui",
        "tools",
        "tests",
    ])
    _run([sys.executable, "-m", "pytest", "-q"])
    _run([sys.executable, "tools/IntegrityCheck.py"])

    retirement_tool = ROOT / "tools" / "RetireLegacyCompatibility.py"
    if retirement_tool.exists():
        _run([sys.executable, str(retirement_tool.relative_to(ROOT))])

    _validate_profiles()


def _validate_profiles() -> None:
    os.chdir(ROOT)
    from core.configuration_manager import ConfigurationManager

    profiles = sorted(path.name for path in PROFILES_ROOT.iterdir() if path.is_dir())
    if not profiles:
        raise RuntimeError("No profiles were found under profiles/.")

    print("\nProfile validation:")
    for profile in profiles:
        config = ConfigurationManager(profile)
        config.get_catalog()
        config.get_family_config()
        config.get_network_config()
        config.get_stock_processing_config()
        config.get_cross_check_config()
        config.get_yoy_reports_config()
        print(f"  PASS  {profile}")


def _workflow_output_path(directory: Path, workflow: str) -> Path:
    return directory / {
        "cross": "cross_check.xlsx",
        "stock": "stock_processing.xlsx",
        "yoy": "yoy_reports.xlsx",
    }[workflow]


def _execute_demo_workflows(
    output_dir: Path,
    cross_system_override: str | None,
    *,
    jobs: int,
) -> dict[str, Path]:
    outputs: dict[str, Path] = {}
    commands: dict[str, list[str]] = {}
    for workflow in WORKFLOWS:
        output = _workflow_output_path(output_dir, workflow)
        outputs[workflow] = output
        command = [
            sys.executable,
            "tools/ReleaseCheck.py",
            "--_demo-workflow",
            workflow,
            "--_output",
            str(output),
        ]
        if workflow == "cross" and cross_system_override:
            command.extend(["--cross-system", cross_system_override])
        commands[workflow] = command

    max_workers = max(1, min(jobs, len(WORKFLOWS)))
    with concurrent.futures.ThreadPoolExecutor(max_workers=max_workers) as executor:
        futures = {workflow: executor.submit(_run, command) for workflow, command in commands.items()}
        failures: list[str] = []
        for workflow, future in futures.items():
            try:
                future.result()
            except subprocess.CalledProcessError as exc:
                failures.append(f"{workflow} workflow exited with status {exc.returncode}")
        if failures:
            raise RuntimeError("Demo workflow execution failed:\n" + "\n".join(failures))

    for workflow, output in outputs.items():
        if not output.exists():
            raise RuntimeError(f"{workflow} workflow reported success but produced no workbook.")
    return outputs


def _demo_gate(cross_system_override: str | None, *, jobs: int) -> None:
    print("\nDemo workflow smoke validation:")
    with tempfile.TemporaryDirectory(prefix="inventory_toolkit_release_smoke_") as temp_dir:
        _execute_demo_workflows(Path(temp_dir), cross_system_override, jobs=jobs)


def _release_gate(cross_system_override: str | None, *, max_differences: int, jobs: int) -> None:
    print("\nGolden-master release certification:")
    manifest = load_manifest()

    fixture_drift = compare_fixture_fingerprint(manifest.get("fixtures", {}))
    if fixture_drift:
        raise RuntimeError(
            "Release references are stale because the demo fixture changed:\n"
            + format_differences(fixture_drift)
            + "\nRun --update-reference only after reviewing and approving the new expected output."
        )

    reference_problems = verify_reference_files(manifest)
    if reference_problems:
        raise RuntimeError(
            "Committed release references are missing or were modified outside the update workflow:\n"
            + format_differences(reference_problems)
        )

    with tempfile.TemporaryDirectory(prefix="inventory_toolkit_release_cert_") as temp_dir:
        outputs = _execute_demo_workflows(Path(temp_dir), cross_system_override, jobs=jobs)
        failures: list[str] = []
        for workflow in WORKFLOWS:
            expected = reference_workbook_path(workflow)
            actual = outputs[workflow]
            result = compare_workbooks(
                expected,
                actual,
                max_differences=max_differences,
            )
            if result.matches:
                print(f"  GOLD  {workflow:<5} matches approved reference")
                continue

            failures.append(f"{workflow} output differs from {expected.relative_to(ROOT)}")
            failures.extend(f"{workflow}: {line}" for line in result.differences)
            if result.truncated:
                failures.append(
                    f"{workflow}: additional differences omitted after {max_differences} diagnostics"
                )

        if failures:
            raise RuntimeError(
                "Golden-master mismatch detected:\n" + format_differences(failures)
            )


def _git_source_revision() -> str | None:
    """Return the current Git revision even when the worktree has expected reference changes."""
    try:
        return subprocess.run(
            ["git", "rev-parse", "HEAD"],
            cwd=ROOT,
            check=True,
            capture_output=True,
            text=True,
        ).stdout.strip()
    except (OSError, subprocess.CalledProcessError):
        return None


def _install_reference_set(staged: dict[str, Path], manifest: dict) -> None:
    """Replace the committed golden-master set with rollback on installation failure."""
    REFERENCE_WORKBOOK_ROOT.mkdir(parents=True, exist_ok=True)
    REFERENCE_MANIFEST_PATH.parent.mkdir(parents=True, exist_ok=True)

    with tempfile.TemporaryDirectory(
        prefix="inventory_toolkit_reference_install_",
        dir=REFERENCE_MANIFEST_PATH.parent,
    ) as install_dir:
        install_root = Path(install_dir)
        candidate_root = install_root / "candidate"
        backup_root = install_root / "backup"
        candidate_root.mkdir()
        backup_root.mkdir()

        candidates: dict[Path, Path] = {}
        for workflow in WORKFLOWS:
            destination = reference_workbook_path(workflow)
            candidate = candidate_root / destination.name
            shutil.copy2(staged[workflow], candidate)
            candidates[destination] = candidate

        candidate_manifest = candidate_root / REFERENCE_MANIFEST_PATH.name
        write_manifest(manifest, candidate_manifest)
        candidates[REFERENCE_MANIFEST_PATH] = candidate_manifest

        backups: dict[Path, Path | None] = {}
        installed: list[Path] = []
        try:
            for destination, candidate in candidates.items():
                backup = backup_root / destination.name
                if destination.exists():
                    shutil.copy2(destination, backup)
                    backups[destination] = backup
                else:
                    backups[destination] = None
                candidate.replace(destination)
                installed.append(destination)
        except Exception:
            for destination in reversed(installed):
                backup = backups.get(destination)
                if backup is None:
                    destination.unlink(missing_ok=True)
                elif backup.exists():
                    shutil.copy2(backup, destination)
            raise


def _confirm_reference_update(assume_yes: bool) -> None:
    if assume_yes:
        return
    if not sys.stdin.isatty():
        raise RuntimeError("Reference update requires an interactive confirmation or --yes.")

    print(
        "\nWARNING: updating golden masters declares the current demo output correct.\n"
        "Use this only after intentionally changing business behavior, demo inputs, or\n"
        "demo configuration and manually reviewing the resulting workbooks.\n"
    )
    confirmation = input("Type UPDATE REFERENCES to continue: ").strip()
    if confirmation != "UPDATE REFERENCES":
        raise RuntimeError("Reference update cancelled; confirmation text did not match.")


def _update_reference(cross_system_override: str | None, *, assume_yes: bool, jobs: int) -> None:
    if cross_system_override:
        raise RuntimeError(
            "--cross-system cannot be used with --update-reference. "
            "Approved golden masters must be generated from the committed demo fixture."
        )

    _confirm_reference_update(assume_yes)
    print("\nGenerating candidate golden masters:")

    with tempfile.TemporaryDirectory(prefix="inventory_toolkit_reference_update_") as temp_dir:
        temp_root = Path(temp_dir)
        outputs = _execute_demo_workflows(temp_root, None, jobs=jobs)

        # Stage all files before replacing any committed reference. If generation
        # or validation fails, TemporaryDirectory removes every candidate.
        staged_root = temp_root / "staged"
        staged_root.mkdir()
        staged: dict[str, Path] = {}
        for workflow, source in outputs.items():
            staged_path = staged_root / reference_workbook_path(workflow).name
            shutil.copy2(source, staged_path)
            staged[workflow] = staged_path

        print("\nCandidate generation completed. Running repository gate before approval...")
        _quick_gate()

        manifest = build_manifest(staged, source_revision=_git_source_revision())
        _install_reference_set(staged, manifest)

    print("\nGolden masters updated:")
    for workflow in WORKFLOWS:
        print(f"  UPDATED  {reference_workbook_path(workflow).relative_to(ROOT)}")
    print(f"  UPDATED  {REFERENCE_MANIFEST_PATH.relative_to(ROOT)}")
    print("\nReview these Git changes before committing them.")


def _run_internal_demo(
    workflow: str,
    cross_system_override: str | None,
    output_path: str | None,
) -> None:
    if not output_path:
        raise ValueError("Internal demo execution requires --_output.")
    os.chdir(ROOT)
    output = Path(output_path).resolve()
    output.parent.mkdir(parents=True, exist_ok=True)
    if workflow == "cross":
        _run_cross_demo(cross_system_override, output)
    elif workflow == "stock":
        _run_stock_demo(output)
    elif workflow == "yoy":
        _run_yoy_demo(output)
    else:
        raise ValueError(f"Unknown demo workflow: {workflow}")


def _run_cross_demo(cross_system_override: str | None, output: Path) -> None:
    from openpyxl import load_workbook

    from core.business_schema import (
        ARTICLE_COLUMN,
        COST_TOTAL_COLUMN,
        DIFFERENCE_COLUMN,
        FAMILY_COLUMN,
        PHYSICAL_COUNT_COLUMN,
        SALES_TOTAL_COLUMN,
        SYSTEM_STOCK_COLUMN,
    )
    from engine.inventory_cross_check.generator import run_cross_check

    demo = ROOT / "examples" / "demo"
    cross_system = (
        Path(cross_system_override).resolve()
        if cross_system_override
        else demo / "cross_check_system_stock.xls"
    )

    result = run_cross_check(
        SimpleNamespace(
            cross_check_system=str(cross_system),
            cross_check_count=str(demo / "cross_check_physical_count.xlsx"),
            shared_cost=str(demo / "shared_cost_list.xlsx"),
            shared_sales=str(demo / "shared_sales_price_list.xlsx"),
            cross_check_out=str(output),
            cross_check_profile="demo",
            cross_check_consolidate=True,
            cross_check_partial=False,
            non_interactive=True,
        )
    )
    if not result:
        raise RuntimeError("Cross Check demo did not produce an output workbook.")
    workbook = load_workbook(result, data_only=False, read_only=True)
    worksheet = workbook[workbook.sheetnames[0]]
    headers = [cell.value for cell in next(worksheet.iter_rows(min_row=1, max_row=1))]
    expected_headers = [
        FAMILY_COLUMN,
        ARTICLE_COLUMN,
        SYSTEM_STOCK_COLUMN,
        PHYSICAL_COUNT_COLUMN,
        DIFFERENCE_COLUMN,
        COST_TOTAL_COLUMN,
        SALES_TOTAL_COLUMN,
    ]
    if headers != expected_headers:
        raise RuntimeError(f"Cross Check demo headers changed: {headers!r}")
    print(f"  PASS  Cross Check ({worksheet.max_row - 1} difference rows)")
    workbook.close()


def _run_stock_demo(output: Path) -> None:
    from openpyxl import load_workbook

    from core.configuration_manager import ConfigurationManager
    from engine.stock_processing.generator import run_stock_processing

    demo = ROOT / "examples" / "demo"
    result = run_stock_processing(
        SimpleNamespace(
            stock_processing_raw=str(demo / "stock_processing_raw_stock.xlsx"),
            shared_cost=str(demo / "shared_cost_list.xlsx"),
            shared_sales=str(demo / "shared_sales_price_list.xlsx"),
            stock_processing_out=str(output),
            stock_processing_profile="demo",
            non_interactive=True,
        )
    )
    if not result:
        raise RuntimeError("Stock Processing demo did not produce an output workbook.")
    stock_config = ConfigurationManager("demo").get_stock_output()
    workbook = load_workbook(result, data_only=False, read_only=True)
    expected_sheets = {
        stock_config["raw_data_sheet"],
        *(summary["sheet_name"] for summary in stock_config["summaries"]),
    }
    missing_sheets = expected_sheets.difference(workbook.sheetnames)
    if missing_sheets:
        raise RuntimeError(f"Stock Processing demo is missing sheets: {sorted(missing_sheets)}")
    raw_sheet = workbook[stock_config["raw_data_sheet"]]
    if raw_sheet.max_row <= 1:
        raise RuntimeError("Stock Processing raw-data sheet contains no data rows.")
    print(f"  PASS  Stock Processing ({raw_sheet.max_row - 1} data rows)")
    workbook.close()


def _run_yoy_demo(output: Path) -> None:
    import pandas as pd
    from openpyxl import load_workbook

    from core.configuration_manager import ConfigurationManager
    from engine.yoy_reports.generator import generate_sales_report

    demo = ROOT / "examples" / "demo"
    yoy_config = ConfigurationManager("demo").get_yoy_reports_config()
    date_column = yoy_config["input"]["date_column"]
    history = pd.read_excel(
        demo / "yoy_sales_history.xlsx",
        sheet_name=0,
        usecols=[date_column],
    )
    dates = pd.to_datetime(history[date_column], errors="coerce").dropna()
    latest_year = int(dates.dt.year.max())
    current_dates = dates[dates.dt.year == latest_year]
    start_date = pd.Timestamp(year=latest_year, month=1, day=1)
    end_date = current_dates.max()

    result = generate_sales_report(
        str(demo / "yoy_sales_history.xlsx"),
        str(output),
        start_date,
        end_date,
        yoy_config,
        yoy_config["input"]["grouping_column"],
        True,
        False,
        "demo",
        yoy_config["output"].get("include_sizes", False),
        True,
    )
    if not result:
        raise RuntimeError("YoY demo did not produce an output workbook.")
    workbook = load_workbook(result, data_only=False, read_only=True)
    if "Full Report" not in workbook.sheetnames:
        raise RuntimeError("YoY demo is missing the Full Report sheet.")
    if len(workbook.sheetnames) < 2:
        raise RuntimeError("YoY segmented demo did not create period sheets.")
    print(f"  PASS  YoY Reports ({len(workbook.sheetnames)} sheets)")
    workbook.close()


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    mode = parser.add_mutually_exclusive_group()
    mode.add_argument(
        "--demo",
        action="store_true",
        help="also execute all three example workflows as smoke tests",
    )
    mode.add_argument(
        "--release",
        action="store_true",
        help="run full pre-release certification against approved golden masters",
    )
    mode.add_argument(
        "--update-reference",
        action="store_true",
        help="regenerate approved golden-master workbooks after explicit confirmation",
    )
    parser.add_argument(
        "--yes",
        action="store_true",
        help="skip the interactive UPDATE REFERENCES prompt (intended for the debug CLI wrapper)",
    )
    parser.add_argument(
        "--jobs",
        type=int,
        choices=(1, 2, 3),
        default=3,
        help="number of isolated demo workflows to run in parallel (default: 3)",
    )
    parser.add_argument(
        "--max-differences",
        type=int,
        default=25,
        help="maximum workbook differences to print per certification run (default: 25)",
    )
    parser.add_argument(
        "--cross-system",
        metavar="PATH",
        help="override the demo Cross Check system-stock file (useful for converted .xlsx fixtures)",
    )
    parser.add_argument(
        "--_demo-workflow",
        choices=WORKFLOWS,
        help=argparse.SUPPRESS,
    )
    parser.add_argument("--_output", help=argparse.SUPPRESS)
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    inherited_debug_level = debug_level_from_environment()
    setup_logger(inherited_debug_level, reset_session_log=False)
    log_debug_event(
        "release_check_start",
        debug_level=inherited_debug_level,
        argv=sys.argv[1:],
        repository=str(ROOT),
    )
    try:
        if args._demo_workflow:
            _run_internal_demo(args._demo_workflow, args.cross_system, args._output)
            log_debug_event(
                "release_check_finish",
                returncode=0,
                workflow=args._demo_workflow,
            )
            return 0

        print("Inventory Toolkit release verification")
        print(f"Repository: {ROOT}\n")

        # Run heavyweight demo workflows before the repository gate. On some
        # constrained environments a large Pandas/OpenPyXL workflow can retain
        # enough OS-level cache pressure that starting Stock Processing after
        # several verification subprocesses becomes unnecessarily slow. The
        # checks remain identical; this ordering keeps each release run stable.
        if args.update_reference:
            _update_reference(args.cross_system, assume_yes=args.yes, jobs=args.jobs)
        elif args.release:
            _release_gate(args.cross_system, max_differences=max(1, args.max_differences), jobs=args.jobs)
            _quick_gate()
        elif args.demo:
            _demo_gate(args.cross_system, jobs=args.jobs)
            _quick_gate()
        else:
            _quick_gate()
    except (Exception, subprocess.CalledProcessError) as exc:
        log_debug_event("release_check_finish", returncode=1, error=str(exc))
        print(f"\nRELEASE CHECK FAILED: {exc}", file=sys.stderr)
        return 1

    print("\nRELEASE CHECK PASSED")
    log_debug_event("release_check_finish", returncode=0)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
