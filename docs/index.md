# 📚 Inventory Toolkit: Master Technical Codex (v1.3.1)

> **System Status:** Production Ready & Bulletproof  
> **Target Audience:** Core Maintainers, System Analysts, and Data Engineers.

Welcome to the ultimate technical reference manual for **Inventory Toolkit**. This documentation covers not only *how* the system works, but *why* specific structural choices were made during its evolution from a basic script into a decoupled, highly modular data engine.

---

## 📑 Master Table of Contents

1. **[Architectural Blueprint & Philosophy](architecture.md)**
   * Why decoupling matters: The MVC-Data pattern.
   * Performance characteristics ($O(n)$ data streaming).
2. **[The Core Infrastructure (`/core`)](core.md)**
   * Configuration caching & JSON multi-tenant isolation.
   * Persistent logging and the *Bulletproof Safe Saver*.
3. **[Command Line Interface (`/cli`)](cli.md)**
   * Routing, argument-hiding design patterns, and Tkinter workflows.
   * The A.P.B. (A Prueba de Boludos) User Experience.
4. **[Engine Subsystems (`/engine`)](engine.md)**
   * `inventory_cross_check/`: Normalization and longest-prefix fuzzy matching.
   * `stock_processing/`: Dynamic multi-branch aggregation and margin math.
   * `yoy_reports/`: Time-series alignment and period slicing.
   * `shared/`: The central prefix-matching family matrix.
5. **[Profiles & Configurations (`/profiles`)](profiles.md)**
   * Schema enforcement and isolated tenant environments.
6. **[Testing Suite & Demo Datasets (`/tests` & `/examples`)](testing_and_examples.md)**
   * Pytest integration and mock retail datasets.
7. **[Development Logs & Operational Lore](dev_notes.md)**
   * From kernel logic structures to retail data pipelines. Fuel sources included.
