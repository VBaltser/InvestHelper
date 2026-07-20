import asyncio
from datetime import datetime, timedelta, timezone
from decimal import Decimal

from app.api_client import (
    get_accounts as fetch_accounts,
    get_bonds,
    get_instrument_by_figi,
    get_operations_by_cursor as fetch_operations,
    get_portfolio as fetch_portfolio,
    money_to_decimal,
    quotation_to_decimal,
)
from app.models import (
    Account,
    AllocationItem,
    BondMetadata,
    OperationItem,
    OperationsPageResponse,
    OperationsSummary,
    PortfolioSummary,
    Position,
)
from app.labels import (
    ALLOCATION_LABELS,
    INSTRUMENT_TYPE_LABELS,
    OPERATION_STATE_LABELS,
    OPERATION_TYPE_LABELS,
)


def _account_name(account: dict) -> str:
    name = account.get("name")
    if name:
        return name
    account_id = account.get("id", "")
    return f"Счёт {account_id[:8]}…"


async def get_accounts() -> list[Account]:
    accounts = await fetch_accounts()
    return [
        Account(
            id=account["id"],
            name=_account_name(account),
            type=account.get("type", "unknown"),
        )
        for account in accounts
    ]


async def _load_instrument_name(figi: str, ticker: str) -> str:
    instrument = await get_instrument_by_figi(figi)
    if instrument and instrument.get("name"):
        return instrument["name"]
    return ticker


def _nominal_currency_from_bond(bond: dict) -> str:
    nominal = bond.get("nominal")
    if isinstance(nominal, dict) and nominal.get("currency"):
        return str(nominal["currency"]).lower()
    return str(bond.get("currency") or "rub").lower()


def _days_to_maturity(maturity_date: str | None) -> int | None:
    if not maturity_date:
        return None
    maturity = datetime.fromisoformat(maturity_date.replace("Z", "+00:00"))
    days = (maturity.date() - datetime.now(timezone.utc).date()).days
    if days < 0:
        return None
    return days


async def _load_bond_metadata(figis: set[str]) -> dict[str, BondMetadata]:
    if not figis:
        return {}

    metadata: dict[str, BondMetadata] = {}
    for bond in await get_bonds():
        figi = bond.get("figi")
        if figi in figis:
            metadata[figi] = BondMetadata(
                nominal_currency=_nominal_currency_from_bond(bond),
                days_to_maturity=_days_to_maturity(bond.get("maturityDate")),
            )
    return metadata


