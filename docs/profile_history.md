# Configuration checkpoints

`core.profile_history` keeps at most ten local checkpoints under `profiles/<id>/.history/`. A checkpoint contains `profile.json` and the six current configuration documents. Workbooks, remembered paths, logs and archived legacy data are excluded. History is ignored by Git and source distributions.

Creating a checkpoint requires the known configuration documents to exist. Existing profiles without metadata remain supported; checkpoints record its absence and restore that absence exactly. Restoring verifies the checkpoint format, owned document paths, content checksums, profile metadata and enabled schema-v3 documents before replacing anything. Disabled workflow settings are retained verbatim, including invalid JSON that is intentionally not active.

A restore first saves the current state, then replaces the saved documents using the rollback-safe document writer. This supports undoing a restoration and recovering a missing live document. A safety copy of an already incomplete or damaged current state may require manual repair before it can itself be restored. Restore preserves the checkpoint's original bytes, including CRLF and UTF-8 BOM. Other files are not replaced.

Checkpoints are local convenience recovery, not an off-machine backup. Copy the profile folder to another location for a separate backup. Concurrent writers to the same profile remain unsupported; close the other application instance before editing or restoring.

Setup automatically checkpoints the current profile before saving a changed page. Changing enabled workflows also checkpoints an existing profile. Saving identical values and review state does not generate another checkpoint; initial profile creation starts with empty history. A failed checkpoint prevents the corresponding configuration edit from proceeding.

## Headless commands

```bash
python -m inventory_toolkit history list --profile demo
python -m inventory_toolkit history create --profile demo --label "Before weekend edits"
python -m inventory_toolkit history restore --profile demo --checkpoint IDENTIFIER
```

Copy an identifier from the list. Interactive restore asks for `RESTORE`; automation requires an explicit `--yes`. Close other Inventory Toolkit instances before restoring. Headless maintenance is available even when a build contains only the GUI.

The console provides the same actions under **Configuration → H**. Checkpoints display a human label and timestamp; interactive restoration selects a list number rather than requiring an identifier to be typed.

The GUI exposes the same history in **Overview → Check profile / restore configuration**, with inline confirmation and background file operations. Leave the panel after maintenance to refresh the normal workflow overview.
