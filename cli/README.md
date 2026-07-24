# CLI Module

The `cli` package contains the complete user interface for Inventory Toolkit.

It is responsible for interacting with the user while keeping all business logic inside the processing engine.

---

## Responsibilities

- Main application menu
- Profile selection
- Profile creation wizard
- Configuration editor
- File selection
- Validation
- User prompts
- Launching Stock Processing
- Launching Inventory Reconciliation

---

## Modules

| Module | Purpose |
|---------|---------|
| menu.py | Main application entry point |
| profiles.py | Profile management |
| wizard.py | Automatic profile initialization |
| config_menu.py | Interactive JSON editor |
| stocks.py | Stock Processing launcher |
| cruces.py | Inventory Reconciliation launcher |
| utils.py | Shared CLI utilities |

---

## Design Philosophy

The CLI should never contain business rules.

Its purpose is only to:

- collect user input
- validate files
- prepare arguments
- invoke the processing engine

All inventory logic belongs inside the engine.

---

## Workflow

```
User

↓

CLI

↓

Engine

↓

Excel Output
```

---

## Future Improvements

- Progress bars
- Colored output
- Better validation messages
- Linux support
- macOS support