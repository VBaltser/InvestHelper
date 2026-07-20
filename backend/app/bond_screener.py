import asyncio
import time
import re
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from decimal import Decimal
from typing import Optional

from app.api_client import (
    get_bonds,
    get_last_prices,
    money_to_decimal,
    quotation_to_decimal,
)
from app.bond_math import calc_yield_to_maturity
from app.models import BondPortfolioMetric, BondScreenerItem, BondScreenerPageResponse
from app.ratings import get_credit_ratings

CACHE_TTL_SECONDS = 1800
_COUPON_CONCURRENCY = 20
_PRICE_BATCH_SIZE = 300
_ENRICH_BATCH_SIZE = 50

_base_cache: Optional[tuple[float, list[BondScreenerItem], dict[str, dict]]] = None
_enriched_figis: set[str] = set()
_build_lock = asyncio.Lock()

RISK_LEVEL_LABELS = {
    "RISK_LEVEL_LOW": "Низкий",
    "RISK_LEVEL_MODERATE": "Средний",
    "RISK_LEVEL_HIGH": "Высокий",
    "RISK_LEVEL_UNSPECIFIED": "—",
}

RATING_SORT_BASE = {
    "AAA": 22,
    "AA": 20,
    "A": 17,
    "BBB": 14,
    "BB": 11,
    "B": 8,
    "CCC": 5,
    "CC": 3,
    "C": 2,
    "D": 1,
}


@dataclass
class ScreenerQuery:
    page: int = 1
    page_size: int = 100
    sort_key: str = "yield_to_maturity"
    sort_dir: str = "desc"
    search: str = ""
    currency: str = "rub"
    sector: str = "all"
    ofz_only: bool = False
    hide_qual: bool = True
    hide_floating: bool = False
    min_yield: Optional[Decimal] = None
    min_years: Optional[Decimal] = None
    max_years: Optional[Decimal] = None
    min_rating: str = "all"
    refresh: bool = False


def _parse_timestamp(value: Optional[str]) -> Optional[datetime]:
    if not value:
        return None
    return datetime.fromisoformat(value.replace("Z", "+00:00"))


def _iso_now() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def _is_ofz(ticker: str, name: str) -> bool:
    ticker_upper = ticker.upper()
    name_upper = name.upper()
    return ticker_upper.startswith("SU") or "ОФЗ" in name_upper or "OFZ" in name_upper


def _risk_level_label(value: Optional[str]) -> Optional[str]:
    if not value:
        return None
    return RISK_LEVEL_LABELS.get(value, value)


def _estimate_annual_coupon(
    events: list[dict],
    coupon_per_year: int,
    now: datetime,
) -> tuple[Optional[Decimal], Optional[str]]:
    if not events:
        return None, None

    parsed: list[tuple[datetime, Decimal]] = []
    for event in events:
        coupon_date = _parse_timestamp(event.get("couponDate"))
        if coupon_date is None:
            continue
        parsed.append((coupon_date, money_to_decimal(event.get("payOneBond"))))

    if not parsed:
        return None, None

    parsed.sort(key=lambda item: item[0])
    future = [item for item in parsed if item[0] >= now]
    source = future if future else parsed

    next_date, next_value = source[0]
    horizon = now + timedelta(days=370)
    annual = sum(
        value for date, value in parsed if now - timedelta(days=7) <= date <= horizon
    )

    if annual <= 0:
        annual = next_value * Decimal(coupon_per_year or 1)

    return annual.quantize(Decimal("0.01")), next_date.date().isoformat()


def _coupon_schedule(events: list[dict], now: datetime) -> list[tuple[datetime, Decimal]]:
    schedule: list[tuple[datetime, Decimal]] = []
    for event in events:
        coupon_date = _parse_timestamp(event.get("couponDate"))
        if coupon_date is None:
            continue
        schedule.append((coupon_date, money_to_decimal(event.get("payOneBond"))))
    schedule.sort(key=lambda item: item[0])
    return schedule


def _calc_current_yield(
    nominal: Decimal,
    price_percent: Optional[Decimal],
    nkd: Decimal,
    annual_coupon: Optional[Decimal],
) -> Optional[Decimal]:
    if price_percent is None or annual_coupon is None or nominal <= 0:
        return None

    dirty_price = (nominal * price_percent / Decimal(100)) + nkd
    if dirty_price <= 0:
        return None

    return (annual_coupon / dirty_price * Decimal(100)).quantize(Decimal("0.01"))


async def _fetch_coupon_events(
    figi: str,
    date_from: str,
    date_to: str,
    semaphore: asyncio.Semaphore,
) -> list[dict]:
    from app.api_client import get_bond_coupons

    async with semaphore:
        for attempt in range(3):
            try:
                return await get_bond_coupons(figi, date_from, date_to)
            except Exception:
                if attempt < 2:
                    await asyncio.sleep(0.4 * (attempt + 1))
        return []


