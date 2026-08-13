# Inventory Toolkit

![Python](https://img.shields.io/badge/Python-3.10+-blue)
![Platform](https://img.shields.io/badge/Platform-Windows-blue)
![License](https://img.shields.io/badge/License-MIT-green)
![Version](https://img.shields.io/badge/Version-1.2.0-orange)

Inventory Toolkit is an open-source toolkit for retail inventory processing.

It automates **Stock Processing**, **Inventory Reconciliation (Cruces)**, and **Year-over-Year (YoY) Sales Analysis** using Microsoft Excel workbooks while keeping business rules outside the source code through a profile-based configuration system.

The project was originally developed to solve real-world inventory problems and has since evolved into a reusable toolkit.

---

# Features

- 📦 Stock Processing
- 🔄 Inventory Reconciliation (Cruces)
- 📊 Year-over-Year (YoY) Sales Reports with Monthly/Annual Segmentation
- 👤 Multiple Profiles
- ⚙ JSON-based Configuration
- 🖥 Interactive Command Line Interface (with Unicode/Emoji support)
- 📂 Native File Picker
- 📊 Automatic Excel Column Detection
- 🪟 Windows Launcher Scripts
- 🔧 Configuration Wizard

---

# Project Structure

InventoryToolkit/

cli/
core/
engine/
profiles/
examples/

README.md
CHANGELOG.md
LICENSE

---

# First Run

Inventory Toolkit includes two Windows launcher scripts.

### 1. Setup Environment.bat

Run this **only once** after cloning the repository.

It will:

- create the Python virtual environment
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

- Stock Processing
- Inventory Reconciliation
- Generate YoY Sales Report

5. Select the required Excel files and parameters.
6. Wait for processing to finish.

---

# Profiles

Inventory Toolkit separates business rules from the processing engine.

Each company can have its own independent profile.

Documentation:

➡ **profiles/demo/README.md**

---

# Example Dataset

A complete example dataset is included for testing.

Documentation:

➡ **examples/demo/README.md**

---

# Documentation

Additional documentation is available inside each module.

| Module | Description |
|---------|-------------|
| cli | User Interface |
| core | Shared utilities |
| engine | Processing engines (Stock, Cruces, YoY Reports) |
| profiles/demo | Example configuration profile |
| examples/demo | Example spreadsheets |

---

# Roadmap

 - v1.3.0  Reports ✅    
 - v1.3.1  English migration    
 - v1.3.2  Stock/Cruces modularization    
 - v1.3.3  Logging    
 - v1.3.4  Testing    
 - v1.3.5  Documentation    

---

# License

MIT License