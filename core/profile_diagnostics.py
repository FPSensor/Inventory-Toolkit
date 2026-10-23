"""Read-only profile diagnostics with stable codes and configuration destinations."""
from collections import defaultdict
from dataclasses import asdict, dataclass
from pathlib import Path
import re

from core import paths
from core.configuration_manager import _CONFIG_MODELS
from core.json_documents import read_document
from core.profile_config import validate_config_header
from core.profile_metadata import validate_metadata
from core.setup_catalog import MODULE_LABELS


@dataclass(frozen=True)
class ProfileIssue:
    severity: str
    code: str
    message: str
    document: str
    module: str | None = None
    step: str | None = None


@dataclass(frozen=True)
class ProfileDiagnostics:
    profile: str
    checked: tuple[str, ...]
    issues: tuple[ProfileIssue, ...]

    @property
    def healthy(self):
        return not any(issue.severity == 'error' for issue in self.issues)

    def as_dict(self):
        return {'profile': self.profile, 'healthy': self.healthy,
                'checked': list(self.checked), 'issues': [asdict(issue) for issue in self.issues]}

    def render(self):
        lines = [f'Profile check — {self.profile}', f'Checked {len(self.checked)} configuration documents.']
        for issue in self.issues:
            lines.append(f'[{issue.severity.upper()} | {issue.code}] {issue.message}')
            lines.append(f'  {issue.document}' + (f' · {MODULE_LABELS[issue.module]} / {issue.step}' if issue.module and issue.step else ''))
        if not self.issues:
            lines.append('No configuration contradictions detected.')
        lines.append('This check does not read input workbooks or mark setup pages as reviewed.')
        return '\n'.join(lines)


def profile_directory(profile):
    """Only address a direct profile directory owned by this installation."""
    target = paths.profile_root(profile).resolve()
    if target.parent != paths.PROFILES_ROOT.resolve():
        raise ValueError('Choose a profile folder directly inside profiles/.')
    return target


