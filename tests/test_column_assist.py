"""Header advice is conservative and independent of any particular profile."""

from core.column_assist import advise_columns
from core.setup_catalog import field


def test_exact_and_normalized_headers_are_distinct_from_suggestions():
    fields = (field('input.item', 'Item', '', hint_key='article_hints'),)
    assert advise_columns(fields, {'input.item': 'SKU'}, ['SKU'])[0].present
    result = advise_columns(fields, {'input.item': 'Item Code'}, ['Item-Code'])[0]
    assert result.suggestion == 'Item-Code'
    assert not result.present


def test_vocabulary_is_external_and_ambiguous_matches_are_never_guessed():
    fields = (field('input.item', 'Item', '', hint_key='article_hints'),)
    match = advise_columns(fields, {'input.item': 'Missing'}, ['SKU'])[0]
    assert match.suggestion == 'SKU'
    ambiguous = advise_columns(fields, {'input.item': 'Missing'}, ['SKU', 'item'])[0]
    assert ambiguous.suggestion is None
    assert ambiguous.ambiguous == ('SKU', 'item')
    assert advise_columns(fields, {'input.item': 'Missing'}, ['Random'])[0].suggestion is None


def test_advice_does_not_modify_the_mapping_or_require_a_sample_column():
    fields = (field('output.family', 'Family', '', hint_key='family_hints', sample_required=False),)
    values = {'output.family': 'Family'}
    advice = advise_columns(fields, values, ['SKU'])[0]
    assert not advice.present and advice.suggestion is None
    assert values == {'output.family': 'Family'}
