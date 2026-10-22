"""Conservative, read-only header advice for guided setup samples."""

from dataclasses import dataclass
import re
import unicodedata

from core.resource_config import load_resource


@dataclass(frozen=True)
class ColumnAdvice:
    field: str
    configured: str
    present: bool
    suggestion: str | None = None
    reason: str = ""
    ambiguous: tuple[str, ...] = ()


def _normalized(value: str) -> str:
    decomposed = unicodedata.normalize("NFKD", str(value)).casefold()
    without_marks = "".join(char for char in decomposed if not unicodedata.combining(char))
    return " ".join(re.findall(r"[\w]+", without_marks, flags=re.UNICODE))


def advise_columns(fields, configured, headers):
    """Suggest only a unique best match; never change stored configuration."""
    hints = load_resource("column_hints.json")
    names = list(dict.fromkeys(str(header) for header in headers))
    result = []
    for field in fields:
        if field.kind != "column":
            continue
        key = ".".join(field.path)
        wanted = str(configured[key])
        if wanted in names:
            result.append(ColumnAdvice(key, wanted, True))
            continue

        normalized_wanted = _normalized(wanted)
        aliases = {_normalized(alias) for alias in hints.get(field.hint_key or "", [])}
        scores = {}
        for name in names:
            normalized_name = _normalized(name)
            if normalized_wanted and normalized_wanted == normalized_name:
                scores[name] = (3, "same name with different accents or punctuation")
            elif normalized_name in aliases:
                scores[name] = (2, "profile vocabulary match")
            elif any(alias and re.search(r"(?<!\w)" + re.escape(alias) + r"(?!\w)", normalized_name)
                     for alias in aliases):
                scores[name] = (1, "partial vocabulary match")

        best = max((score for score, _reason in scores.values()), default=0)
        candidates = tuple(name for name in names if name in scores and scores[name][0] == best)
        if len(candidates) == 1:
            chosen = candidates[0]
            result.append(ColumnAdvice(key, wanted, False, chosen, scores[chosen][1]))
        else:
            result.append(ColumnAdvice(key, wanted, False, ambiguous=candidates))
    return tuple(result)
