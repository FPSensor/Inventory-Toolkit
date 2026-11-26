"""Run a report without questions, for schedulers and other programs."""

import argparse
import json
import sys
from dataclasses import fields

from core.runtime.paths import profile_root
from core.profiles.profile_store import load_last_paths
from core.setup.setup_service import SetupSession
from workflows import cross, stock, yoy

# Request field -> name under which interfaces remember it.
_FILES = {
    "stock": (stock, stock.StockRequest, {"stock": "stock", "cost": "cost", "sales": "sales"}),
    "cross": (cross, cross.CrossRequest, {"system": "system", "count": "count", "cost": "cost", "sales": "sales"}),
    "yoy": (yoy, yoy.YoYRequest, {"sales": "file"}),
}


def _parser():
    parser = argparse.ArgumentParser(
        prog="inventory_toolkit run", description="Create a report without questions.",
        epilog="Files default to the last ones used by the profile. Exit status: 0 created, 1 failed, 2 usage error.")
    reports = parser.add_subparsers(dest="report", required=True)
    for name, (_workflow, request, files) in _FILES.items():
        command = reports.add_parser(name)
        command.add_argument("--profile", required=True)
        command.add_argument("--json", action="store_true", help="Print a machine-readable result")
        for field in fields(request):
            if field.name in ("profile", *files):
                continue
            option = "--" + field.name.replace("_", "-")
            if field.type == "bool":
                command.add_argument(option, action=argparse.BooleanOptionalAction, default=field.default)
            else:
                command.add_argument(option, required=field.name in ("start", "end"), default=field.default)
        for role in files:
            command.add_argument(f"--{role}")
    return parser


def main(argv) -> int:
    values = vars(_parser().parse_args(argv))
    workflow, request_type, files = _FILES[values.pop("report")]
    as_json, profile = values.pop("json"), values["profile"]
    try:
        if not profile_root(profile).is_dir():
            raise ValueError(f"Profile not found: {profile}")
        SetupSession(profile, workflow.MODULE).validate_required()
        saved = load_last_paths(profile).get(workflow.MODULE, {})
        for role, remembered in files.items():
            values[role] = values[role] or saved.get(remembered, "")
        values["output"] = values["output"] or saved.get("out", "")
        request = request_type(**values)
        result = workflow.prepare(request, workflow.check(request)).run()
    except Exception as exc:
        code = getattr(getattr(exc, "code", None), "value", type(exc).__name__)
        if as_json:
            print(json.dumps({"ok": False, "code": code, "error": str(exc)}, ensure_ascii=False))
        else:
            print(f"[{code}] {exc}", file=sys.stderr)
        return 1
    if as_json:
        print(json.dumps({"ok": True, "output": result.output, "seconds": round(result.elapsed, 2),
                          "warnings": list(result.warnings)}, ensure_ascii=False))
    else:
        print(result.output)
        for warning in result.warnings:
            print(f"Warning: {warning}", file=sys.stderr)
    return 0
