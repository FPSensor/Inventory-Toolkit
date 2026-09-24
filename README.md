# Inventory Toolkit

![Python](https://img.shields.io/badge/Python-3.10+-blue)
![Platform](https://img.shields.io/badge/Platform-Windows%20%7C%20Linux%20%7C%20macOS-blue)
![License](https://img.shields.io/badge/License-MIT-green)
![Version](https://img.shields.io/badge/Version-1.4.0-orange)

Inventory Toolkit is an open-source toolkit for retail inventory processing.

It automates **Stock Processing**, **Inventory Cross Check (formerly Cruces)**, and **Year-over-Year (YoY) Sales Analysis** using Microsoft Excel workbooks while keeping business rules outside the source code through a profile-based configuration system.

The project was originally developed to solve real-world inventory problems and has since evolved into a reusable toolkit, usable either from an interactive command-line interface or from a native desktop GUI, and runs on Windows, Linux, and macOS.

---

# Features

- 📦 Stock Processing (`engine/stock_processing/`)
- 🔄 Inventory Cross Check (`engine/inventory_cross_check/`)
- 📊 Year-over-Year (YoY) Sales Reports with Monthly/Annual Segmentation and optional Size Breakdown (`engine/yoy_reports/`)
- 🧪 Experimental Desktop GUI (`gui/app.py`), Tkinter/CustomTkinter based; currently in active testing rather than a user-ready replacement for the CLI
- 🐧 Cross-Platform: Windows, Linux, and macOS launchers
- 👤 Multiple Profiles with Isolated Config Folders
- ⚙ JSON-based Configuration Subdirectories, validated against Pydantic schemas (`core/config_schemas.py`)
- 🖥 Interactive Command Line Interface (Internationalized in English)
- 🗂️ Persistent Per-Profile File Path Memory (pre-fills the last files used)
- 📂 Native File Picker
- 📊 Automatic Excel Column Detection
- 🔧 Module-oriented Guided Setup with per-workflow Excel auto-detection and readiness dashboard
- 🧭 Shared SKU/Family Classification with parity and performance diagnostics
- 🛡️ APB Protocol Validations & PermissionError Safe Savers
- 📝 Persistent Dual-Channel Logging (`logs/session.log`)
- 🧪 Automated Unit Testing with Pytest, plus Integrity Check and Stress Test diagnostic tools (`tools/`)

---

# Project Structure

InventoryToolkit/    
├── cli/    
│   ├── config_menu.py    
│   ├── cross_check_launcher.py    
│   ├── menu.py    
│   ├── profiles.py    
│   ├── stock_processing_launcher.py    
│   ├── utils.py    
│   ├── wizard.py    
│   └── yoy_reports_launcher.py    
├── core/    
│   ├── config_schemas.py    
│   ├── configuration_manager.py    
│   ├── data_sanitizer.py    
│   ├── logger.py    
│   ├── system_utils.py    
│   └── telemetry.py    
├── docs/    
│   ├── architecture.md    
│   ├── cli.md    
│   ├── core.md    
│   ├── dev_notes.md    
│   ├── engine.md    
│   ├── index.md    
│   ├── profiles.md    
│   └── testing_and_examples.md    
├── engine/    
│   ├── inventory_cross_check/    
│   │   ├── data_processor.py    
│   │   ├── excel_renderer.py    
│   │   └── generator.py    
│   ├── shared/    
│   │   └── families.py    
│   ├── stock_processing/    
│   │   ├── data_processor.py    
│   │   ├── excel_renderer.py    
│   │   └── generator.py    
│   └── yoy_reports/    
│       ├── data_processor.py    
│       ├── excel_renderer.py    
│       └── generator.py    
├── examples/    
│   └── demo/    
├── gui/    
│   └── app.py    
├── logs/    
├── profiles/    
│   └── demo/    
│       ├── configs/    
│       │   ├── general/            # catalog.json, families.json, network.json
│       │   ├── stock_processing/   # settings.json
│       │   ├── cross_check/        # settings.json
│       │   └── yoy_reports/        # settings.json
│       └── last_paths.json    
├── tests/    
│   ├── test_config.py    
│   ├── test_inventory_cross_check.py    
│   └── test_stock_processing.py    
├── tools/    
│   ├── IntegrityCheck.py    
│   └── StressTests.py    
├── CHANGELOG.md    
├── LICENSE    
├── README.md    
├── requirements.txt    
├── Inventory Toolkit.bat    
├── Inventory Toolkit.sh    
└── Setup Environment.bat    

---

# First Run

Inventory Toolkit includes two Windows launcher scripts.

### 1. Setup Environment.bat

Run this **only once** after cloning the repository.

It will:

- Install Python (if it doesnt exist)
- install dependencies
- prepare the project

### 2. Inventory Toolkit.bat

Launches Inventory Toolkit.

This is the file intended for everyday use, optimized with UTF-8 encoding support for terminal rendering.

On Linux and macOS, use **Inventory Toolkit.sh** instead (`./Inventory\ Toolkit.sh`).

---

# Desktop GUI (Experimental)

Inventory Toolkit includes an experimental desktop GUI (`gui/app.py`) covering the three workflows plus a graphical Configuration Hub. The GUI is still in active testing and is not yet considered the primary user-facing interface. It runs on Windows, Linux, and macOS, and uses CustomTkinter when installed, falling back to plain Tkinter/ttk otherwise.

Run it from the repository root as a module:

```bash
python -m gui.app
```

CustomTkinter is optional and is not installed by `requirements.txt`; the standard-library Tkinter fallback remains supported.

---

# Quick Start

1. Run **Setup Environment.bat** (first time only).
2. Run **Inventory Toolkit.bat**.
3. Create or select a profile.
4. Choose:

- Inventory Cross Check
- Stock Processing
- YoY Sales Report

5. Select the required Excel files and parameters.
6. Wait for processing to finish.

---

# Profiles

Inventory Toolkit separates business rules from the processing engine.

Each company can have its own independent profile under `profiles/<profile_name>/configs/`. Configuration v2 is module-oriented: shared catalog/network rules live under `general/`, while Stock Processing, Cross Check, and YoY each own a cohesive `settings.json`. The Configuration Hub and Guided Setup are the recommended editing surfaces.

Documentation:

➡ [docs/profiles.md](./docs/profiles.md)

---

# Example Dataset

A complete example dataset is included for testing.

Documentation:

➡ [examples/demo/README.md](examples/demo/README.md)

---

# Documentation

Comprehensive technical documentation is available inside the `docs/` folder, go and check it out:

➡ [docs/index.md](./docs/index.md)

---

# Testing

Run the automated test suite using `pytest`:

```bash
pytest tests/
``` 

# License    
MIT License