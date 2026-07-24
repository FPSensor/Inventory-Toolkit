# Core

The `core` package contains shared functionality used by the processing engine.

While the CLI handles user interaction and the engine performs processing, the core package provides reusable utilities shared across the project.

---

## Responsibilities

Typical responsibilities include:

- Configuration loading
- Shared helper functions
- Data normalization
- Validation
- Common processing routines

---

## Philosophy

Any code duplicated between processing modules should be moved into `core`.

This keeps the engine focused on inventory processing while centralizing reusable logic.

---

## Dependency Flow

```
CLI
 │
 ▼
Engine
 │
 ▼
Core
```

The dependency is intentionally one-directional.

- CLI depends on Engine
- Engine depends on Core
- Core should not depend on CLI

---

## Goal

The purpose of `core` is to reduce duplicated code and provide a stable foundation for Inventory Toolkit as new processing modules are added.