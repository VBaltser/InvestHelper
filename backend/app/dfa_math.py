from datetime import datetime
from decimal import Decimal
from typing import Optional

from app.bond_math import calc_yield_to_maturity


def _add_months(dt: datetime, months: int) -> datetime:
    month_index = dt.month - 1 + months
    year = dt.year + month_index // 12
    month = month_index % 12 + 1
    days_in_month = [
        31,
        29 if year % 4 == 0 and (year % 100 != 0 or year % 400 == 0) else 28,
        31,
        30,
        31,
        30,
        31,
        31,
        30,
        31,
        30,
        31,
    ][month - 1]
    day = min(dt.day, days_in_month)
    return dt.replace(year=year, month=month, day=day)


def build_dfa_coupon_schedule(
    *,
    now: datetime,
    maturity: datetime,
    next_coupon: datetime | None,
    coupon_value: Decimal,
    coupon_per_year: int,
) -> list[tuple[datetime, Decimal]]:
    if coupon_value <= 0 or maturity <= now:
        return []

    if coupon_per_year <= 0:
        pay_date = next_coupon or maturity
        if pay_date > now:
            return [(pay_date, coupon_value)]
        return []

    months_step = max(1, 12 // coupon_per_year)
    anchor = next_coupon or maturity
    dates: list[datetime] = []

    current = anchor
    while current <= maturity:
        if current > now:
            dates.append(current)
        current = _add_months(current, months_step)

    current = _add_months(anchor, -months_step)
    while current > now:
        dates.insert(0, current)
        current = _add_months(current, -months_step)

    return [(date, coupon_value) for date in dates]


def calc_dfa_yield_to_maturity(
    *,
    dirty_price: Decimal,
    nominal: Decimal,
    maturity: datetime | None,
    next_coupon: datetime | None,
    coupon_value: Decimal,
    coupon_per_year: int,
    now: datetime,
) -> Optional[Decimal]:
    if dirty_price <= 0 or nominal <= 0 or maturity is None or maturity <= now:
        return None

    schedule = build_dfa_coupon_schedule(
        now=now,
        maturity=maturity,
        next_coupon=next_coupon,
        coupon_value=coupon_value,
        coupon_per_year=coupon_per_year,
    )
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
