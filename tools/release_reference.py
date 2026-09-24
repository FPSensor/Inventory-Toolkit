"""Golden-master support for Inventory Toolkit release certification.

Reference outputs are stored as real XLSX files so failures can be diagnosed
against an inspectable workbook. Normal certification compares canonicalized
XLSX XML instead of ZIP bytes: volatile archive timestamps are ignored while
worksheet data, formulas, styles, merges, filters, dimensions, and workbook
structure remain covered.
"""

from __future__ import annotations

import hashlib
import json
import zipfile
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Iterable

ROOT = Path(__file__).resolve().parents[1]
DEMO_ROOT = ROOT / "examples" / "demo"
PROFILE_ROOT = ROOT / "profiles" / "demo"
REFERENCE_ROOT = ROOT / "tests" / "release_reference"
REFERENCE_WORKBOOK_ROOT = REFERENCE_ROOT / "workbooks"
REFERENCE_MANIFEST_PATH = REFERENCE_ROOT / "manifest.json"
REFERENCE_SCHEMA_VERSION = 1

REFERENCE_FILENAMES = {
    "cross": "cross_check.xlsx",
    "stock": "stock_processing.xlsx",
    "yoy": "yoy_reports.xlsx",
}

DEMO_INPUTS = (
    DEMO_ROOT / "cross_check_physical_count.xlsx",
    DEMO_ROOT / "cross_check_system_stock.xls",
    DEMO_ROOT / "shared_cost_list.xlsx",
    DEMO_ROOT / "shared_sales_price_list.xlsx",
    DEMO_ROOT / "stock_processing_raw_stock.xlsx",
    DEMO_ROOT / "yoy_sales_history.xlsx",
)

_SEMANTIC_EXACT_PARTS = {
    "[Content_Types].xml",
    "xl/workbook.xml",
    "xl/styles.xml",
    "xl/sharedStrings.xml",
    "xl/_rels/workbook.xml.rels",
}
_SEMANTIC_PREFIXES = (
    "xl/worksheets/",
    "xl/tables/",
    "xl/theme/",
    "xl/drawings/",
)


@dataclass(frozen=True)
class WorkbookComparison:
    """Semantic comparison result for two workbooks."""

    matches: bool
    differences: tuple[str, ...]
    truncated: bool = False


def _sha256_bytes(payload: bytes) -> str:
    return hashlib.sha256(payload).hexdigest()


