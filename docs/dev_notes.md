# Developer Notes

This file records engineering conventions that are easy to lose during refactors.

## Preserve business invariants before improving structure

A cleaner implementation is not an improvement if it changes approved business output accidentally.

For refactors that claim behavioral parity:

```bash
pytest -q
python tools/ReleaseCheck.py --release
```

should pass against existing golden masters.

## Do not "simplify" variable-length article normalization

Scanner values can append size/color data to article codes whose length varies. `normalize_article()` intentionally relies on the system master and longest valid prefix. A fixed substring length is not equivalent.

Unmatched input must remain visible as `REVISAR | <original>`.

## Longest-prefix classification is a contract

The family-classification implementation may change for performance, but overlapping prefix semantics must not. Benchmark changes and verify parity.

## Configuration ownership matters

Do not reintroduce cross-module dumping grounds such as a YoY config file containing Stock output settings.

Current ownership:

- `general/`: catalog/families/network;
- Stock: cleaning/pricing/output;
- Cross Check: filters/price-list mappings;
- YoY: input/output/report groups.

## Keep engines frontend-agnostic

Engine/core code must not assume a terminal exists. If user interaction is necessary, surface a typed condition/error and let CLI/GUI decide how to present it.

## Split modules only at real responsibility boundaries

A smaller file count is not automatically simpler; neither is a larger file count automatically more modular.

YoY has separate current/comparison/style/sheet/workbook renderers because those concerns became substantial independently. Cross Check and Stock remain more compact because their existing split is sufficient.

## Logging should explain execution, not leak datasets

Forensic mode should log counts, shapes, columns, decisions, timings, paths, and exceptions. Avoid wholesale row dumps or unnecessary business-data exposure.

## Golden masters are approval, not convenience

`--update-reference` is not a test-fix command. It changes the definition of correct expected output. Review candidates before committing.

<!-- BEGIN LEGACY_COMPATIBILITY -->
## Compatibility is temporary

Do not add new calls to legacy projections. The compatibility layer includes its own readiness/retirement tooling so the project can eventually delete it cleanly.

<!-- END LEGACY_COMPATIBILITY -->

## Documentation is part of the codebase contract

When changing:

- CLI options;
- project structure;
- configuration schema;
- workflow inputs/outputs;
- debug/release tooling;

update `CHANGELOG.md` and the affected README/module docs in the same change. Record post-release work under `Unreleased`; do not advance the application version or redate a released entry merely to describe ongoing development. Check the roadmap against implemented features before release preparation.

Keep implementation identifiers, comments and operator messages in English. External business labels belong in profile/bundled JSON resources. Use synthetic family/store configurations for generic regression tests; approved demo data remains in profile/fixture/reference files.

Patch commits use `sector: component: change`, the author `FPSensor <gkartyt@gmail.com>`, and a brief body explaining previous behavior, the change and the result. Split independent features into separate patches. Verify application in order and run release certification on the cumulative patched tree before sharing.

## About the easter eggs

Small harmless easter eggs exist in the CLI/source. They must never alter business output, configuration, release references, or engine behavior.
