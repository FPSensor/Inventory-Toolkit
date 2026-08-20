import json
from pathlib import Path
from core.logger import log

DEFAULT_SCHEMA = {
    "cleaning": {"required": ["columnas_a_eliminar", "columnas_texto_a_limpiar", "columnas_a_formatear"]},
    "stores": {"required": ["locales_activos"]},
    "settings": {"required": ["columna_articulo", "columna_familia"]}
}

class ConfigurationManager:
    def __init__(self, profile="demo"):
        self.profile = profile
        self.base_dir = Path("profiles") / profile / "configs"
        self._index = {}
        self.load_all()

    def load_all(self):
        if not self.base_dir.exists():
            log.warning(f"Profile directory not found: {self.base_dir}")
            return

        for path in self.base_dir.rglob("*.json"):
            key = path.stem
            try:
                with open(path, "r", encoding="utf-8") as f:
                    self._index[key] = json.load(f)
            except Exception as e:
                log.error(f"Error loading {path}: {e}")

        self.validate()

    def validate(self):
        schema_path = self.base_dir / "general" / "schema.json"
        if not schema_path.exists():
            schema_path = self.base_dir / "schema.json"
            
        schema = DEFAULT_SCHEMA
        if schema_path.exists():
            try:
                with open(schema_path, "r", encoding="utf-8") as f:
                    loaded_schema = json.load(f)
                    if loaded_schema:
                        schema = loaded_schema
            except Exception:
                schema = DEFAULT_SCHEMA

        for section, rules in schema.items():
            required_keys = rules.get("required", [])
            section_data = self._index.get(section, {})
            for rk in required_keys:
                if rk not in section_data:
                    log.warning(f"Validation Warning: '{section}.json' is missing required key '{rk}'.")

    def get_config(self, name, default=None):
        if default is None:
            default = {}
        return self._index.get(name, default)

    def get_familias(self): return self.get_config("familias")
    def get_databases(self): return self.get_config("databases")
    def get_settings(self): return self.get_config("settings")
    def get_stores(self): return self.get_config("stores")
    def get_cleaning_rules(self): return self.get_config("cleaning")
    def get_reports(self): return self.get_config("reports")
