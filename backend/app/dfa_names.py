import re
from datetime import date, datetime
from decimal import Decimal
from typing import Optional

# Код эмитента в тикере NDM_{CODE}-... -> читаемое имя (по Cbonds / открытым данным).
ISSUER_NAMES: dict[str, str] = {
    "ANYP": "AnyPlatform",
    "ASPC": "Aspect",
    "BARN": "Барн",
    "BLKH": "Black House",
    "BLTL": "Балтика",
    "BNFR": "Бонфар",
    "BTK": "БТК",
    "DGDE": "ДГДЕ",
    "DLAG": "Делаг",
    "DMVK": "Домовик",
    "DNTG": "Динтег",
    "ENTK": "Энтек",
    "ETLN": "Эталон",
    "FLWW": "Flowwow",
    "FOHM": "Фохм",
    "FRMP": "Ферма",
    "FSYS": "F.Systems",
    "GFNR": "Гефнер",
    "GLLR": "Галерея",
    "GLRX": "Глоракс",
    "GZTS": "Газтранс",
    "HLNB": "Хлебник",
    "ISCP": "Искра",
    "ITSM": "ITSM",
    "KNFS": "Конфидент",
    "KRVT": "Корвет",
    "MDSN": "Медскан",
    "NFSN": "Нафаня",
    "PKVV": "Пиков",
    "PNPZ": "Пеноплекс",
    "RDLN": "Редлайн",
    "REST": "Rest",
    "RLCT": "Реликт",
    "ROWI": "Rowi",
    "RSIN": "Росин",
    "RWB": "RWB",
    "TBNK": "Т-Банк",
    "TBNKD": "Т-Банк",
    "TBTC": "Т-Банк",
    "TECH": "Тех",
    "TENP": "TenChat",
    "TINS": "Т-Страхование",
    "TLVN": "Телевон",
    "TMLD": "Тимолд",
    "TRBE": "Турбo",
    "VHDG": "VHD Group",
    "VIS": "ВИС",
    "WBIN": "Wildberries",
    "WFMT": "Wformat",
}

GENERIC_PRODUCT_NAMES = frozenset(
    {
        "Долговой актив",
        "Цифровой актив",
        "Смарт-процент",
        "Арт-токен",
        "Поддержка художника",
        "Смарт-венчур",
    }
)

_TICKER_RE = re.compile(
    r"^NDM_(?P<issuer>[A-Z0-9]+)-(?P<series>[^-]+)-(?P<coupon>[^-]+)-(?P<maturity>[\d.]+(?:-\d+)?)$",
    re.IGNORECASE,
)


def parse_dfa_ticker(ticker: str) -> tuple[str, str, str, str]:
    match = _TICKER_RE.match((ticker or "").strip())
    if not match:
        return "", "", "", ""
    return (
        match.group("issuer").upper(),
        match.group("series").upper(),
        match.group("coupon").upper(),
        match.group("maturity"),
    )


def resolve_issuer_name(ticker: str) -> tuple[str, str]:
    code, _, _, _ = parse_dfa_ticker(ticker)
    if not code:
        return "", ""
    return code, ISSUER_NAMES.get(code, code)


def resolve_product_type(api_name: str) -> Optional[str]:
    name = (api_name or "").strip()
    if not name or name in GENERIC_PRODUCT_NAMES:
        return name if name in GENERIC_PRODUCT_NAMES else None
    return name


def _format_maturity_label(maturity_date: Optional[str]) -> str:
    if not maturity_date:
        return ""
    try:
        parsed = date.fromisoformat(maturity_date[:10])
    except ValueError:
        return maturity_date
    return parsed.strftime("%d.%m.%Y")


def build_display_name(
    *,
    ticker: str,
    api_name: str,
    yield_to_maturity: Optional[Decimal],
    maturity_date: Optional[str],
) -> tuple[str, str, Optional[str]]:
    issuer_code, issuer_name = resolve_issuer_name(ticker)
    product_type = resolve_product_type(api_name)

    parts: list[str] = []
    if issuer_name:
        parts.append(issuer_name)
    elif issuer_code:
        parts.append(issuer_code)

    if yield_to_maturity is not None and yield_to_maturity > 0:
        ytm_text = format(yield_to_maturity.quantize(Decimal("0.01")), "f").rstrip("0").rstrip(".")
        parts.append(f"{ytm_text}%")

    maturity_label = _format_maturity_label(maturity_date)
    if maturity_label:
        parts.append(f"погаш. {maturity_label}")

    if parts:
        display_name = ", ".join(parts[:2])
        if len(parts) > 2:
            display_name = f"{display_name} · {parts[2]}"
    else:
        display_name = api_name or ticker or "—"

    return issuer_name or issuer_code, display_name, product_type