def inspect_configuration(profile):
    issues, checked, documents = [], [], {}
    def add(code, message, document, module=None, step=None, severity='error'):
        issues.append(ProfileIssue(severity, code, message, document, module, step))
    try:
        root = profile_directory(profile)
        metadata = validate_metadata(read_document(root / 'profile.json'))
    except (ValueError, OSError) as exc:
        add('PROFILE_METADATA', str(exc), 'profile.json')
        return ProfileDiagnostics(profile, (), tuple(issues))
    modules = metadata.get('enabled_modules', list(MODULE_LABELS))
    logical_names = [name for name in _CONFIG_MODELS if name.startswith('general/') or name.split('/')[0] in modules]
    for logical in logical_names:
        relative = f'configs/{logical}.json'
        try:
            payload = read_document(root / relative)
            validate_config_header(root / relative, payload)
            documents[logical] = _CONFIG_MODELS[logical].model_validate(payload).model_dump()
            checked.append(relative)
        except (ValueError, OSError) as exc:
            add('CONFIG_DOCUMENT', str(exc), relative, logical.split('/')[0] if not logical.startswith('general/') else None)
    catalog = documents.get('general/catalog', {}).get('columns', {})
    network = documents.get('general/network', {})
    active = network.get('active', [])
    if len(set(active)) != len(active) or any(not name.strip() for name in active):
        add('LOCATION_NAMES', 'Location names must be nonempty and unique.', 'configs/general/network.json', 'stock_processing' if 'stock_processing' in modules else None, 'network')
    rules = documents.get('general/families', {}).get('rules', {})
    owners = defaultdict(set)
    for family, prefixes in rules.items():
        if not family.strip() or any(not prefix for prefix in prefixes):
            add('CATEGORY_RULE', 'Category names and prefixes must not be empty.', 'configs/general/families.json', severity='warning')
        for prefix in prefixes:
            owners[prefix].add(family)
    for prefix, families in owners.items():
        if len(families) > 1:
            add('PREFIX_CONFLICT', f'Prefix {prefix!r} belongs to multiple categories: {", ".join(sorted(families))}.', 'configs/general/families.json', severity='warning')

    def columns(mapping, module, step, *, optional=()):
        relative = f'configs/{module}/settings.json'
        used = {}
        for role, header in mapping.items():
            destination = step
            if role == 'category':
                destination = 'classification'
            elif module == 'stock_processing' and role == 'product':
                destination = 'stock_layout'
            elif module == 'yoy_reports':
                destination = ('yoy_period' if role in {'date_column', 'quantity_column', 'sales_column'}
                               else 'yoy_variants' if role == 'variant_column' else step)
            if not header.strip():
                if role not in optional:
                    add('COLUMN_REQUIRED', f'Configure the {role} column.', relative, module, destination)
            elif header in used:
                add('COLUMN_COLLISION', f'{role} and {used[header]} both use {header!r}. Choose distinct source columns.', relative, module, destination)
            else:
                used[header] = role

    def sheets(names, module, step):
        seen = set()
        for name in names:
            if not name.strip() or len(name) > 31 or re.search(r'[\[\]:*?/\\]', name) or name.startswith("'") or name.endswith("'"):
                add('SHEET_NAME', f'Invalid Excel sheet name: {name!r}. Use 1–31 characters without []:*?/\\ or boundary apostrophes.', f'configs/{module}/settings.json', module, step)
            if name.casefold() in seen:
                add('SHEET_COLLISION', f'Sheet name {name!r} is repeated (Excel ignores letter case).', f'configs/{module}/settings.json', module, step)
            seen.add(name.casefold())

    stock = documents.get('stock_processing/settings')
    if stock:
        module, relative = 'stock_processing', 'configs/stock_processing/settings.json'
        source, pricing = stock['input'], stock['pricing']
        quantities = source['quantity_columns'] or {name: name for name in active}
        deposits = source['deposit_columns'] if source['deposit_columns'] is not None else network.get('stock_database_columns', {})
        locations = list(quantities) if source['format'] == 'wide' else active
        mapping = {'product': source['article_column'] or catalog.get('article', '')}
        if source['family_mode'] == 'column':
            mapping['category'] = source['family_column']
        if source['format'] == 'wide':
            mapping.update({f'quantity for {name}': header for name, header in quantities.items()})
            mapping.update({f'deposit for {name}': header for name, header in deposits.items()})
        else:
            mapping['quantity'] = source['quantity_column']
            if source['branch_column']:
                mapping['location'] = source['branch_column']
            elif source['default_store'] not in active:
                add('STOCK_LOCATION', 'Choose an active default location for stock without a location column.', relative, module, 'stock_long')
        columns(mapping, module, 'stock_long' if source['format'] == 'long' else 'stock_input')
        if not locations:
            add('STOCK_LOCATIONS', 'Add at least one stock location.', 'configs/general/network.json', module, 'network')
        for side in ('cost', 'sales'):
            price = pricing[f'{side}_columns'] or pricing['columns']
            columns(price, module, f'stock_{side}', optional=('database',))
            if not price['database'] and pricing['default_store'] not in locations:
                add('PRICE_LOCATION', f'Choose a stock location for the {side} list without a location column.', relative, module, 'stock_price_location')
        required_cleaned = {catalog.get('article'), *locations, *deposits.values()}
        if source['family_mode'] == 'column':
            required_cleaned.add(source['family_column'])
        for column in sorted(set(stock['cleaning']['drop_columns']) & required_cleaned):
            add('DROP_REQUIRED', f'Cleanup removes required column {column!r}.', relative, module, 'stock_cleaning')
        for group, members in network.get('regional_groups', {}).items():
            unknown = sorted(set(members) - set(locations))
            if unknown:
                add('GROUP_LOCATIONS', f'Group {group!r} refers to unavailable stock locations: {unknown}.', 'configs/general/network.json', module, 'network_groups')
        sheets([stock['output']['raw_data_sheet'], *(entry['sheet_name'] for entry in stock['output']['summaries'])], module, 'stock_output')
        for summary in stock['output']['summaries']:
            unknown = set(summary['entities']) - set(locations) - set(network.get('regional_groups', {}))
            if unknown:
                add('SUMMARY_LOCATIONS', f'Summary {summary["sheet_name"]!r} has unknown entities: {sorted(unknown)}.', relative, module, 'stock_summaries')

    cross = documents.get('cross_check/settings')
    if cross:
        module = 'cross_check'
        source = cross['input']
        mapping = {'product': source['article_column'] or catalog.get('article', ''), 'quantity': source['quantity_column']}
        if source['family_mode'] == 'column':
            mapping['category'] = source['family_column']
        columns(mapping, module, 'cross_input')
        if source['count_mode'] == 'quantities':
            columns({'product': source['count_article_column'], 'quantity': source['count_quantity_column']}, module, 'cross_count_columns')
        for side in ('cost', 'sales'):
            columns(cross['price_lists'][side], module, f'cross_{side}')

    yoy = documents.get('yoy_reports/settings')
    if yoy:
        module = 'yoy_reports'
        source = yoy['input']
        mapping = {key: source[key] for key in ('date_column', 'quantity_column', 'branch_column', 'item_column')}
        if 'sales' in yoy['output']['metrics']:
            mapping['sales_column'] = source['sales_column']
        if yoy['output']['include_variants']:
            mapping['variant_column'] = source['variant_column']
        columns(mapping, module, 'yoy_products')
        if not yoy['groups'] or not any(yoy['groups'].values()):
            add('REPORT_GROUPS', 'Configure at least one sales comparison group.', 'configs/yoy_reports/settings.json', module, 'yoy_groups')
        for group, members in yoy['groups'].items():
            if not group.strip() or not members or any(not member.strip() for member in members) or len(set(members)) != len(members):
                add('REPORT_GROUP_MEMBERS', f'Group {group!r} needs unique nonempty location names.', 'configs/yoy_reports/settings.json', module, 'yoy_groups')
    return ProfileDiagnostics(profile, tuple(checked), tuple(issues))
