#!/usr/bin/env python3
"""Create a source distribution from an explicit allowlist, without work files."""

from pathlib import Path
from zipfile import ZipFile, ZIP_DEFLATED
import argparse


ROOT = Path(__file__).resolve().parents[1]
SOURCE_DIRS = ("cli", "core", "engine", "gui", "tools", "tests", "docs")
ROOT_FILES = (
    "cli.py", "requirements.txt", "pytest.ini", "README.md", "CHANGELOG.md",
    "LICENSE", "Inventory Toolkit.sh", "Inventory Toolkit.bat", "Setup Environment.bat",
)


def distribution_files():
    for name in ROOT_FILES:
        path = ROOT / name
        if path.is_file():
            yield path
    for name in SOURCE_DIRS:
        for path in sorted((ROOT / name).rglob("*")):
            if path.is_file() and path.suffix in {".py", ".md", ".json", ".xlsx"}:
                yield path
    for name in ("examples/demo", "profiles/demo"):
        for path in sorted((ROOT / name).rglob("*")):
            if path.is_file() and path.suffix in {".json", ".xlsx", ".xls", ".md"}:
                yield path


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("output", type=Path, help="destination .zip path")
    args = parser.parse_args()
    output = args.output.resolve()
    if output.suffix.lower() != ".zip":
        parser.error("output must end in .zip")
    output.parent.mkdir(parents=True, exist_ok=True)
    with ZipFile(output, "w", ZIP_DEFLATED) as archive:
        for path in distribution_files():
            archive.write(path, arcname=Path("Inventory-Toolkit") / path.relative_to(ROOT))
    print(f"Created {output}")


if __name__ == "__main__":
    main()
