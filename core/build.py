"""One validated, CWD-independent manifest for runtime capabilities."""
from dataclasses import dataclass
from pathlib import Path

from core.paths import APPLICATION_ROOT


@dataclass(frozen=True)
class BuildInfo:
    version: str
    type: str
    control_type: str
    default_control: str
    gui_stage: str

    def supports(self, interface):
        return interface in {"cli", "gui"} and self.control_type in {interface, "both"}

    def require(self, interface):
        if not self.supports(interface):
            raise RuntimeError(f"This build does not include the {interface.upper()} interface.")


def load_build(path: Path | None = None) -> BuildInfo:
    values = {}
    for number, line in enumerate((path or APPLICATION_ROOT / "build.prop").read_text(encoding="utf-8").splitlines(), 1):
        line = line.strip()
        if not line or line.startswith("#"):
            continue
        if "=" not in line:
            raise ValueError(f"Invalid build property at line {number}.")
        key, value = (part.strip() for part in line.split("=", 1))
        if key in values:
            raise ValueError(f"Duplicate build property: {key}")
        values[key] = value
    if set(values) != {"ver", "type", "control-type", "default-control", "gui-stage"}:
        raise ValueError("Build manifest has missing or unknown properties.")
    if values["type"] not in {"debug", "release"}:
        raise ValueError("Build type must be debug or release.")
    if values["control-type"] not in {"cli", "gui", "both"}:
        raise ValueError("Control type must be cli, gui or both.")
    if not values["ver"] or not values["gui-stage"]:
        raise ValueError("Build version and GUI stage cannot be empty.")
    build = BuildInfo(values["ver"].removeprefix("v"), values["type"], values["control-type"], values["default-control"], values["gui-stage"])
    build.require(build.default_control)
    return build


BUILD = load_build()
