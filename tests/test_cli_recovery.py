from core import paths
from core.profile_creation import create_profile
from core.profile_history import list_checkpoints
from cli.profile_recovery import profile_recovery_menu


def test_console_checkpoint_and_cancelled_restore(tmp_path, monkeypatch, capsys):
    monkeypatch.setattr(paths, 'PROFILES_ROOT', tmp_path)
    profile = create_profile('Console example', '', ['cross_check'])
    answers = iter(['C', 'Before edits', '', 'D', '', 'R', '1', 'cancel', '', '0'])
    monkeypatch.setattr('builtins.input', lambda _prompt: next(answers))
    profile_recovery_menu(profile)
    assert len(list_checkpoints(profile)) == 1
    output = capsys.readouterr().out
    assert 'Checkpoint saved.' in output
    assert 'No configuration contradictions detected.' in output
    assert 'Restore cancelled.' in output
