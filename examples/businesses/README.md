# Small-business verification scenarios

`scenarios.json` contains invented data and explicit configuration answers for three businesses. No data represents a real company.

| Scenario | Quantities | Stock layout | Product variant | Locations |
| --- | --- | --- | --- | --- |
| Kiosco | Whole units | One quantity column per location | Flavor | One |
| Verduleria | Fractional kg | One quantity per product row | Presentation | One |
| Almacen | Whole units | One quantity column per location | Package | Two |

Each scenario deliberately uses different product and category headers for Stock, Cross Check and YoY. Prices also have independent purchase and retail mappings. Source categories avoid an unnecessary prefix-maintenance task. The greengrocer uses measured physical quantities rather than pretending each scanner reading represents one kilogram.

## Reproduce the checks

From the development checkout:

```bash
python -m pytest -q tests/test_business_scenarios.py
```

The tests create temporary profiles through `create_profile`, then save each visible assistant page through `SetupSession.save_step`, the same setup service used by CLI and GUI. They assert completion before executing the real engines. No profile configurations are installed into your working profiles directory.

Coverage per business:

- Stock quantities, source categories, preserved product identifiers and purchase/retail valuations for every location.
- Four Cross Check combinations: consolidation on/off and partial count on/off, with independently specified expected differences and valuations.
- Sixty-four YoY combinations: full/monthly reports, annual comparison on/off, variants on/off, revenue on/off, item/category grouping, and provided/generated categories. Verify sheet count, one current quantity block per sheet, independently expected current quantities, and metric selection.

These are automated setup-service and engine checks, not a claim that a person manually completed every graphical page. Existing scanner, prefix, negative-stock and input-recovery tests cover additional contracts. Real widget tests cover desktop navigation separately.

## Lessons reflected in setup

- Location names are separate from source-file quantity headers.
- A single-location price list does not require a made-up origin column.
- Source categories and unclassified products work without prefix rules.
- Variants are optional and are separate from quantities or units of measure.
- Revenue means the **line total**, not the unit price; it is not multiplied by quantity a second time.
- Source quantities may be fractional. Display formats do not convert kg, units or currencies.

Mixed-unit aggregation, currency conversion, tax handling and accounting valuation methods are outside these scenarios. Configure comparable quantities and monetary conventions explicitly.
