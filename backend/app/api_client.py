from decimal import Decimal
from typing import Any, Optional, Union

import httpx

from app.config import settings
from app.tinkoff_client import get_base_url

_client: Optional[httpx.AsyncClient] = None


class TinkoffApiError(Exception):
    pass


def _ssl_verify() -> Union[bool, str]:
    if settings.tinkoff_ssl_ca_file:
        return settings.tinkoff_ssl_ca_file
    return settings.tinkoff_ssl_verify


def _client_kwargs() -> dict:
    timeout = httpx.Timeout(
        settings.tinkoff_api_timeout,
        connect=min(settings.tinkoff_api_timeout, 15.0),
    )
    kwargs: dict = {
        "timeout": timeout,
        "verify": _ssl_verify(),
        "trust_env": True,
        "limits": httpx.Limits(max_connections=25, max_keepalive_connections=15),
    }
    if settings.tinkoff_https_proxy:
        kwargs["proxy"] = settings.tinkoff_https_proxy
    return kwargs


async def get_http_client() -> httpx.AsyncClient:
    global _client
    if _client is None or _client.is_closed:
        _client = httpx.AsyncClient(**_client_kwargs())
    return _client


async def close_http_client() -> None:
    global _client
    if _client is not None and not _client.is_closed:
        await _client.aclose()
    _client = None


def _parse_decimal(value: Any) -> Decimal:
    if value is None:
        return Decimal(0)
    if isinstance(value, (int, float, Decimal)):
        return Decimal(str(value))
    if isinstance(value, str):
        return Decimal(value)
    if isinstance(value, dict):
        units = value.get("units", 0)
        nano = value.get("nano", 0)
        return Decimal(str(units)) + Decimal(str(nano)) / Decimal(1_000_000_000)
    return Decimal(0)


def _connection_error_message(exc: Exception) -> str:
    details = str(exc).strip() or type(exc).__name__
    return (
        "Не удалось подключиться к T-Invest API (invest-public-api.tbank.ru). "
        "Скорее всего сеть блокирует порт 443 до API. "
        "Попробуйте VPN или мобильный интернет. "
        f"Диагностика: http://127.0.0.1:8000/api/diagnostics. "
        f"Технически: {details}"
    )


async def _call_api(service: str, method: str, payload: Optional[dict] = None) -> dict:
    url = f"{get_base_url()}/{service}/{method}"
    headers = {
        "Authorization": f"Bearer {settings.tinkoff_token}",
        "Content-Type": "application/json",
    }

    client = await get_http_client()
    try:
        response = await client.post(url, json=payload or {}, headers=headers)
    except httpx.TimeoutException as exc:
        raise TinkoffApiError(_connection_error_message(exc)) from exc
    except httpx.TransportError as exc:
        raise TinkoffApiError(_connection_error_message(exc)) from exc

    if response.status_code != 200:
        raise TinkoffApiError(
            f"API {method}: HTTP {response.status_code} — {response.text[:300]}"
        )

    data = response.json()
    if "code" in data and data.get("code", 0) != 0:
        raise TinkoffApiError(
            f"API {method}: {data.get('message', 'unknown error')}"
        )

    return data


async def get_accounts() -> list[dict]:
    data = await _call_api(
        "tinkoff.public.invest.api.contract.v1.UsersService",
        "GetAccounts",
    )
    return data.get("accounts", [])


async def get_portfolio(account_id: str, currency: str = "RUB") -> dict:
    return await _call_api(
        "tinkoff.public.invest.api.contract.v1.OperationsService",
        "GetPortfolio",
        {"accountId": account_id, "currency": currency},
    )


async def get_operations_by_cursor(
    account_id: str,
    *,
    cursor: str = "",
    limit: int = 100,
    date_from: Optional[str] = None,
    date_to: Optional[str] = None,
    state: Optional[str] = None,
) -> dict:
    payload: dict[str, Any] = {
        "accountId": account_id,
        "limit": limit,
        "cursor": cursor,
    }
    if date_from:
        payload["from"] = date_from
    if date_to:
        payload["to"] = date_to
    if state:
        payload["state"] = state
    return await _call_api(
        "tinkoff.public.invest.api.contract.v1.OperationsService",
        "GetOperationsByCursor",
        payload,
    )


async def get_instrument_by_figi(figi: str) -> Optional[dict]:
    if not figi:
        return None
    try:
        data = await _call_api(
            "tinkoff.public.invest.api.contract.v1.InstrumentsService",
            "GetInstrumentBy",
            {
                "idType": "INSTRUMENT_ID_TYPE_FIGI",
                "id": figi,
            },
        )
        return data.get("instrument")
    except TinkoffApiError:
        return None


def money_to_decimal(value: Optional[dict]) -> Decimal:
    return _parse_decimal(value)


def quotation_to_decimal(value: Optional[dict]) -> Decimal:
    return _parse_decimal(value)


async def get_bonds(instrument_status: str = "INSTRUMENT_STATUS_BASE") -> list[dict]:
    data = await _call_api(
        "tinkoff.public.invest.api.contract.v1.InstrumentsService",
        "Bonds",
        {"instrumentStatus": instrument_status},
    )
    return data.get("instruments", [])


async def get_dfas(instrument_status: str = "INSTRUMENT_STATUS_ALL") -> list[dict]:
    data = await _call_api(
        "tinkoff.public.invest.api.contract.v1.InstrumentsService",
        "Dfas",
        {"instrumentStatus": instrument_status},
    )
    return data.get("instruments", [])


async def get_last_prices(instrument_ids: list[str]) -> dict[str, dict]:
    if not instrument_ids:
        return {}
    data = await _call_api(
        "tinkoff.public.invest.api.contract.v1.MarketDataService",
        "GetLastPrices",
        {"instrumentId": instrument_ids},
    )
    result: dict[str, dict] = {}
    for item in data.get("lastPrices", []):
        for key in (
            item.get("figi"),
            item.get("instrumentUid"),
            item.get("instrumentId"),
        ):
            if key:
                result[key] = item
    return result


async def get_bond_coupons(figi: str, date_from: str, date_to: str) -> list[dict]:
    data = await _call_api(
        "tinkoff.public.invest.api.contract.v1.InstrumentsService",
        "GetBondCoupons",
        {"figi": figi, "from": date_from, "to": date_to},
    )
    return data.get("events", [])
