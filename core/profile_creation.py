"""Create portable profiles with neutral business defaults and selected workflows."""
import re
import shutil
import unicodedata

from core import paths
from core.build import BUILD
from core.json_documents import write_documents
from core.module_preferences import set_enabled_modules
from core.resource_config import load_resource
from core.configuration_manager import _CONFIG_MODELS
from core.setup_service import initialize_setup


def profile_slug(name):
    ascii_name = unicodedata.normalize("NFKD", name).encode("ascii", "ignore").decode().lower()
    slug = re.sub(r"[^a-z0-9_-]+", "_", ascii_name).strip("_-")
    reserved = {"con", "prn", "aux", "nul", *(f"com{i}" for i in range(1, 10)), *(f"lpt{i}" for i in range(1, 10))}
    if not slug or slug in reserved:
        raise ValueError("Choose a profile name containing letters or numbers and not a reserved device name.")
    return slug


def create_profile(name, description, modules, *, profile_id=None):
    if not name.strip():
        raise ValueError("Enter a profile name.")
    profile = profile_slug(profile_id or name)
    target = paths.profile_root(profile)
    target.mkdir(parents=True, exist_ok=False)
    try:
        data = load_resource("new_profile_defaults.json")
        documents = {target / 'configs' / f'{logical}.json': _CONFIG_MODELS[logical].model_validate(value).model_dump() for logical, value in data.items()}
        documents[target / 'profile.json'] = {'name': name.strip(), 'description': description.strip(), 'version': BUILD.version}
        write_documents(documents)
        set_enabled_modules(profile, modules)
        initialize_setup(profile)
        return profile
    except Exception:
        shutil.rmtree(target)
        raise
