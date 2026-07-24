import json
from pathlib import Path

class ConfigurationError(Exception):
    """Excepción para errores críticos de configuración."""
    pass

class ConfigNode:
    """Nodo con caché para permitir acceso dual (por punto y por llave)."""
    def __init__(self, data_dict):
        self._data = data_dict
        self._cache = {}
        
    def __getattr__(self, key):
        if key in self._data:
            val = self._data[key]
            if isinstance(val, dict):
                if key not in self._cache:
                    self._cache[key] = ConfigNode(val)
                return self._cache[key]
            return val
        raise AttributeError(f"No existe la configuración '{key}'")

    def __getitem__(self, key):
        val = self._data[key]
        if isinstance(val, dict):
            if key not in self._cache:
                self._cache[key] = ConfigNode(val)
            return self._cache[key]
        return val

    def get(self, key, default=None):
        return self._data.get(key, default)


class ConfigurationManager:
    """Servicio encargado de escanear, cargar, indexar y validar la configuración por perfiles."""
    
    # CORRECCIÓN: profiles_root ahora es "profiles" por defecto
    def __init__(self, profile="demo", profiles_root="profiles"):
        # Se construye la ruta dinámica basada en el perfil
        self.profile = profile
        self.base_dir = Path(profiles_root) / self.profile / "configs"
        
        self._data = {}
        self._index = {}         # Índice plano O(1) para búsquedas instantáneas
        self._loaded_files = []  # Paths para el CLI
        self._cache = {}         # Caché raíz
        self.reload()

    def reload(self):
        """Limpia memoria, escanea el directorio recursivamente y valida."""
        self._data = {}
        self._index = {}
        self._loaded_files = []
        self._cache = {}
        self._load_directory(self.base_dir, self._data)
        self.validate()

    def _load_directory(self, current_dir, current_dict):
        if not current_dir.exists():
            raise ConfigurationError(f"Directorio base del perfil no encontrado: {current_dir}")

        for item in current_dir.iterdir():
            if item.is_dir():
                current_dict[item.name] = {}
                self._load_directory(item, current_dict[item.name])
            elif item.suffix == ".json" and item.name != "schema.json":
                try:
                    with open(item, 'r', encoding='utf-8') as f:
                        data = json.load(f)
                        current_dict[item.stem] = data
                        self._loaded_files.append(item.relative_to(self.base_dir))
                        # Poblamos el índice plano O(1) para la validación
                        self._index[item.stem] = data 
                except json.JSONDecodeError:
                    raise ConfigurationError(f"ERROR: JSON malformado en {item}")

    def validate(self):
        """Valida dinámicamente usando el índice O(1) contra schema.json."""
        schema_path = self.base_dir / "schema.json"
        if not schema_path.exists():
            return 
            
        with open(schema_path, 'r', encoding='utf-8') as f:
            schema = json.load(f)

        for category, rules in schema.items():
            target = self._index.get(category)
            if target is None:
                raise ConfigurationError(f"ERROR: Falta el archivo requerido por el schema: {category}.json")
                
            required = rules.get("required", [])
            for req in required:
                if req not in target:
                    raise ConfigurationError(f"ERROR: {category}.json\nMissing key: '{req}'")

    def check(self):
        """Impresión de estado de salud para debug o CLI."""
        print(f"Checking configuration for profile: '{self.profile}'...\n")
        
        for file in sorted(self._loaded_files):
            print(f"✓ {file.as_posix()}")
            
        if (self.base_dir / "schema.json").exists():
            print("✓ schema.json (Validation passed)")
            
        print("\nLoaded:")
        print(f"{len(self._loaded_files)} configuration files\n")
        print("Configuration OK")

    def __getattr__(self, key):
        if key in self._data:
            val = self._data[key]
            if isinstance(val, dict):
                if key not in self._cache:
                    self._cache[key] = ConfigNode(val)
                return self._cache[key]
            return val
        raise AttributeError(f"No existe la configuración '{key}'")

    def __getitem__(self, key):
        val = self._data[key]
        if isinstance(val, dict):
            if key not in self._cache:
                self._cache[key] = ConfigNode(val)
            return self._cache[key]
        return val

    # =========================================================
    # COMPATIBILIDAD CON ENGINE (Getters dinámicos O(1))
    # =========================================================
    def get_familias(self):
        return self._index.get("familias", {})
        
    def get_databases(self):
        return self._index.get("databases", {})
        
    def get_exclusions(self):
        return self._index.get("exclusions", {})
        
    def get_settings(self):
        return self._index.get("settings", {})
        
    def get_stores(self):
        return self._index.get("stores", {})
        
    def get_cleaning_rules(self):
        return self._index.get("cleaning", {})
        
    def get_reports(self):
        return self._index.get("reports", {})