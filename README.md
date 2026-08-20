# Inventory Toolkit

![Python](https://img.shields.io/badge/Python-3.10+-blue)
![Platform](https://img.shields.io/badge/Platform-Windows-blue)
![License](https://img.shields.io/badge/License-MIT-green)
![Version](https://img.shields.io/badge/Version-1.3.1-orange)

Inventory Toolkit is an open-source toolkit for retail inventory processing.

It automates **Stock Processing**, **Inventory Cross Check (formerly Cruces)**, and **Year-over-Year (YoY) Sales Analysis** using Microsoft Excel workbooks while keeping business rules outside the source code through a profile-based configuration system.

The project was originally developed to solve real-world inventory problems and has since evolved into a reusable toolkit.

---

# Features

- 📦 Stock Processing (`engine/stock_processing/`)
- 🔄 Inventory Cross Check (`engine/inventory_cross_check/`)
- 📊 Year-over-Year (YoY) Sales Reports with Monthly/Annual Segmentation (`engine/yoy_reports/`)
- 👤 Multiple Profiles with Isolated Config Folders
- ⚙ JSON-based Configuration Subdirectories
- 🖥 Interactive Command Line Interface (Internationalized in English)
- 📂 Native File Picker
- 📊 Automatic Excel Column Detection
- 🪟 Windows Launcher Scripts
- 🔧 Configuration Wizard
- 🛡️ APB Protocol Validations & PermissionError Safe Savers
- 📝 Persistent Dual-Channel Logging (`logs/session.log`)
- 🧪 Automated Unit Testing with Pytest

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
│   ├── configuration_manager.py    
│   ├── logger.py    
│   └── system_utils.py    
├── docs/    
│   ├── architecture.md    
│   ├── cli.md    
│   ├── configuration.md    
│   ├── core.md    
│   ├── dev_notes.md    
│   ├── development_and_apb.md    
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
├── logs/    
├── profiles/    
│   └── demo/    
│       └── configs/    
│           ├── cross_check/    
│           ├── general/    
│           ├── stock_processing/    
│           └── yoy_reports/    
├── tests/    
│   ├── test_config.py    
│   ├── test_inventory_cross_check.py    
│   └── test_stock_processing.py    
├── CHANGELOG.md    
├── LICENSE    
├── README.md    
├── requirements.txt    
├── Inventory Toolkit.bat    
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

Each company can have its own independent profile located inside `profiles/<profile_name>/configs/` with isolated subfolders for general, cross-check, stock processing, and YoY report settings.

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

# Roadmap    
 - v1.3.0 Reports ✅    
 - v1.3.1 Full Core Refactor (Migration, Modularization, APB, Logging, Testing, Docs) ✅    

# License    
MIT License