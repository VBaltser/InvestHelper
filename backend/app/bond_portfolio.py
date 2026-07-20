import asyncio
from datetime import datetime, timedelta, timezone
from decimal import Decimal

from app.api_client import (
    get_bonds,
    get_last_prices,
    money_to_decimal,
    quotation_to_decimal,
)
from app.bond_math import calc_yield_to_maturity
from app.bond_screener import (
    _coupon_date_to,
    _coupon_schedule,
    _fetch_coupon_events,
    _is_ofz,
    _parse_timestamp,
)
from app.models import BondPortfolioMetric, BondPortfolioMetricInput
from app.ratings import get_credit_ratings

_COUPON_CONCURRENCY = 10


def _resolve_credit_rating(
    ticker: str,
    name: str,
    sector: str,
    ratings_map: dict[str, str | None],
) -> str | None:
    if sector in {"government", "municipal"} or _is_ofz(ticker, name):
        return "Гос."
    return ratings_map.get(ticker)


def _maturity_income_rub(
    *,
    quantity: Decimal,
    nominal: Decimal,
    market_dirty: Decimal,
    portfolio_clean_rub: Decimal,
    nkd: Decimal,
    coupon_events: list[dict],
    now: datetime,
    maturity: datetime | None,
    floating: bool,
    amortization: bool,
) -> Decimal | None:
    if (
        floating
        or amortization
        or maturity is None
        or market_dirty <= 0
        or quantity <= 0
        or nominal <= 0
        or portfolio_clean_rub <= 0
    ):
        return None

    schedule = _coupon_schedule(coupon_events, now)
    future_coupons = sum(value for date, value in schedule if date > now)
    per_bond_income = future_coupons + nominal - market_dirty
    clean_nominal = market_dirty - nkd
    if clean_nominal <= 0:
        return None

    rub_factor = portfolio_clean_rub / clean_nominal
    return (per_bond_income * rub_factor * quantity).quantize(Decimal("0.01"))


def _calc_yield_to_maturity(
    *,
    floating: bool,
    amortization: bool,
    dirty_price: Decimal,
    nominal: Decimal,
    maturity: datetime | None,
    coupon_events: list[dict],
    now: datetime,
) -> Decimal | None:
    if floating or amortization or maturity is None or dirty_price <= 0:
        return None

    schedule = _coupon_schedule(coupon_events, now)
    ytm = calc_yield_to_maturity(
        dirty_price=dirty_price,
        nominal=nominal,
        maturity=maturity,
        coupon_events=schedule,
        now=now,
    )
    if ytm is None or ytm < Decimal("-5") or ytm > Decimal("100"):
        return None
    return ytm


async def _load_bond_instruments(figis: list[str]) -> dict[str, dict]:
    wanted = set(figis)
    by_figi: dict[str, dict] = {}
    for bond in await get_bonds():
        figi = bond.get("figi")
        if figi in wanted:
            by_figi[figi] = bond
    return by_figi


def _resolve_entry_dirty_price(nominal: Decimal, average_price: Decimal) -> Decimal:
    if average_price <= 0:
        return Decimal(0)

    if average_price < Decimal("100") and nominal > average_price * Decimal(5):
        return nominal * average_price / Decimal(100)

    return average_price


def _resolve_market_dirty_price(
    *,
    nominal: Decimal,
    nkd: Decimal,
    price_info: dict | None,
    portfolio_price: Decimal,
) -> Decimal:
    if price_info and nominal > 0:
        price_percent = quotation_to_decimal(price_info.get("price"))
        if price_percent > 0:
            return (nominal * price_percent / Decimal(100)) + nkd

    if portfolio_price <= 0:
        return Decimal(0)

    if portfolio_price < Decimal("100") and nominal > portfolio_price * Decimal(5):
        return (nominal * portfolio_price / Decimal(100)) + nkd

    return portfolio_price + nkd


async def _compute_metrics(
    inputs: list[BondPortfolioMetricInput],
) -> list[BondPortfolioMetric]:
    if not inputs:
        return []

    now = datetime.now(timezone.utc)
    date_from = (now - timedelta(days=30)).isoformat().replace("+00:00", "Z")
    semaphore = asyncio.Semaphore(_COUPON_CONCURRENCY)

    figis = [item.figi for item in inputs]
    instruments = await _load_bond_instruments(figis)
    prices = await get_last_prices(figis)

    coupon_tasks = []
    for item in inputs:
        instrument = instruments.get(item.figi)
        maturity = (
            _parse_timestamp(instrument.get("maturityDate")) if instrument else None
        )
        coupon_tasks.append(
            _fetch_coupon_events(
                item.figi,
                date_from,
                _coupon_date_to(maturity, now),
                semaphore,
            )
        )
    coupon_results = await asyncio.gather(*coupon_tasks)

    rating_secids = []
    for item in inputs:
        instrument = instruments.get(item.figi)
        sector = (instrument or {}).get("sector") or ""
        if (
            sector not in {"government", "municipal"}
            and not _is_ofz(item.ticker, item.name)
            and item.ticker
            and item.ticker != "—"
        ):
            rating_secids.append(item.ticker)

    ratings_map = await get_credit_ratings(rating_secids)

    metrics: list[BondPortfolioMetric] = []
    for item, coupon_events in zip(inputs, coupon_results):
        instrument = instruments.get(item.figi)
        if not instrument:
            metrics.append(BondPortfolioMetric(figi=item.figi))
            continue

        sector = instrument.get("sector") or ""
        floating = bool(instrument.get("floatingCouponFlag"))
        amortization = bool(instrument.get("amortizationFlag"))
        nominal = money_to_decimal(instrument.get("nominal"))
        maturity = _parse_timestamp(instrument.get("maturityDate"))
        entry_dirty_price = _resolve_entry_dirty_price(nominal, item.average_price)
        market_dirty_price = _resolve_market_dirty_price(
            nominal=nominal,
            nkd=item.current_nkd,
            price_info=prices.get(item.figi),
            portfolio_price=item.current_price,
        )
        ytm_kwargs = dict(
            floating=floating,
            amortization=amortization,
            nominal=nominal,
            maturity=maturity,
            coupon_events=coupon_events,
            now=now,
        )

        metrics.append(
            BondPortfolioMetric(
                figi=item.figi,
                credit_rating=_resolve_credit_rating(
                    item.ticker,
                    item.name,
                    sector,
                    ratings_map,
                ),
                current_yield_to_maturity=_calc_yield_to_maturity(
                    dirty_price=market_dirty_price,
                    **ytm_kwargs,
                ),
                yield_to_maturity=_calc_yield_to_maturity(
                    dirty_price=entry_dirty_price,
                    **ytm_kwargs,
                ),
                maturity_income_rub=_maturity_income_rub(
                    quantity=item.quantity,
                    nominal=nominal,
                    market_dirty=market_dirty_price,
                    portfolio_clean_rub=item.current_price,
                    nkd=item.current_nkd,
                    coupon_events=coupon_events,
                    now=now,
                    maturity=maturity,
                    floating=floating,
                    amortization=amortization,
                ),
            )
        )

    return metrics


async def get_portfolio_bond_metrics(
    inputs: list[BondPortfolioMetricInput],
) -> list[BondPortfolioMetric]:
    return await _compute_metrics(inputs)
