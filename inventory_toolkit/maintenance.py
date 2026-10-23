"""Headless profile maintenance available in CLI-only and GUI-only builds."""
import argparse
import json
import sys


def main(argv):
    parser = argparse.ArgumentParser(prog='inventory_toolkit', description='Local profile diagnostics and recovery')
    commands = parser.add_subparsers(dest='command', required=True)
    doctor = commands.add_parser('doctor', help='Check profile configuration without changing it')
    doctor.add_argument('--profile', required=True)
    doctor.add_argument('--json', action='store_true', help='Print a machine-readable report')
    history = commands.add_parser('history', help='List, create or restore configuration checkpoints')
    actions = history.add_subparsers(dest='action', required=True)
    for name in ('list', 'create', 'restore'):
        action = actions.add_parser(name)
        action.add_argument('--profile', required=True)
        if name == 'create':
            action.add_argument('--label', default='Manual checkpoint')
        elif name == 'restore':
            action.add_argument('--checkpoint', required=True)
            action.add_argument('--yes', action='store_true', help='Confirm replacement of configuration without a terminal prompt')
    args = parser.parse_args(argv)
    try:
        if args.command == 'doctor':
            from core.profile_diagnostics import inspect_configuration
            report = inspect_configuration(args.profile)
            print(json.dumps(report.as_dict(), indent=2, ensure_ascii=False) if args.json else report.render())
            return 0 if report.healthy else 1
        from core.profile_history import create_checkpoint, list_checkpoints, restore_checkpoint
        if args.action == 'list':
            identifiers = list_checkpoints(args.profile)
            print('\n'.join(identifiers) if identifiers else 'No local checkpoints yet.')
        elif args.action == 'create':
            print(f'Created checkpoint: {create_checkpoint(args.profile, args.label)}')
        else:
            if not args.yes:
                if not sys.stdin.isatty():
                    parser.error('Restoring configuration requires --yes in non-interactive use.')
                answer = input(f'Restore configuration for {args.profile!r}? Type RESTORE to continue: ')
                if answer != 'RESTORE':
                    print('Restore cancelled.')
                    return 0
            safety = restore_checkpoint(args.profile, args.checkpoint)
            print(f'Configuration restored. Previous state saved as: {safety}')
        return 0
    except (OSError, ValueError, ImportError) as exc:
        print(f'Profile maintenance failed: {exc}', file=sys.stderr)
        return 2