def _coupon_date_to(maturity: Optional[datetime], now: datetime) -> str:
    if maturity and maturity > now:
        return (maturity + timedelta(days=7)).isoformat().replace("+00:00", "Z")
    return (now + timedelta(days=365 * 5)).isoformat().replace("+00:00", "Z")


def _build_base_item(
    bond: dict,
    price_info: Optional[dict],
    now: datetime,
) -> BondScreenerItem:
    nominal = money_to_decimal(bond.get("nominal"))
    nkd = money_to_decimal(bond.get("aciValue"))
    price_percent = (
        quotation_to_decimal(price_info.get("price")) if price_info else None
    )
    price = (
        (nominal * price_percent / Decimal(100)).quantize(Decimal("0.01"))
        if price_percent is not None and nominal > 0
        else None
    )

    maturity = _parse_timestamp(bond.get("maturityDate"))
    years_to_maturity = None
    if maturity:
        days = (maturity - now).days
        if days > 0:
            years_to_maturity = (Decimal(days) / Decimal("365.25")).quantize(
                Decimal("0.01")
            )

    ticker = bond.get("ticker") or ""
    name = bond.get("name") or ticker
    sector = bond.get("sector") or ""

    return BondScreenerItem(
        figi=bond["figi"],
        ticker=ticker,
        name=name,
        isin=bond.get("isin") or "",
        currency=bond.get("currency") or "rub",
        sector=sector,
        exchange=bond.get("exchange") or "",
        nominal=nominal,
        price_percent=price_percent,
        price=price,
        nkd=nkd,
        maturity_date=maturity.date().isoformat() if maturity else None,
        years_to_maturity=years_to_maturity,
        coupon_per_year=int(bond.get("couponQuantityPerYear") or 0),
        next_coupon_date=None,
        annual_coupon=None,
        current_yield=None,
        floating_coupon=bool(bond.get("floatingCouponFlag")),
        perpetual=bool(bond.get("perpetualFlag")),
        amortization=bool(bond.get("amortizationFlag")),
        buy_available=bool(bond.get("buyAvailableFlag")),
        for_qual_investor=bool(bond.get("forQualInvestorFlag")),
        subordinated=bool(bond.get("subordinatedFlag")),
        is_ofz=_is_ofz(ticker, name),
        credit_rating=None,
        yield_to_maturity=None,
        risk_level=_risk_level_label(bond.get("riskLevel")),
    )


async def _build_base_cache() -> tuple[list[BondScreenerItem], dict[str, dict]]:
    now = datetime.now(timezone.utc)
    bonds_raw = await get_bonds()
    tradeable = [
        bond
        for bond in bonds_raw
        if bond.get("apiTradeAvailableFlag")
        and not bond.get("perpetualFlag")
        and (
            (maturity := _parse_timestamp(bond.get("maturityDate"))) is None
            or maturity > now
        )
    ]

    raw_by_figi = {bond["figi"]: bond for bond in tradeable}

    prices: dict[str, dict] = {}
    figis = [bond["figi"] for bond in tradeable]
    for index in range(0, len(figis), _PRICE_BATCH_SIZE):
        batch = figis[index : index + _PRICE_BATCH_SIZE]
        prices.update(await get_last_prices(batch))

    items = [
        _build_base_item(bond, prices.get(bond["figi"]), now)
        for bond in tradeable
    ]
    return items, raw_by_figi


async def _ensure_base_cache(
    refresh: bool = False,
) -> tuple[list[BondScreenerItem], dict[str, dict], str]:
    global _base_cache, _enriched_figis

    if refresh:
        _base_cache = None
        _enriched_figis = set()

    if _base_cache is not None:
        cached_at, items, raw_by_figi = _base_cache
        if time.time() - cached_at < CACHE_TTL_SECONDS:
            return items, raw_by_figi, datetime.fromtimestamp(
                cached_at, tz=timezone.utc
            ).isoformat().replace("+00:00", "Z")

    async with _build_lock:
        if not refresh and _base_cache is not None:
            cached_at, items, raw_by_figi = _base_cache
            if time.time() - cached_at < CACHE_TTL_SECONDS:
                return items, raw_by_figi, datetime.fromtimestamp(
                    cached_at, tz=timezone.utc
                ).isoformat().replace("+00:00", "Z")

        items, raw_by_figi = await _build_base_cache()
        cached_at = time.time()
        _base_cache = (cached_at, items, raw_by_figi)
        if refresh:
            _enriched_figis = set()
        return items, raw_by_figi, _iso_now()


