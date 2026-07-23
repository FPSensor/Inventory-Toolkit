# Inventory Toolkit

Inventory Toolkit is an open-source toolkit for inventory processing and reconciliation, designed to be configurable through external JSON files instead of hardcoded business rules.

The project started as an internal tool but is evolving into a generic inventory processing framework that can be adapted to different companies through profiles and configuration files.

> **Current version:** 1.1.0

---

# Features

- 📦 Stock processing
- 🔄 Inventory reconciliation
- ⚙️ JSON-based configuration system
- 👤 Profile support
- 🧩 Business rules externalized from the source code
- 📝 Example profile included
- ❤️ Open Source

---

# Project Structure

```
Inventory-Toolkit/
│
├── core/
│   └── configuration_manager.py
│
├── profiles/
│   └── demo/
│       ├── profile.json
│       ├── README.md
│       └── configs/
│           ├── familias.json
│           ├── databases.json
│           ├── schema.json
│           ├── cruces/
│           └── stocks/
│
├── Cruces.py
├── Stocks.py
├── CHANGELOG.md
└── requirements.txt
```

> **Note:** The processing scripts (`Cruces.py` and `Stocks.py`) are still located at the repository root. They will be moved into an `engine/` package in a future release once the CLI architecture is completed.

---

# Profiles

Inventory Toolkit now supports profiles.

A profile contains all business-specific configuration, allowing the same processing engine to work for different companies without modifying the source code.

Each profile contains:

- Company metadata
- JSON configuration files
- Processing rules
- Store definitions
- Product families
- Database mappings

The repository includes a demonstration profile:

```
profiles/demo/
```

This profile exists only as an example and contains no private company data.

---

# Configuration

Almost every business rule is now stored as JSON.

Examples include:

- Product families
- Cleaning rules
- Pricing configuration
- Store definitions
- Report configuration
- Reconciliation settings
- Database mappings

This makes the toolkit much easier to customize without modifying Python code.

---

# Philosophy

The goal of Inventory Toolkit is to separate:

- Processing Engine
- Business Configuration
- Company Profiles

This allows the same engine to be reused across completely different inventory systems.

---

# Roadmap

Planned improvements include:

- Modular CLI
- Engine package
- Plugin architecture
- Multiple profile support
- Automatic profile selection
- Interactive configuration wizard
- Better documentation

---

# License

This project is released as Open Source.

```

---

## Yo agregaría una sola nota más

Como esta es tu **primera versión pública seria**, agregaría arriba del README algo como:

```markdown
> ⚠️ Inventory Toolkit is under active development.
> While the core processing engine is stable, the project structure and CLI are still evolving.
```

Eso le avisa a cualquiera que vea el repositorio que la arquitectura todavía está creciendo y evita que alguien abra un Issue diciendo "¿por qué Cruces.py está en la raíz?". Además, cuando salga la 1.2.0 con `engine/` y el CLI modular, simplemente eliminás esa nota.
