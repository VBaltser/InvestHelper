import asyncio
import time
from dataclasses import dataclass
from datetime import datetime, timezone
from decimal import Decimal
from typing import Optional

from app.api_client import get_dfas, get_last_prices, money_to_decimal, quotation_to_decimal
from app.dfa_math import calc_dfa_yield_to_maturity
from app.dfa_names import build_display_name
from app.models import DfaScreenerItem, DfaScreenerPageResponse

CACHE_TTL_SECONDS = 1800
_PRICE_BATCH_SIZE = 300

_cache: Optional[tuple[float, list[DfaScreenerItem]]] = None
_build_lock = asyncio.Lock()


@dataclass
class DfaScreenerQuery:
    page: int = 1
    page_size: int = 100
    sort_key: str = "yield_to_maturity"
    sort_dir: str = "desc"
    search: str = ""
    currency: str = "rub"
    buy_only: bool = False
    hide_qual: bool = True
    min_yield: Optional[Decimal] = None
    min_years: Optional[Decimal] = None
    max_years: Optional[Decimal] = None
    refresh: bool = False


def _parse_timestamp(value: Optional[str]) -> Optional[datetime]:
    if not value:
        return None
    return datetime.fromisoformat(value.replace("Z", "+00:00"))


def _iso_now() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def _years_to_maturity(maturity: datetime | None, now: datetime) -> Decimal | None:
    if maturity is None:
        return None
    days = (maturity - now).days
    if days <= 0:
        return None
    return (Decimal(days) / Decimal("365.25")).quantize(Decimal("0.01"))


def _build_item(raw: dict, price_info: dict | None, now: datetime) -> DfaScreenerItem:
    nominal = money_to_decimal(raw.get("nominal"))
    price = quotation_to_decimal(price_info.get("price")) if price_info else Decimal(0)
    if price <= 0 and nominal > 0:
        price = nominal

    price_percent = None
    if nominal > 0 and price > 0:
        price_percent = (price / nominal * Decimal(100)).quantize(Decimal("0.01"))

    maturity = _parse_timestamp(raw.get("maturityDate"))
    coupon_value = money_to_decimal(raw.get("couponValue"))
    coupon_freq = int(raw.get("couponPaymentFrequency") or 0)
    annual_coupon = None
    if coupon_value > 0 and coupon_freq > 0:
        annual_coupon = (coupon_value * Decimal(coupon_freq)).quantize(Decimal("0.01"))

    nkd = money_to_decimal(raw.get("aciValue"))
    dirty_price = (price + nkd) if price > 0 else None
    next_coupon = _parse_timestamp(raw.get("couponPaymentDate"))

    api_ytm = quotation_to_decimal(raw.get("yieldToMaturity"))
    if api_ytm <= 0:
        api_ytm = None

    ytm = None
    if dirty_price is not None and maturity is not None:
        ytm = calc_dfa_yield_to_maturity(
            dirty_price=dirty_price,
            nominal=nominal,
            maturity=maturity,
            next_coupon=next_coupon,
            coupon_value=coupon_value,
            coupon_per_year=coupon_freq,
            now=now,
        )
    if ytm is None:
        ytm = api_ytm

    ticker = raw.get("ticker") or "—"
    api_name = raw.get("name") or ticker
    issuer_name, display_name, product_type = build_display_name(
        ticker=ticker,
        api_name=api_name,
        yield_to_maturity=ytm,
        maturity_date=maturity.date().isoformat() if maturity else None,
    )

    return DfaScreenerItem(
        uid=raw.get("uid") or "",
        ticker=ticker,
        name=display_name,
        display_name=display_name,
        issuer_name=issuer_name,
        product_type=product_type,
        currency=(raw.get("currency") or "rub").lower(),
        nominal=nominal,
        price=price if price > 0 else None,
        price_percent=price_percent,
        nkd=nkd,
        maturity_date=maturity.date().isoformat() if maturity else None,
        years_to_maturity=_years_to_maturity(maturity, now),
        coupon_per_year=coupon_freq,
        coupon_value=coupon_value if coupon_value > 0 else None,
        next_coupon_date=raw.get("couponPaymentDate"),
        annual_coupon=annual_coupon,
        yield_to_maturity=ytm,
        yield_at_nominal=api_ytm,
        buy_available=bool(raw.get("buyAvailableFlag")),
        sell_available=bool(raw.get("sellAvailableFlag")),
        for_qual_investor=bool(raw.get("forQualInvestorFlag")),
    )