async def _enrich_items(
    items: list[BondScreenerItem],
    raw_by_figi: dict[str, dict],
) -> None:
    global _enriched_figis

    pending = [item for item in items if item.figi not in _enriched_figis]
    if not pending:
        return

    now = datetime.now(timezone.utc)
    date_from = (now - timedelta(days=30)).isoformat().replace("+00:00", "Z")
    semaphore = asyncio.Semaphore(_COUPON_CONCURRENCY)

    coupon_tasks = []
    for item in pending:
        bond = raw_by_figi[item.figi]
        maturity = _parse_timestamp(bond.get("maturityDate"))
        coupon_tasks.append(
            _fetch_coupon_events(
                item.figi,
                date_from,
                _coupon_date_to(maturity, now),
                semaphore,
            )
        )
    coupon_results = await asyncio.gather(*coupon_tasks)

    rating_secids = [
        item.ticker
        for item in pending
        if item.sector not in {"government", "municipal"}
        and not item.is_ofz
        and item.ticker
    ]
    ratings_map = await get_credit_ratings(rating_secids)

    for item, coupon_events in zip(pending, coupon_results):
        bond = raw_by_figi[item.figi]
        nominal = item.nominal
        nkd = item.nkd
        price_percent = item.price_percent
        dirty_price = (
            (nominal * price_percent / Decimal(100)) + nkd
            if price_percent is not None
            else None
        )
        maturity = _parse_timestamp(bond.get("maturityDate"))
        coupon_per_year = int(bond.get("couponQuantityPerYear") or 0)

        annual_coupon, next_coupon_date = _estimate_annual_coupon(
            coupon_events, coupon_per_year, now
        )
        item.annual_coupon = annual_coupon
        item.next_coupon_date = next_coupon_date

        if item.floating_coupon:
            item.current_yield = None
            item.yield_to_maturity = None
        else:
            item.current_yield = _calc_current_yield(
                nominal, price_percent, nkd, annual_coupon
            )
            if (
                not item.amortization
                and dirty_price is not None
                and maturity is not None
                and dirty_price > 0
            ):
                schedule = _coupon_schedule(coupon_events, now)
                ytm = calc_yield_to_maturity(
                    dirty_price=dirty_price,
                    nominal=nominal,
                    maturity=maturity,
                    coupon_events=schedule,
                    now=now,
                )
                if ytm is not None and Decimal("-5") <= ytm <= Decimal("100"):
                    item.yield_to_maturity = ytm

        if item.sector in {"government", "municipal"} or item.is_ofz:
            item.credit_rating = "Гос."
        else:
            item.credit_rating = ratings_map.get(item.ticker) or None

        _enriched_figis.add(item.figi)


def _rating_sort_key(rating: Optional[str], for_asc: bool = False) -> int:
    if not rating:
        return 999 if for_asc else -1
    if rating == "Гос.":
        return 100

    normalized = rating.upper().strip()
    match = re.match(r"^([A-Z]{1,3})([+-])?$", normalized)
    if not match:
        return 998 if for_asc else 0

    base, modifier = match.group(1), match.group(2)
    base_score = RATING_SORT_BASE.get(base)
    if base_score is None:
        return 998 if for_asc else 0

    if modifier == "+":
        return base_score + 1
    if modifier == "-":
        return base_score - 1
    return base_score


def _apply_filters(items: list[BondScreenerItem], query: ScreenerQuery) -> list[BondScreenerItem]:
    search = query.search.strip().lower()

    filtered: list[BondScreenerItem] = []
    for bond in items:
        if query.currency != "all" and bond.currency != query.currency:
            continue
        if query.sector != "all" and bond.sector != query.sector:
            continue
        if query.ofz_only and not bond.is_ofz:
            continue
        if query.hide_qual and bond.for_qual_investor:
            continue
        if query.hide_floating and bond.floating_coupon:
            continue
        if query.min_years is not None:
            if (
                bond.years_to_maturity is None
                or bond.years_to_maturity < query.min_years
            ):
                continue
        if query.max_years is not None and bond.years_to_maturity is not None:
            if bond.years_to_maturity > query.max_years:
                continue
        if search:
            haystack = f"{bond.ticker} {bond.name} {bond.isin}".lower()
            if search not in haystack:
                continue
        filtered.append(bond)

    return filtered


def _bond_yield_value(bond: BondScreenerItem) -> Decimal:
    if bond.yield_to_maturity is not None:
        return bond.yield_to_maturity
    if bond.current_yield is not None:
        return bond.current_yield
    return Decimal("-1")


def _matches_min_yield(bond: BondScreenerItem, min_yield: Decimal) -> bool:
    value = _bond_yield_value(bond)
    return value >= min_yield


