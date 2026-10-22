"""Shared module readiness overview for console and desktop frontends."""

from dataclasses import dataclass

from core.setup_catalog import MODULE_LABELS
from core.setup_service import SetupSession, SetupState
from core.workflow_errors import WorkflowError


@dataclass(frozen=True)
class ModuleOverview:
    module: str
    label: str
    state: SetupState | None
    reviewed: int | None
    total: int
    pending_step: str | None
    pending_titles: tuple[str, ...]
    issue: str | None = None

    @property
    def status(self):
        if self.issue:
            return "Needs attention"
        return {
            SetupState.NOT_CONFIGURED: "Not configured",
            SetupState.PARTIAL: "Partially configured",
            SetupState.COMPLETE: "Ready",
        }[self.state]


def inspect_profile(profile: str) -> tuple[ModuleOverview, ...]:
    """Explain setup state without treating operator review as file validation."""
    results = []
    for module, label in MODULE_LABELS.items():
        steps = ()
        try:
            session = SetupSession(profile, module)
            steps = session.steps
            state = session.state()
            fingerprints = session.reviewed()
            if fingerprints is None:
                reviewed, pending, pending_step = None, (), None
            else:
                pending_steps = [step for step in steps
                    if fingerprints.get(step.id) != session.fingerprint(step)]
                reviewed = len(steps) - len(pending_steps)
                if not pending_steps and state == SetupState.PARTIAL:
                    try:
                        session.validate_required()
                    except WorkflowError as exc:
                        pending_steps = [step for step in steps if step.id == exc.step]
                pending = tuple(step.title for step in pending_steps)
                pending_step = pending_steps[0].id if pending_steps else None
            results.append(ModuleOverview(module, label, state, reviewed, len(steps), pending_step, pending))
        except (OSError, ValueError, KeyError, TypeError) as exc:
            results.append(ModuleOverview(module, label, None, None, len(steps), None, (), str(exc)))
    return tuple(results)
