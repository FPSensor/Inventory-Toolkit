"""Console access to shared read-only checks and local configuration recovery."""
from cli.utils import clear_screen
from core.profile_diagnostics import inspect_configuration
from core.profile_history import checkpoint_info, create_checkpoint, list_checkpoints, restore_checkpoint


def profile_recovery_menu(profile):
    while True:
        clear_screen()
        print(f'\n  PROFILE CHECKS AND RECOVERY — {profile}\n')
        points = list_checkpoints(profile)
        for number, identifier in enumerate(points, 1):
            try:
                point = checkpoint_info(profile, identifier)
                print(f'  {number}. {point["label"]} — {point["created"]}')
            except (ValueError, OSError):
                print(f'  {number}. Unreadable checkpoint — {identifier}')
        if not points:
            print('  No local checkpoints yet. Setup saves one before changed settings.')
        print('\n  D. Check configuration (does not read workbooks)')
        print('  C. Save checkpoint now')
        print('  R. Restore a checkpoint')
        print('  0. Back')
        choice = input('\n  Choose an action: ').strip().upper()
        if choice == '0':
            return
        try:
            if choice == 'D':
                print('\n' + inspect_configuration(profile).render())
            elif choice == 'C':
                label = input('  Checkpoint label (Enter for Manual checkpoint): ').strip()
                create_checkpoint(profile, label or 'Manual checkpoint')
                print('  Checkpoint saved.')
            elif choice == 'R':
                selected = input('  Checkpoint number to restore (Enter to cancel): ').strip()
                if not selected:
                    continue
                if not selected.isdigit() or not 1 <= int(selected) <= len(points):
                    raise ValueError('Choose a checkpoint number from the list.')
                identifier = points[int(selected) - 1]
                print('  This replaces configuration and review state. The current state is saved first.')
                if input('  Type RESTORE to continue: ').strip() != 'RESTORE':
                    print('  Restore cancelled.')
                else:
                    safety = restore_checkpoint(profile, identifier)
                    print(f'  Configuration restored. Previous state saved as {safety}.')
            else:
                continue
        except (ValueError, OSError) as exc:
            print(f'  Could not complete the action: {exc}')
        input('\n  Press Enter to continue...')
