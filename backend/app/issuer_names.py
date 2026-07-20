import re

_LEGAL_FORM_PREFIX_RE = re.compile(
    r"^(?:"
    r"публичное\s+акционерное\s+общество|"
    r"акционерное\s+общество|"
    r"общество\s+с\s+ограниченной\s+ответственностью|"
    r"пao|пао|аo|ао|оo|ооо"
    r")\s+",
    re.IGNORECASE,
)
_LEGAL_FORM_SUFFIX_RE = re.compile(
    r"\s+(?:пao|пао|аo|ао|оo|ооо)$",
    re.IGNORECASE,
)
_BOND_SERIES_RE = re.compile(
    r"\s+(?:"
    r"б[оo]\s*[-]?\s*\d|"
    r"\d{3}[a-zа-я]?\s*[-]\s*\d|"
    r"001[prdst]?\s*[-]\s*\d|"
    r"облигаци|"
    r"биржев|"
    r"commercial|"
    r"series|"
    r"выпуск"
    r")",
    re.IGNORECASE,
)


def extract_issuer_search_query(
    *,
    ticker: str,
    name: str,
    sector: str,
    is_ofz: bool,
) -> str | None:
    if is_ofz or sector in {"government", "municipal"}:
        return None

    cleaned = name.strip().strip('"').strip("«»")
    series_match = _BOND_SERIES_RE.search(cleaned)
    if series_match:
        cleaned = cleaned[: series_match.start()].strip()

    cleaned = _LEGAL_FORM_PREFIX_RE.sub("", cleaned)
    cleaned = _LEGAL_FORM_SUFFIX_RE.sub("", cleaned)
    cleaned = cleaned.strip(" ,.-")

    if len(cleaned) >= 2:
        return cleaned

    fallback = re.sub(r"\d+", "", ticker).strip()
    return fallback or None
