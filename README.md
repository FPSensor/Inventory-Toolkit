# Inventory Toolkit

![Python](https://img.shields.io/badge/Python-3.10+-blue)
![Platform](https://img.shields.io/badge/Platform-Windows-blue)
![License](https://img.shields.io/badge/License-MIT-green)
![Version](https://img.shields.io/badge/Version-1.2.0-orange)

Inventory Toolkit is an open-source toolkit for retail inventory processing.

It automates **Stock Processing** and **Inventory Reconciliation (Cruces)** using Microsoft Excel workbooks while keeping business rules outside the source code through a profile-based configuration system.

The project was originally developed to solve real-world inventory problems and has since evolved into a reusable toolkit.

---

# Features

- 📦 Stock Processing
- 🔄 Inventory Reconciliation (Cruces)
- 👤 Multiple Profiles
- ⚙ JSON-based Configuration
- 🖥 Interactive Command Line Interface
- 📂 Native File Picker
- 📊 Automatic Excel Column Detection
- 🪟 Windows Launcher Scripts
- 🔧 Configuration Wizard

---

# Project Structure

```
InventoryToolkit/

cli/
core/
engine/
profiles/
examples/

README.md
CHANGELOG.md
LICENSE
```

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

This is the file intended for everyday use.

---

# Quick Start

1. Run **Setup Environment.bat** (first time only).
2. Run **Inventory Toolkit.bat**.
3. Create or select a profile.
4. Choose:

- Stock Processing
- Inventory Reconciliation

5. Select the required Excel files.
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
| engine | Processing engines |
| profiles/demo | Example configuration profile |
| examples/demo | Example spreadsheets |

---

# Roadmap

- GUI
- Additional documentation
- Configuration templates
- Engine improvements
- Additional validation

---

# License

MIT License