async def get_portfolio(account_id: str) -> PortfolioSummary:
    portfolio = await fetch_portfolio(account_id)

    total_amount = money_to_decimal(portfolio.get("totalAmountPortfolio"))
    currency = (
        portfolio.get("totalAmountPortfolio", {}).get("currency", "rub")
        if portfolio.get("totalAmountPortfolio")
        else "rub"
    )

    allocation_sources = [
        ("shares", portfolio.get("totalAmountShares")),
        ("bonds", portfolio.get("totalAmountBonds")),
        ("etf", portfolio.get("totalAmountEtf")),
        ("currencies", portfolio.get("totalAmountCurrencies")),
        ("futures", portfolio.get("totalAmountFutures")),
        ("options", portfolio.get("totalAmountOptions")),
        ("sp", portfolio.get("totalAmountSp")),
        ("dfa", portfolio.get("totalAmountDfa")),
    ]

    allocation: list[AllocationItem] = []
    for key, money_value in allocation_sources:
        amount = money_to_decimal(money_value)
        if amount <= 0:
            continue
        share_percent = (
            (amount / total_amount * 100).quantize(Decimal("0.01"))
            if total_amount > 0
            else Decimal(0)
        )
        allocation.append(
            AllocationItem(
                key=key,
                label=ALLOCATION_LABELS.get(key, key),
                amount=amount.quantize(Decimal("0.01")),
                share_percent=share_percent,
            )
        )

    allocation.sort(key=lambda item: item.amount, reverse=True)

    raw_positions: list[dict] = []
    for item in portfolio.get("positions", []):
        quantity = quotation_to_decimal(item.get("quantity"))
        current_price = money_to_decimal(item.get("currentPrice"))
        average_price = money_to_decimal(item.get("averagePositionPrice"))
        current_value = (quantity * current_price).quantize(Decimal("0.01"))
        share_percent = (
            (current_value / total_amount * 100).quantize(Decimal("0.01"))
            if total_amount > 0
            else Decimal(0)
        )

        instrument_type = item.get("instrumentType", "unknown")
        ticker = item.get("ticker") or "—"
        figi = item.get("figi", "")

        raw_positions.append(
            {
                "figi": figi,
                "ticker": ticker,
                "instrument_type": instrument_type,
                "instrument_type_label": INSTRUMENT_TYPE_LABELS.get(
                    instrument_type, instrument_type
                ),
                "quantity": quantity,
                "current_price": current_price,
                "average_price": average_price,
                "current_nkd": money_to_decimal(item.get("currentNkd")),
                "current_value": current_value,
                "share_percent": share_percent,
                "expected_yield": quotation_to_decimal(item.get("expectedYield")),
                "currency": item.get("currentPrice", {}).get("currency", currency),
            }
        )

    names = await asyncio.gather(
        *(
            _load_instrument_name(item["figi"], item["ticker"])
            for item in raw_positions
        )
    )

    bond_figis = {
        item["figi"]
        for item in raw_positions
        if item["instrument_type"] == "bond" and item["figi"]
    }
    bond_metadata = await _load_bond_metadata(bond_figis)

    positions: list[Position] = []
    for item, name in zip(raw_positions, names):
        position_currency = item["currency"]
        bond_meta = bond_metadata.get(item["figi"])
        nominal_currency = bond_meta.nominal_currency if bond_meta else position_currency
        days_to_maturity = bond_meta.days_to_maturity if bond_meta else None
        if item["instrument_type"] != "bond":
            nominal_currency = position_currency
            days_to_maturity = None

        positions.append(
            Position(
                figi=item["figi"],
                ticker=item["ticker"],
                name=name,
                instrument_type=item["instrument_type"],
                instrument_type_label=item["instrument_type_label"],
                quantity=item["quantity"],
                current_price=item["current_price"],
                average_price=item["average_price"],
                current_nkd=item["current_nkd"],
                current_value=item["current_value"],
                share_percent=item["share_percent"],
                expected_yield=item["expected_yield"],
                currency=position_currency,
                nominal_currency=nominal_currency,
                days_to_maturity=days_to_maturity,
            )
        )

    positions.sort(key=lambda pos: pos.current_value, reverse=True)

    daily_yield = portfolio.get("dailyYield")
    daily_yield_relative = portfolio.get("dailyYieldRelative")

    return PortfolioSummary(
        account_id=account_id,
        total_amount=total_amount.quantize(Decimal("0.01")),
        expected_yield=quotation_to_decimal(portfolio.get("expectedYield")),
        daily_yield=money_to_decimal(daily_yield) if daily_yield else None,
        daily_yield_relative=quotation_to_decimal(daily_yield_relative)
        if daily_yield_relative
        else None,
        currency=currency,
        allocation=allocation,
        positions=positions,
    )


def _money_currency(value: dict | None, fallback: str = "rub") -> str:
    if isinstance(value, dict) and value.get("currency"):
        return str(value["currency"]).lower()
    return fallback


def _operation_quantity(value) -> Decimal:
    if value is None:
        return Decimal(0)
    return Decimal(str(value))