def _sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _canonical_json_bytes(path: Path) -> bytes:
    """Serialize JSON fixture content independently of formatting/line endings."""
    with path.open("r", encoding="utf-8-sig") as stream:
        payload = json.load(stream)
    return json.dumps(
        payload,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8")


def _normalized_text_sha256(path: Path) -> str:
    """Hash text after normalizing CRLF/CR to LF for legacy manifests."""
    payload = path.read_bytes().replace(b"\r\n", b"\n").replace(b"\r", b"\n")
    return _sha256_bytes(payload)


def _fixture_hash(path: Path) -> str:
    """Return a stable fixture hash suitable for cross-platform certification."""
    if path.suffix.lower() == ".json":
        return _sha256_bytes(_canonical_json_bytes(path))
    return _sha256_file(path)


def _fixture_hash_candidates(path: Path) -> set[str]:
    """Return hashes accepted for current and pre-canonical JSON manifests.

    Schema-v1 manifests originally stored raw-byte SHA-256 values. Git may check
    text files out as CRLF on Windows, so an unchanged JSON fixture could look
    stale. Keep accepting the old raw/LF-normalized forms while new manifests use
    canonical JSON hashing.
    """
    candidates = {_fixture_hash(path)}
    if path.suffix.lower() == ".json":
        candidates.add(_sha256_file(path))
        candidates.add(_normalized_text_sha256(path))
    return candidates


def _fixture_paths() -> list[Path]:
    paths = list(DEMO_INPUTS)
    paths.append(PROFILE_ROOT / "profile.json")
    paths.extend(sorted((PROFILE_ROOT / "configs").rglob("*.json")))
    return sorted(path.resolve() for path in paths)


def fixture_fingerprint() -> dict[str, str]:
    """Return stable hashes for every file that defines the demo release fixture."""
    fingerprint: dict[str, str] = {}
    for path in _fixture_paths():
        relative = path.relative_to(ROOT).as_posix()
        fingerprint[relative] = _fixture_hash(path) if path.exists() else "<missing>"
    return fingerprint


def compare_fixture_fingerprint(expected: dict[str, str]) -> list[str]:
    """Describe demo input/config drift against a stored fingerprint."""
    current = fixture_fingerprint()
    differences: list[str] = []
    for relative in sorted(set(expected) | set(current)):
        if relative not in expected:
            differences.append(f"added fixture: {relative}")
        elif relative not in current:
            differences.append(f"removed fixture: {relative}")
        elif expected[relative] != current[relative]:
            path = ROOT / relative
            if not path.exists() or expected[relative] not in _fixture_hash_candidates(path):
                differences.append(f"changed fixture: {relative}")
    return differences


def load_manifest() -> dict[str, Any]:
    if not REFERENCE_MANIFEST_PATH.exists():
        raise FileNotFoundError(
            f"Release reference manifest not found: {REFERENCE_MANIFEST_PATH.relative_to(ROOT)}"
        )
    with REFERENCE_MANIFEST_PATH.open("r", encoding="utf-8") as stream:
        manifest = json.load(stream)
    if manifest.get("schema_version") != REFERENCE_SCHEMA_VERSION:
        raise RuntimeError(
            "Unsupported release-reference schema: "
            f"{manifest.get('schema_version')!r}; expected {REFERENCE_SCHEMA_VERSION}."
        )
    return manifest


def reference_workbook_path(workflow: str) -> Path:
    try:
        filename = REFERENCE_FILENAMES[workflow]
    except KeyError as exc:
        raise ValueError(f"Unknown release-reference workflow: {workflow}") from exc
    return REFERENCE_WORKBOOK_ROOT / filename


def _is_semantic_part(name: str) -> bool:
    if name in _SEMANTIC_EXACT_PARTS:
        return True
    if name.endswith(".rels") and name.startswith("xl/worksheets/_rels/"):
        return True
    return name.endswith(".xml") and name.startswith(_SEMANTIC_PREFIXES)


def _canonical_xml(payload: bytes) -> bytes:
    """Return inner XLSX XML bytes; ZIP container metadata is ignored separately."""
    return payload


def _semantic_parts(path: Path) -> dict[str, bytes]:
    parts: dict[str, bytes] = {}
    with zipfile.ZipFile(path, "r") as archive:
        for name in sorted(archive.namelist()):
            if not _is_semantic_part(name):
                continue
            parts[name] = _canonical_xml(archive.read(name))
    return parts


def workbook_semantic_sha256(path: Path) -> str:
    """Hash workbook semantics independently of XLSX ZIP metadata."""
    digest = hashlib.sha256()
    for name, payload in _semantic_parts(Path(path)).items():
        digest.update(name.encode("utf-8"))
        digest.update(b"\0")
        digest.update(payload)
        digest.update(b"\0")
    return digest.hexdigest()


def _append_difference(
    differences: list[str],
    message: str,
    *,
    max_differences: int,
) -> bool:
    if len(differences) < max_differences:
        differences.append(message)
    return len(differences) >= max_differences


def _diagnose_cell_differences(
    expected_path: Path,
    actual_path: Path,
    differences: list[str],
    *,
    max_differences: int,
) -> bool:
    """Add cell/formula diagnostics. Return True if the report was truncated."""
    from openpyxl import load_workbook

    expected = load_workbook(expected_path, data_only=False, read_only=True)
    actual = load_workbook(actual_path, data_only=False, read_only=True)
    truncated = False
    try:
        if expected.sheetnames != actual.sheetnames:
            truncated = _append_difference(
                differences,
                f"sheet order changed: expected {expected.sheetnames!r}, got {actual.sheetnames!r}",
                max_differences=max_differences,
            )
            if truncated:
                return True

        for sheet_name in (name for name in expected.sheetnames if name in actual.sheetnames):
            expected_sheet = expected[sheet_name]
            actual_sheet = actual[sheet_name]
            if (expected_sheet.max_row, expected_sheet.max_column) != (
                actual_sheet.max_row,
                actual_sheet.max_column,
            ):
                truncated = _append_difference(
                    differences,
                    f"{sheet_name}: dimensions changed from "
                    f"{expected_sheet.max_row}x{expected_sheet.max_column} to "
                    f"{actual_sheet.max_row}x{actual_sheet.max_column}",
                    max_differences=max_differences,
                )
                if truncated:
                    return True

            max_row = max(expected_sheet.max_row, actual_sheet.max_row)
            max_column = max(expected_sheet.max_column, actual_sheet.max_column)
            expected_rows = expected_sheet.iter_rows(
                min_row=1,
                max_row=max_row,
                min_col=1,
                max_col=max_column,
            )
            actual_rows = actual_sheet.iter_rows(
                min_row=1,
                max_row=max_row,
                min_col=1,
                max_col=max_column,
            )
            for expected_row, actual_row in zip(expected_rows, actual_rows):
                for expected_cell, actual_cell in zip(expected_row, actual_row):
                    if (
                        expected_cell.value != actual_cell.value
                        or expected_cell.data_type != actual_cell.data_type
                    ):
                        truncated = _append_difference(
                            differences,
                            f"{sheet_name}!{expected_cell.coordinate}: expected "
                            f"{expected_cell.value!r}, got {actual_cell.value!r}",
                            max_differences=max_differences,
                        )
                        if truncated:
                            return True
    finally:
        expected.close()
        actual.close()
    return truncated



def _diagnose_presentation_differences(
    expected_path: Path,
    actual_path: Path,
    differences: list[str],
    *,
    max_differences: int,
) -> bool:
    """Add human-readable worksheet presentation diagnostics on mismatch."""
    from openpyxl import load_workbook

    expected = load_workbook(expected_path, data_only=False, read_only=False)
    actual = load_workbook(actual_path, data_only=False, read_only=False)
    truncated = False
    try:
        for sheet_name in (name for name in expected.sheetnames if name in actual.sheetnames):
            expected_sheet = expected[sheet_name]
            actual_sheet = actual[sheet_name]
            pairs = (
                ("freeze_panes", str(expected_sheet.freeze_panes or ""), str(actual_sheet.freeze_panes or "")),
                ("auto_filter", expected_sheet.auto_filter.ref or "", actual_sheet.auto_filter.ref or ""),
                ("merged_ranges", tuple(sorted(str(item) for item in expected_sheet.merged_cells.ranges)), tuple(sorted(str(item) for item in actual_sheet.merged_cells.ranges))),
            )
            for label, expected_value, actual_value in pairs:
                if expected_value != actual_value:
                    truncated = _append_difference(
                        differences,
                        f"{sheet_name}: {label} changed: expected {expected_value!r}, got {actual_value!r}",
                        max_differences=max_differences,
                    )
                    if truncated:
                        return True
    finally:
        expected.close()
        actual.close()
    return truncated

def compare_workbooks(
    expected_path: Path,
    actual_path: Path,
    *,
    max_differences: int = 25,
) -> WorkbookComparison:
    """Compare workbook semantics; diagnose cells only when a mismatch exists."""
    expected_path = Path(expected_path)
    actual_path = Path(actual_path)
    expected_parts = _semantic_parts(expected_path)
    actual_parts = _semantic_parts(actual_path)
    if expected_parts == actual_parts:
        return WorkbookComparison(True, ())

    differences: list[str] = []
    changed_parts: list[str] = []
    for name in sorted(set(expected_parts) | set(actual_parts)):
        if name not in expected_parts:
            changed_parts.append(f"added XLSX part: {name}")
        elif name not in actual_parts:
            changed_parts.append(f"removed XLSX part: {name}")
        elif expected_parts[name] != actual_parts[name]:
            changed_parts.append(f"changed XLSX part: {name}")

    truncated = _diagnose_cell_differences(
        expected_path,
        actual_path,
        differences,
        max_differences=max_differences,
    )
    if not truncated:
        truncated = _diagnose_presentation_differences(
            expected_path,
            actual_path,
            differences,
            max_differences=max_differences,
        )
    if not differences:
        for message in changed_parts:
            if _append_difference(
                differences,
                message + " (values/formulas match; presentation or workbook metadata changed)",
                max_differences=max_differences,
            ):
                truncated = True
                break
    elif not truncated:
        remaining = max_differences - len(differences)
        for message in changed_parts[:remaining]:
            differences.append(message)
        if len(changed_parts) > remaining:
            truncated = True

    return WorkbookComparison(False, tuple(differences), truncated)


def build_manifest(reference_paths: dict[str, Path], *, source_revision: str | None) -> dict[str, Any]:
    """Build the versioned manifest for a freshly approved reference set."""
    references: dict[str, Any] = {}
    for workflow, path in reference_paths.items():
        references[workflow] = {
            "file": reference_workbook_path(workflow).relative_to(REFERENCE_ROOT).as_posix(),
            "sha256": _sha256_file(path),
            "semantic_sha256": workbook_semantic_sha256(path),
        }
    return {
        "schema_version": REFERENCE_SCHEMA_VERSION,
        "profile": "demo",
        "source_revision": source_revision,
        "fixtures": fixture_fingerprint(),
        "references": references,
    }


def write_manifest(manifest: dict[str, Any], path: Path | None = None) -> None:
    """Write a release-reference manifest to ``path`` or the committed location."""
    destination = Path(path) if path is not None else REFERENCE_MANIFEST_PATH
    destination.parent.mkdir(parents=True, exist_ok=True)
    with destination.open("w", encoding="utf-8", newline="\n") as stream:
        json.dump(manifest, stream, indent=4, ensure_ascii=False, sort_keys=True)
        stream.write("\n")


def verify_reference_files(manifest: dict[str, Any]) -> list[str]:
    """Return missing/corrupted-file diagnostics for committed references."""
    problems: list[str] = []
    references = manifest.get("references", {})
    for workflow, filename in REFERENCE_FILENAMES.items():
        entry = references.get(workflow)
        if not entry:
            problems.append(f"manifest is missing reference entry: {workflow}")
            continue
        path = REFERENCE_ROOT / entry.get("file", filename)
        if not path.exists():
            problems.append(f"reference workbook is missing: {path.relative_to(ROOT)}")
            continue
        if entry.get("sha256") != _sha256_file(path):
            problems.append(f"reference workbook changed outside the update workflow: {path.relative_to(ROOT)}")
    return problems


def format_differences(lines: Iterable[str], *, indent: str = "    ") -> str:
    return "\n".join(f"{indent}- {line}" for line in lines)