def _matches_min_rating(bond: BondScreenerItem, min_rating: str) -> bool:
    if not min_rating or min_rating == "all":
        return True
    if min_rating == "none":
        return bond.credit_rating is None
    if min_rating == "gov":
        return bond.credit_rating == "Гос."

    min_score = _rating_sort_key(min_rating, for_asc=False)
    if min_score <= 0:
        return True

    bond_score = _rating_sort_key(bond.credit_rating, for_asc=False)
    if bond_score < 0:
        return False
    return bond_score >= min_score


def _needs_enriched_filter(query: ScreenerQuery) -> bool:
    if query.min_yield is not None:
        return True
    return bool(query.min_rating and query.min_rating != "all")


def _matches_enriched_filters(bond: BondScreenerItem, query: ScreenerQuery) -> bool:
    if query.min_yield is not None and not _matches_min_yield(bond, query.min_yield):
        return False
    if query.min_rating and not _matches_min_rating(bond, query.min_rating):
        return False
    return True


def _sort_items(items: list[BondScreenerItem], query: ScreenerQuery) -> None:
    reverse = query.sort_dir != "asc"

    def pick(bond: BondScreenerItem):
        if query.sort_key == "ticker":
            return bond.ticker
        if query.sort_key == "current_yield":
            return bond.current_yield or Decimal("-1")
        if query.sort_key == "yield_to_maturity":
            return bond.yield_to_maturity or Decimal("-1")
        if query.sort_key == "credit_rating":
            return _rating_sort_key(bond.credit_rating, query.sort_dir == "asc")
        if query.sort_key == "sector":
            return bond.sector
        if query.sort_key == "years_to_maturity":
            return bond.years_to_maturity or Decimal("9999")
        if query.sort_key == "price_percent":
            return bond.price_percent or Decimal("-1")
        if query.sort_key == "maturity_date":
            return bond.maturity_date or ""
        if query.sort_key == "annual_coupon":
            return bond.annual_coupon or Decimal("-1")
        return bond.yield_to_maturity or Decimal("-1")

    items.sort(key=pick, reverse=reverse)


async def get_bond_screener_page(query: ScreenerQuery) -> BondScreenerPageResponse:
    items, raw_by_figi, cached_at = await _ensure_base_cache(query.refresh)
    sectors = sorted({bond.sector for bond in items if bond.sector})
    filtered = _apply_filters(items, query)

    page = max(query.page, 1)
    page_size = min(max(query.page_size, 1), 100)

    if _needs_enriched_filter(query):
        matched: list[BondScreenerItem] = []
        for batch_start in range(0, len(filtered), _ENRICH_BATCH_SIZE):
            batch = filtered[batch_start : batch_start + _ENRICH_BATCH_SIZE]
            await _enrich_items(batch, raw_by_figi)
            for bond in batch:
                if _matches_enriched_filters(bond, query):
                    matched.append(bond)

        _sort_items(matched, query)
        filtered_total = len(matched)
        start = (page - 1) * page_size
        page_items = matched[start : start + page_size]
    else:
        proxy = ScreenerQuery(
            page=query.page,
            page_size=query.page_size,
            sort_key=(
                "years_to_maturity"
                if query.sort_key
                in {"yield_to_maturity", "current_yield", "annual_coupon", "credit_rating"}
                else query.sort_key
            ),
            sort_dir=query.sort_dir,
        )
        _sort_items(filtered, proxy)
        filtered_total = len(filtered)
        start = (page - 1) * page_size
        page_items = filtered[start : start + page_size]
        await _enrich_items(page_items, raw_by_figi)
        _sort_items(page_items, query)

    return BondScreenerPageResponse(
        bonds=page_items,
        total=len(items),
        filtered_total=filtered_total,
        page=page,
        page_size=page_size,
        cached_at=cached_at,
        sectors=sectors,
    )


async def get_cached_portfolio_metrics(
    figis: list[str],
) -> dict[str, BondPortfolioMetric]:
    if not figis or _base_cache is None:
        return {}

    _, items, raw_by_figi = _base_cache
    by_figi = {item.figi: item for item in items}
    to_enrich = [by_figi[figi] for figi in figis if figi in by_figi]
    if not to_enrich:
        return {}

    await _enrich_items(to_enrich, raw_by_figi)

    result: dict[str, BondPortfolioMetric] = {}
    for figi in figis:
        item = by_figi.get(figi)
        if item is None or figi not in _enriched_figis:
            continue
        result[figi] = BondPortfolioMetric(
            figi=figi,
            yield_to_maturity=item.yield_to_maturity,
            credit_rating=item.credit_rating,
        )
    return result
