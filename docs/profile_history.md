# Configuration checkpoints

`core.profile_history` keeps at most ten local checkpoints under `profiles/<id>/.history/`. A checkpoint contains `profile.json` and the six current configuration documents. Workbooks, remembered paths, logs and archived legacy data are excluded. History is ignored by Git and source distributions.

Creating a checkpoint requires the known profile documents to exist. Restoring verifies the checkpoint format, owned document paths, content checksums, profile metadata and enabled schema-v3 documents before replacing anything. Disabled workflow settings are retained verbatim, including invalid JSON that is intentionally not active.

A restore first saves the current state, then replaces the saved documents using the rollback-safe document writer. This supports undoing a restoration and recovering a missing live document. A safety copy of an already incomplete or damaged current state may require manual repair before it can itself be restored. Restore preserves the checkpoint's original bytes, including CRLF and UTF-8 BOM. Other files are not replaced.

Checkpoints are local convenience recovery, not an off-machine backup. Copy the profile folder to another location for a separate backup. Concurrent writers to the same profile remain unsupported; close the other application instance before editing or restoring.
