# Optional developer tools

This package is included in debug source builds and omitted from release source builds. The application can start without it. `core.optional_debug` gates discovery using `build.prop`; the CLI imports the developer console only when requested.

```bash
python -m debug_tools release --release
python -m debug_tools integrity
python -m debug_tools stress
```

Implementations live here; the corresponding `tools/` Python files and `cli/debug_menu.py` remain source-checkout wrappers for documented older commands. They are not a restored pre-v3 profile/API migration layer.

The root manifest selects `type`, `control-type`, `default-control`, `ver` and `gui-stage`. The existing source distribution builder respects these boundaries. No binary bundle or cross-platform executable build is introduced by this structure.
