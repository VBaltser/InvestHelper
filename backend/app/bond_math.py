from datetime import datetime
from decimal import Decimal
from typing import Optional


def xirr(
    cashflows: list[tuple[datetime, float]],
    tolerance: float = 1e-7,
    max_iterations: int = 100,
) -> Optional[float]:
    if len(cashflows) < 2:
        return None

    d0 = cashflows[0][0]

    def npv(rate: float) -> float:
        if rate <= -0.999:
            return float("inf")
        total = 0.0
        for date, amount in cashflows:
            years = (date - d0).days / 365.25
            total += amount / ((1 + rate) ** years)
        return total

    low, high = -0.5, 0.5
    f_low, f_high = npv(low), npv(high)

    if f_low * f_high > 0:
        high = 2.0
        f_high = npv(high)
        if f_low * f_high > 0:
            return None

    for _ in range(max_iterations):
        mid = (low + high) / 2
        f_mid = npv(mid)
        if abs(f_mid) < tolerance:
            return mid
        if f_low * f_mid < 0:
            high = mid
            f_high = f_mid
        else:
            low = mid
            f_low = f_mid

    return (low + high) / 2


def calc_yield_to_maturity(
    dirty_price: Decimal,
    nominal: Decimal,
    maturity: datetime,
    coupon_events: list[tuple[datetime, Decimal]],
    now: datetime,
) -> Optional[Decimal]:
    if dirty_price <= 0 or nominal <= 0 or maturity <= now:
        return None

    cashflows: list[tuple[datetime, float]] = [
        (now, -float(dirty_price)),
    ]

    for coupon_date, coupon_value in coupon_events:
        if coupon_date <= now or coupon_value <= 0:
            continue
        cashflows.append((coupon_date, float(coupon_value)))

    cashflows.append((maturity, float(nominal)))

    rate = xirr(cashflows)
    if rate is None:
        return None

    return (Decimal(str(rate)) * Decimal(100)).quantize(Decimal("0.01"))
