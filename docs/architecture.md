# Architecture

Inventory Toolkit is organized around a simple rule: **presentation gathers intent, core provides infrastructure, engines own business processing, profiles own configurable business rules**.

The boundaries are pragmatic rather than ceremonial. Modules are split when doing so improves isolation, testing, or readability; the project does not force every workflow into an identical file count.

## High-level flow

```text
User / automation
      │
      ├── CLI (primary)
      └── GUI (experimental)
             │
             ▼
      Profile + parameters
             │
             ▼
      core infrastructure
      configuration / logging /
      sanitization / safe saving
             │
             ▼
           engine
      transformations +
      business calculations +
      workbook rendering
             │
             ▼
        Excel output
```

## Layer responsibilities

### Presentation — `cli/`, `cli.py`, `gui/`

Presentation code may:

- ask the user for files and options;
- choose/select profiles;
- perform lightweight pre-flight checks;
- inspect workbook headers for setup/autodetection;
- present Configuration Hub and Guided Setup;
- call engines;
- display progress/errors.

Presentation code should **not** reimplement stock reconciliation, family classification, valuation formulas, or YoY calculations.

The GUI must not rely on terminal input. Long-running GUI operations execute away from the Tk main thread and UI updates return to the main thread.

### Infrastructure — `core/`

Core owns cross-cutting concerns:

- schema-v3 configuration loading and validation;
- business-label constants;
- legacy configuration transition while it exists;
- data sanitization helpers;
- runtime logging and structured debug events;
- timing/telemetry helpers;
- safe Excel saving and locked-output behavior.

Core should not decide business results for a specific engine.

### Business processing — `engine/`

Engines own:

- transformations;
- reconciliation/valuation mathematics;
- report segmentation;
- Excel workbook structure and formulas;
- shared business algorithms such as family prefix classification.

Engines are callable directly from Python and must remain independent from CLI prompts.

### Configuration — `profiles/`

Profile storage is resolved through the canonical application paths in `core/paths.py`; it does not move with the process current working directory. User-supplied relative workbook paths remain caller-CWD-relative.

Profiles hold environment/business differences that should not require source-code forks. Current schema v3 gives each module clear ownership of its configuration.

## Business invariants

Several behaviors are more important than file/module layout and should be treated as contracts.

### Variable-length article normalization

Cross Check does not know article length in advance. `normalize_article()` uses the system article master:

1. sanitize the scanner value;
2. accept an exact master match when available;
3. otherwise find valid master articles that are prefixes of the scanner value;
4. choose the **longest** valid match;
5. if no match exists, return `REVISAR | <original>`.

A fixed slice such as `value[:9]` is not equivalent and would corrupt shorter/longer article codes.

### Longest-prefix family classification

Family rules may overlap (`01`, `001`, `008`, `0085`, etc.). The shared classifier preserves longest-prefix priority. Its current trie implementation is a performance choice; longest-prefix behavior is the invariant.

### Unknown data must remain visible

When the program cannot prove a scanner/article mapping, it marks the value for review rather than silently dropping or inventing a match.

### Release output is a contract

Approved demo output is stored as semantic golden masters. A refactor that claims to preserve business behavior should pass strict release certification without replacing those references.

## Configuration boundary

Current internal configuration uses English keys and version `3`. External workbook labels may remain Spanish because those labels are part of real input/output contracts.

`core/business_schema.py` defines canonical v1.x business vocabulary, while profile-owned column mappings may replace those labels at workbook boundaries. Engines should resolve configurable external names once, then operate on stable internal contracts rather than repeatedly hard-coding or threading source labels through business logic. Stock Processing applies this rule explicitly with private article/family pipeline keys and restores the configured labels only when projecting the final workbook.

Legacy v1/v2 storage and old API projections are temporary compatibility concerns, not the current architecture. See [legacy_compatibility.md](legacy_compatibility.md).

## Excel strategy

Pandas is used for flexible ingestion/transformation of messy workbook exports. OpenPyXL is used when workbook structure, formulas, styles, merged cells, filters, widths, and other presentation metadata matter.

This combination is deliberate: generic dataframe export is insufficient for the generated reports, while forcing every input through a database/ORM would add deployment complexity without solving the legacy-workbook problem.

## Failure strategy

Prefer explicit failure over silent corruption.

Examples:

- invalid typed configuration raises/blocks validation;
- locked output files use retry/copy behavior in the CLI and a typed non-interactive error for GUI callers;
- unresolved scanner articles are marked `REVISAR |`;
- stale golden masters are rejected when demo/profile fingerprints change;
- destructive compatibility retirement refuses to run until readiness checks pass.

## Evolution rule

Before introducing a new abstraction, ask whether it creates a real boundary. Cross Check and Stock Processing remain compact because their current processor/renderer/generator split is sufficient. YoY has more rendering modules because its formula/layout responsibilities became independently complex.
