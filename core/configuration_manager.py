"""configuration_manager.py — Central config loader for Inventory Toolkit.

Loads all JSON files under profiles/<profile>/configs/ recursively and indexes
them by filename stem for fast lookup.
"""

import json
from pathlib import Path
from typing import Any, Dict

from core.config_schemas import (
    CleaningConfig,
    CrossCheckSettings,
    FamiliasConfig,
    PricingConfig,
    StoresConfig,
    YoYReportsConfig,
)
from core.logger import log


class ConfigurationManager:

  def __init__(self, profile: str = 'demo'):
    self.profile = profile
    self.base_dir = Path('profiles') / profile / 'configs'
    self._index: Dict[str, Any] = {}
    self._load_all()

  # ── Loading ──────────────────────────────────────────────────────────────

  def _load_all(self) -> None:
    """Recursively load every *.json under the profile's configs directory."""
    if not self.base_dir.exists():
      log.warning(f'Profile config dir not found: {self.base_dir}')
      return

    for json_file in self.base_dir.rglob('*.json'):
      try:
        with open(json_file, 'r', encoding='utf-8') as f:
          self._index[json_file.stem] = json.load(f)
      except Exception as e:
        log.error(f'Error loading {json_file.name}: {e}')
        if json_file.stem not in self._index:
          self._index[json_file.stem] = {}

  # ── Raw access ───────────────────────────────────────────────────────────

  def get_config(self, name: str, default: Any = None) -> Any:
    """Return the raw parsed JSON for *name* (filename stem)."""
    return self._index.get(name, default if default is not None else {})

  # ── Validated access ─────────────────────────────────────────────────────

  def _safe_validate(self, model_class, config_name: str):
    """Validate raw config against a Pydantic model; fall back to defaults on error."""
    raw = self.get_config(config_name)
    try:
      validated = model_class.model_validate(raw)
      return validated.model_dump()
    except Exception as e:
      log.error(
          f"ValidationError in '{config_name}.json': {e}. Using safe fallback."
      )
      fallback = model_class.model_validate({})
      return fallback.model_dump()

  # ── Typed accessors (used by engines) ────────────────────────────────────

  def get_familias(self) -> Dict[str, list]:
    return self._safe_validate(FamiliasConfig, 'familias')

  def get_stores(self) -> dict:
    return self._safe_validate(StoresConfig, 'stores')

  def get_cleaning_rules(self) -> dict:
    return self._safe_validate(CleaningConfig, 'cleaning')

  def get_pricing_rules(self) -> dict:
    return self._safe_validate(PricingConfig, 'pricing')

  def get_cross_check_settings(self) -> dict:
    return self._safe_validate(CrossCheckSettings, 'cross_check_settings')

  def get_reports(self) -> dict:
    return self._safe_validate(YoYReportsConfig, 'reports')

  def get_yoy_settings(self) -> dict:
    # Backward-compatible semantic alias used by the YoY workflow.
    return self.get_reports()

  # Raw dicts — no Pydantic overhead needed for these
  def get_databases(self) -> dict:
    return self.get_config('databases')

  def get_settings(self) -> dict:
    return self.get_config('settings')