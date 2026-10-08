"""Console setup gating and structured, explicit recovery decisions."""
from cli.wizard import run_module_setup
from core.setup_service import SetupSession, SetupState
from core.configuration_errors import ConfigurationError
from core.workflow_errors import WorkflowError


def recover_configuration(profile, exc):
    if not isinstance(exc, WorkflowError):
        return False
    print(f'  [{exc.code.value}] {exc}')
    if exc.can_configure and input('  Configure this setting now? [y/N]: ').strip().lower() == 'y':
        run_module_setup(profile, exc.module, exc.step)
        print('  Configuration returned. Run again when ready; saved paths are retained.')
        return True
    return False


def launch_configured(profile, module, launch):
    try:
        session = SetupSession(profile, module)
        state = session.state()
        if state == SetupState.NOT_CONFIGURED:
            run_module_setup(profile, module)
            return
        if state == SetupState.PARTIAL:
            answer = input('  Module setup is partial. Continue with current settings? [y/N]: ').strip().lower()
            if answer != 'y':
                if input('  Complete setup now? [y/N]: ').strip().lower() == 'y':
                    run_module_setup(profile, module)
                return
        session.validate_required()
        launch(profile)
    except WorkflowError as exc:
        recover_configuration(profile, exc)
    except ConfigurationError as exc:
        print(f'  Profile configuration cannot be used: {exc}')
        input('  Press Enter to return...')