def _map_operation(item: dict) -> OperationItem:
    payment = item.get("payment")
    price = item.get("price")
    commission = item.get("commission")
    operation_type = item.get("type") or "OPERATION_TYPE_UNSPECIFIED"
    state = item.get("state") or "OPERATION_STATE_UNSPECIFIED"
    instrument_type = item.get("instrumentType") or ""
    name = item.get("name") or item.get("description") or ""
    ticker = item.get("ticker") or ""

    return OperationItem(
        id=str(item.get("id") or item.get("cursor") or ""),
        date=str(item.get("date") or ""),
        type=operation_type,
        type_label=OPERATION_TYPE_LABELS.get(operation_type, operation_type),
        name=name,
        description=item.get("description") or "",
        state=state,
        state_label=OPERATION_STATE_LABELS.get(state, state),
        figi=item.get("figi") or "",
        ticker=ticker,
        instrument_type=instrument_type,
        instrument_type_label=INSTRUMENT_TYPE_LABELS.get(
            instrument_type, instrument_type
        ),
        payment=money_to_decimal(payment).quantize(Decimal("0.01")),
        payment_currency=_money_currency(payment),
        price=money_to_decimal(price).quantize(Decimal("0.01")),
        price_currency=_money_currency(price),
        commission=money_to_decimal(commission).quantize(Decimal("0.01")),
        commission_currency=_money_currency(commission),
        quantity=_operation_quantity(item.get("quantity")),
        quantity_done=_operation_quantity(
            item.get("quantityDone", item.get("quantity"))
        ),
    )


BUY_OPERATION_TYPES = {
    "OPERATION_TYPE_BUY",
    "OPERATION_TYPE_BUY_CARD",
    "OPERATION_TYPE_BUY_MARGIN",
    "OPERATION_TYPE_DELIVERY_BUY",
}

SELL_OPERATION_TYPES = {
    "OPERATION_TYPE_SELL",
    "OPERATION_TYPE_SELL_CARD",
    "OPERATION_TYPE_SELL_MARGIN",
    "OPERATION_TYPE_DELIVERY_SELL",
}

DEPOSIT_OPERATION_TYPES = {
    "OPERATION_TYPE_INPUT",
    "OPERATION_TYPE_INPUT_SWIFT",
    "OPERATION_TYPE_INPUT_ACQUIRING",
    "OPERATION_TYPE_INP_MULTI",
    "OPERATION_TYPE_INPUT_SECURITIES",
}

WITHDRAWAL_OPERATION_TYPES = {
    "OPERATION_TYPE_OUTPUT",
    "OPERATION_TYPE_OUTPUT_SWIFT",
    "OPERATION_TYPE_OUTPUT_ACQUIRING",
    "OPERATION_TYPE_OUT_MULTI",
    "OPERATION_TYPE_OUTPUT_SECURITIES",
    "OPERATION_TYPE_OUTPUT_PENALTY",
}

DIVIDEND_OPERATION_TYPES = {
    "OPERATION_TYPE_DIVIDEND",
    "OPERATION_TYPE_DIV_EXT",
    "OPERATION_TYPE_DIVIDEND_TRANSFER",
}

COUPON_OPERATION_TYPES = {
    "OPERATION_TYPE_COUPON",
}

TAX_OPERATION_TYPES = {
    "OPERATION_TYPE_TAX",
    "OPERATION_TYPE_BOND_TAX",
    "OPERATION_TYPE_DIVIDEND_TAX",
    "OPERATION_TYPE_BENEFIT_TAX",
    "OPERATION_TYPE_TAX_CORRECTION",
    "OPERATION_TYPE_TAX_PROGRESSIVE",
    "OPERATION_TYPE_BOND_TAX_PROGRESSIVE",
    "OPERATION_TYPE_DIVIDEND_TAX_PROGRESSIVE",
    "OPERATION_TYPE_BENEFIT_TAX_PROGRESSIVE",
    "OPERATION_TYPE_TAX_CORRECTION_PROGRESSIVE",
    "OPERATION_TYPE_TAX_REPO_PROGRESSIVE",
    "OPERATION_TYPE_TAX_REPO",
    "OPERATION_TYPE_TAX_REPO_HOLD",
    "OPERATION_TYPE_TAX_REPO_REFUND",
    "OPERATION_TYPE_TAX_REPO_HOLD_PROGRESSIVE",
    "OPERATION_TYPE_TAX_REPO_REFUND_PROGRESSIVE",
    "OPERATION_TYPE_TAX_CORRECTION_COUPON",
}

