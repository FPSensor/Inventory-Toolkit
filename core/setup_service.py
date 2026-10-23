"""Persistent module setup with field review fingerprints and atomic writes."""
from copy import deepcopy
from enum import IntEnum
import hashlib
import json
import os
import tempfile

from core import paths
from core.configuration_manager import ConfigurationManager, _CONFIG_MODELS
from core.profile_config import ensure_profile_config
from core.setup_catalog import STEPS, get_value, set_value
from core.workflow_errors import ErrorCode, WorkflowError
from core.module_preferences import require_enabled


class SetupState(IntEnum):
    NOT_CONFIGURED = 0
    PARTIAL = 1
    COMPLETE = 2


def write_json(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, name = tempfile.mkstemp(dir=path.parent, prefix='.setup-', suffix='.tmp')
    try:
        with os.fdopen(fd, 'w', encoding='utf-8', newline='\n') as handle:
            json.dump(value, handle, indent=4, ensure_ascii=False)
            handle.write('\n')
        os.replace(name, path)
    finally:
        if os.path.exists(name):
            os.unlink(name)


def _read(path):
    try:
        return json.loads(path.read_text(encoding='utf-8'))
    except (ValueError, OSError) as exc:
        raise WorkflowError(ErrorCode.CONFIG_INVALID, f'Could not read configuration: {path.name}') from exc


def initialize_setup(profile):
    path = paths.profile_root(profile) / 'profile.json'
    data = _read(path)
    data['setup'] = {'version': 1, 'modules': {module: {'reviewed': {}} for module in STEPS}}
    write_json(path, data)


class SetupSession:
    def __init__(self, profile, module, *, include_advanced=False):
        if module not in STEPS:
            raise ValueError(f'Unknown workflow: {module}')
        require_enabled(profile, module)
        self.profile, self.module = profile, module
        self.all_steps = STEPS[module]
        self.include_advanced = include_advanced
        self.root = paths.profile_configs_root(profile)
        ensure_profile_config(self.root, logical_names={step.logical for step in self.all_steps})

    @property
    def steps(self):
        result = []
        for step in self.all_steps:
            if step.advanced and not self.include_advanced:
                continue
            if step.condition and get_value(self.data(step), tuple(step.condition[0].split('.'))) != step.condition[1]:
                continue
            result.append(step)
        return tuple(result)

    def data(self, step):
        data = _CONFIG_MODELS[step.logical].model_validate(_read(self.root / f'{step.logical}.json')).model_dump()
        if step.logical in {'stock_processing/settings', 'cross_check/settings'}:
            if not data['input']['article_column']:
                data['input']['article_column'] = _read(self.root / 'general/catalog.json')['columns']['article']
        if step.logical == 'stock_processing/settings':
            network = _read(self.root / 'general/network.json')
            data['input']['quantity_columns'] = data['input']['quantity_columns'] or {name: name for name in network['active']}
            if data['input']['deposit_columns'] is None:
                data['input']['deposit_columns'] = network['stock_database_columns']
            for side in ('cost', 'sales'):
                data['pricing'][f'{side}_columns'] = data['pricing'][f'{side}_columns'] or data['pricing']['columns'].copy()
            if not data['pricing']['default_store'] and len(network['active']) == 1:
                data['pricing']['default_store'] = network['active'][0]
            if not data['input']['default_store'] and len(network['active']) == 1:
                data['input']['default_store'] = network['active'][0]
        return data

    def fingerprint(self, step):
        data = self.data(step)
        values = [get_value(data, field.path) for field in step.fields]
        return hashlib.sha256(json.dumps(values, sort_keys=True).encode()).hexdigest()

    def metadata(self):
        path = paths.profile_root(self.profile) / 'profile.json'
        data = _read(path) if path.exists() else {}
        if not isinstance(data, dict):
            raise WorkflowError(ErrorCode.SETUP_STATE_INVALID, 'Profile metadata must be an object.')
        return data

    def reviewed(self):
        setup = self.metadata().get('setup')
        if setup is None:
            return None  # Existing profiles keep their pre-wizard lifecycle.
        if not isinstance(setup, dict) or setup.get('version') != 1 or not isinstance(setup.get('modules'), dict):
            raise WorkflowError(ErrorCode.SETUP_STATE_INVALID, 'Setup metadata is invalid; restore the profile metadata.')
        item = setup['modules'].get(self.module, {})
        if not isinstance(item, dict) or not isinstance(item.get('reviewed', {}), dict):
            raise WorkflowError(ErrorCode.SETUP_STATE_INVALID, 'Module setup metadata is invalid.')
        if item.get('legacy') is True:
            return None
        reviewed = item.get('reviewed', {})
        if not all(isinstance(key, str) and isinstance(value, str) for key, value in reviewed.items()):
            raise WorkflowError(ErrorCode.SETUP_STATE_INVALID, 'Setup reviews must contain field fingerprints.')
        return reviewed

    def effective_reviews(self):
        own = self.reviewed()
        if own is None:
            return None
        combined = dict(own)
        modules = self.metadata().get('setup', {}).get('modules', {})
        for step in self.steps:
            if step.shared and step.id not in own:
                fingerprint = self.fingerprint(step)
                if any(item.get('reviewed', {}).get(step.id) == fingerprint for item in modules.values() if isinstance(item, dict)):
                    combined[step.id] = fingerprint
        return combined

    def review_summary(self):
        lines = []
        for step in self.steps:
            data = self.data(step)
            for field in step.fields:
                value = get_value(data, field.path)
                if isinstance(value, (dict, list)):
                    value = f'{len(value)} configured entries'
                elif field.kind == 'choice':
                    value = next((label for label, stored in field.choices if stored == value), value)
                elif isinstance(value, bool):
                    value = 'Yes' if value else 'No'
                lines.append(f'{field.label}: {value if value != "" else "Not used"}')
        return lines

    def state(self):
        reviewed = self.reviewed()
        if reviewed is None:
            ConfigurationManager(self.profile, module=self.module)
            return SetupState.COMPLETE
        if not reviewed:
            return SetupState.NOT_CONFIGURED
        try:
            reviewed = self.effective_reviews()
            complete = all(reviewed.get(step.id) == self.fingerprint(step) for step in self.steps)
            if complete:
                self.validate_required()
                return SetupState.COMPLETE
        except (WorkflowError, KeyError, TypeError):
            pass
        return SetupState.PARTIAL

    def validate_required(self, *, include_sales=False, include_variants=False):
        for step in self.steps:
            raw = self.data(step)
            for field in step.fields:
                try:
                    value = get_value(raw, field.path)
                except (KeyError, TypeError):
                    value = None
                required = field.kind in {'column', 'text'} and not field.optional
                if self.module == 'yoy_reports':
                    if field.path == ('input', 'sales_column'):
                        required = include_sales
                    elif field.path == ('input', 'variant_column'):
                        required = include_variants or raw["output"]["include_variants"]
                if required and (not isinstance(value, str) or not value.strip()):
                    raise WorkflowError(ErrorCode.CONFIG_REQUIRED_FIELD,
                        f'{field.label} has not been configured.', module=self.module,
                        step=step.id, field='.'.join(field.path))
            try:
                _CONFIG_MODELS[step.logical].model_validate(raw)
            except ValueError as exc:
                raise WorkflowError(ErrorCode.CONFIG_INVALID,
                    f'Review {step.title}: one or more values are invalid.', module=self.module, step=step.id) from exc
        raw = self.data(next(s for s in self.steps if s.id == ('network' if self.module == 'stock_processing' else 'yoy_groups'))) if self.module != 'cross_check' else None
        if self.module == 'stock_processing' and not raw.get('active'):
            raise WorkflowError(ErrorCode.CONFIG_REQUIRED_FIELD, 'Add at least one active store.', module=self.module, step='network', field='active')
        if self.module == 'yoy_reports' and not any(raw.get('groups', {}).values()):
            raise WorkflowError(ErrorCode.CONFIG_REQUIRED_FIELD, 'Add at least one report group with a store.', module=self.module, step='yoy_groups', field='groups')

        if self.module == 'stock_processing':
            stock = self.data(next(s for s in self.steps if s.id == 'stock_layout'))
            if any(not stock['pricing'][f'{side}_columns']['database'] for side in ('cost', 'sales')) and not stock['pricing']['default_store']:
                raise WorkflowError(ErrorCode.CONFIG_REQUIRED_FIELD, 'Choose a location for price lists without a location column.', module=self.module, step='stock_price_location', field='pricing.default_store')
            if stock['input']['format'] == 'long' and not stock['input']['branch_column'] and stock['input']['default_store'] not in raw['active']:
                raise WorkflowError(ErrorCode.CONFIG_REQUIRED_FIELD, 'Choose an active location for row-based stock without a location column.', module=self.module, step='stock_long', field='input.default_store')

    def save_step(self, step_id, values):
        self.reviewed()  # Reject damaged metadata before changing a configuration file.
        step = next(s for s in self.all_steps if s.id == step_id)
        raw = deepcopy(self.data(step))
        for field in step.fields:
            value = values['.'.join(field.path)]
            if field.kind in {'column', 'text'} and not field.optional and (not isinstance(value, str) or not value.strip()):
                raise WorkflowError(ErrorCode.CONFIG_REQUIRED_FIELD, f'{field.label} cannot be empty.', module=self.module, step=step.id, field='.'.join(field.path))
            set_value(raw, field.path, value)
        try:
            _CONFIG_MODELS[step.logical].model_validate(raw)
        except ValueError as exc:
            raise WorkflowError(ErrorCode.CONFIG_INVALID, f'Review {step.title}: {exc}', module=self.module, step=step.id) from exc
        write_json(self.root / f'{step.logical}.json', raw)
        metadata = self.metadata()
        setup = metadata.setdefault('setup', {'version': 1, 'modules': {module: {'legacy': True, 'reviewed': {}} for module in STEPS}})
        reviewed = setup['modules'].setdefault(self.module, {'reviewed': {}})['reviewed']
        setup['modules'][self.module].pop('legacy', None)
        reviewed[step.id] = self.fingerprint(step)
        write_json(paths.profile_root(self.profile) / 'profile.json', metadata)

    def first_pending(self):
        reviewed = self.effective_reviews() or {}
        for step in self.steps:
            try:
                if reviewed.get(step.id) == self.fingerprint(step):
                    continue
            except (KeyError, TypeError, WorkflowError):
                pass
            return step.id
        return self.steps[0].id
