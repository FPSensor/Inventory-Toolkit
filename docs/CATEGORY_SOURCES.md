# Category sources

Stock and Cross Check each own `input.family_mode`:

| Value | Behavior |
| --- | --- |
| `column` | Read the configured `input.family_column` from this workflow's input. Blank category cells use the profile default category. |
| `rules` | Apply shared prefix rules, with the longest matching prefix taking priority. |
| `none` | Put every product in the profile default category. |

Configure this in the module assistant under **Where do your categories come from?**. New profiles start with `none`; existing profiles retain `rules`. Shared prefix rules remain editable in additional settings.

The stock input and Cross Check system input may use different category headers. A missing configured header fails inspection unless the operator explicitly selects an available default for that run. Cross Check refuses conflicting categories for the same product rather than choosing one arbitrarily.

YoY retains its independent source-family selection for each report. These settings do not change price, quantity or year-over-year calculations.