FEE_OPERATION_TYPES = {
    "OPERATION_TYPE_BROKER_FEE",
    "OPERATION_TYPE_SERVICE_FEE",
    "OPERATION_TYPE_MARGIN_FEE",
    "OPERATION_TYPE_SUCCESS_FEE",
    "OPERATION_TYPE_CASH_FEE",
    "OPERATION_TYPE_OUT_FEE",
    "OPERATION_TYPE_OUT_STAMP_DUTY",
    "OPERATION_TYPE_TRACK_MFEE",
    "OPERATION_TYPE_TRACK_PFEE",
    "OPERATION_TYPE_OVER_COM",
    "OPERATION_TYPE_ADVICE_FEE",
    "OPERATION_TYPE_OTHER_FEE",
}

PERIOD_DAYS = {
    "day": 1,
    "week": 7,
    "month": 30,
}


def _period_date_from(period: str) -> str | None:
    days = PERIOD_DAYS.get(period)
    if days is None:
        return None
    start = datetime.now(timezone.utc) - timedelta(days=days)
    return start.isoformat().replace("+00:00", "Z")


def _rub_amount(amount: Decimal, currency: str) -> Decimal:
    if currency.lower() != "rub":
        return Decimal(0)
    return amount


def _build_operations_summary(items: list[OperationItem]) -> OperationsSummary:
    summary = OperationsSummary(total_count=len(items), currency="rub")

    for item in items:
        payment = _rub_amount(item.payment, item.payment_currency)
        commission = abs(_rub_amount(item.commission, item.commission_currency))

        if item.type in BUY_OPERATION_TYPES:
            summary.buy_count += 1
        elif item.type in SELL_OPERATION_TYPES:
            summary.sell_count += 1

        if item.type in DEPOSIT_OPERATION_TYPES:
            summary.deposits += abs(payment)
        elif item.type in WITHDRAWAL_OPERATION_TYPES:
            summary.withdrawals += abs(payment)
        elif item.type in DIVIDEND_OPERATION_TYPES:
            summary.dividends += abs(payment)
        elif item.type in COUPON_OPERATION_TYPES:
            summary.coupons += abs(payment)
        elif item.type in TAX_OPERATION_TYPES:
            summary.taxes += abs(payment)
        elif item.type in FEE_OPERATION_TYPES:
            summary.commissions += abs(payment)

        summary.commissions += commission

    quant = Decimal("0.01")
    summary.deposits = summary.deposits.quantize(quant)
    summary.withdrawals = summary.withdrawals.quantize(quant)
    summary.dividends = summary.dividends.quantize(quant)
    summary.coupons = summary.coupons.quantize(quant)
    summary.commissions = summary.commissions.quantize(quant)
    summary.taxes = summary.taxes.quantize(quant)
    return summary


async def get_operations(
    account_id: str,
    *,
    period: str = "month",
    state: str | None = None,
) -> OperationsPageResponse:
    period_key = period if period in ("day", "week", "month", "all") else "month"
    date_from = _period_date_from(period_key)

    items: list[OperationItem] = []
    cursor = ""
    for _ in range(200):
        data = await fetch_operations(
            account_id,
            cursor=cursor,
            limit=1000,
            date_from=date_from,
            state=state,
        )
        batch = data.get("items") or []
        items.extend(_map_operation(item) for item in batch)
        if not data.get("hasNext"):
            break
        cursor = str(data.get("nextCursor") or "")
        if not cursor:
            break

    return OperationsPageResponse(
        account_id=account_id,
        period=period_key,
        items=items,
        summary=_build_operations_summary(items),
    )