async def _build_cache() -> list[DfaScreenerItem]:
    now = datetime.now(timezone.utc)
    raw_items = [
        item
        for item in await get_dfas("INSTRUMENT_STATUS_ALL")
        if item.get("type") == "debt_dfa"
    ]

    active: list[dict] = []
    for item in raw_items:
        maturity = _parse_timestamp(item.get("maturityDate"))
        if maturity is not None and maturity <= now:
            continue
        active.append(item)

    uids = [item["uid"] for item in active if item.get("uid")]
    prices: dict[str, dict] = {}
    for index in range(0, len(uids), _PRICE_BATCH_SIZE):
        batch = uids[index : index + _PRICE_BATCH_SIZE]
        prices.update(await get_last_prices(batch))

    return [
        _build_item(item, prices.get(item.get("uid", "")), now)
        for item in active
    ]


async def _ensure_cache(refresh: bool = False) -> tuple[list[DfaScreenerItem], str]:
    global _cache

    if refresh:
        _cache = None

    if _cache is not None:
        cached_at, items = _cache
        if time.time() - cached_at < CACHE_TTL_SECONDS:
            return items, datetime.fromtimestamp(
                cached_at, tz=timezone.utc
            ).isoformat().replace("+00:00", "Z")

    async with _build_lock:
        if _cache is not None and not refresh:
            cached_at, items = _cache
            if time.time() - cached_at < CACHE_TTL_SECONDS:
                return items, datetime.fromtimestamp(
                    cached_at, tz=timezone.utc
                ).isoformat().replace("+00:00", "Z")

        items = await _build_cache()
        cached_at = time.time()
        _cache = (cached_at, items)
        return items, datetime.fromtimestamp(
            cached_at, tz=timezone.utc
        ).isoformat().replace("+00:00", "Z")


def _apply_filters(items: list[DfaScreenerItem], query: DfaScreenerQuery) -> list[DfaScreenerItem]:
    search = query.search.strip().lower()
    filtered: list[DfaScreenerItem] = []

    for item in items:
        if query.currency != "all" and item.currency != query.currency:
            continue
        if query.buy_only and not item.buy_available:
            continue
        if query.hide_qual and item.for_qual_investor:
            continue
        if query.min_yield is not None:
            if item.yield_to_maturity is None or item.yield_to_maturity < query.min_yield:
                continue
        if query.min_years is not None:
            if (
                item.years_to_maturity is None
                or item.years_to_maturity < query.min_years
            ):
                continue
        if query.max_years is not None and item.years_to_maturity is not None:
            if item.years_to_maturity > query.max_years:
                continue
        if search:
            haystack = (
                f"{item.ticker} {item.name} {item.display_name} "
                f"{item.issuer_name} {item.product_type or ''}"
            ).lower()
            if search not in haystack:
                continue
        filtered.append(item)

    return filtered


def _sort_items(items: list[DfaScreenerItem], query: DfaScreenerQuery) -> None:
    reverse = query.sort_dir != "asc"

    def pick(item: DfaScreenerItem):
        if query.sort_key == "ticker":
            return item.issuer_name or item.ticker
        if query.sort_key == "issuer_name":
            return item.issuer_name or item.ticker
        if query.sort_key == "price":
            return item.price or Decimal("-1")
        if query.sort_key == "price_percent":
            return item.price_percent or Decimal("-1")
        if query.sort_key == "yield_to_maturity":
            return item.yield_to_maturity or Decimal("-1")
        if query.sort_key == "years_to_maturity":
            return item.years_to_maturity or Decimal("9999")
        if query.sort_key == "maturity_date":
            return item.maturity_date or ""
        if query.sort_key == "annual_coupon":
            return item.annual_coupon or Decimal("-1")
        if query.sort_key == "coupon_per_year":
            return item.coupon_per_year
        return item.yield_to_maturity or Decimal("-1")

    items.sort(key=pick, reverse=reverse)


async def get_dfa_screener_page(query: DfaScreenerQuery) -> DfaScreenerPageResponse:
    items, cached_at = await _ensure_cache(query.refresh)
    filtered = _apply_filters(items, query)
    _sort_items(filtered, query)

    page = max(query.page, 1)
    page_size = min(max(query.page_size, 1), 100)
    start = (page - 1) * page_size
    page_items = filtered[start : start + page_size]

    return DfaScreenerPageResponse(
        items=page_items,
        total=len(items),
        filtered_total=len(filtered),
        page=page,
        page_size=page_size,
        cached_at=cached_at,
    )
