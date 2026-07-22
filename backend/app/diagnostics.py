import asyncio
import socket
from datetime import datetime, timezone
from urllib.parse import urlparse

import httpx

from app.config import settings
from app.tinkoff_client import get_base_url

API_HOST = "invest-public-api.tbank.ru"
API_PORT = 443


def _check_tcp(host: str, port: int, timeout: float = 5.0) -> dict:
    try:
        with socket.create_connection((host, port), timeout=timeout):
            return {"ok": True, "message": f"TCP {host}:{port} доступен"}
    except OSError as exc:
        return {"ok": False, "message": f"TCP {host}:{port} недоступен: {exc}"}


async def _check_api_request() -> dict:
    url = (
        get_base_url()
        + "/tinkoff.public.invest.api.contract.v1.UsersService/GetAccounts"
    )
    verify = (
        settings.tinkoff_ssl_ca_file
        if settings.tinkoff_ssl_ca_file
        else settings.tinkoff_ssl_verify
    )
    proxy = settings.tinkoff_https_proxy
    timeout = httpx.Timeout(settings.tinkoff_api_timeout, connect=10.0)

    try:
        async with httpx.AsyncClient(
            timeout=timeout,
            verify=verify,
            proxy=proxy,
            trust_env=True,
        ) as client:
            response = await client.post(
                url,
                json={},
                headers={
                    "Authorization": f"Bearer {settings.tinkoff_token}",
                    "Content-Type": "application/json",
                },
            )
        if response.status_code == 200:
            return {"ok": True, "message": "API отвечает (HTTP 200)"}
        if response.status_code == 401:
            return {
                "ok": True,
                "message": "Сеть работает, API доступен (токен отклонён — проверьте TINKOFF_TOKEN)",
            }
        return {
            "ok": False,
            "message": f"API вернул HTTP {response.status_code}",
        }
    except httpx.TimeoutException as exc:
        return {"ok": False, "message": f"Таймаут API: {exc or type(exc).__name__}"}
    except httpx.TransportError as exc:
        return {"ok": False, "message": f"Ошибка транспорта: {exc or type(exc).__name__}"}


async def run_network_diagnostics() -> dict:
    host = urlparse(get_base_url()).hostname or API_HOST
    tcp = await asyncio.to_thread(_check_tcp, host, API_PORT)
    api = await _check_api_request()

    suggestions: list[str] = []
    if not tcp["ok"]:
        suggestions.extend(
            [
                "Сеть блокирует доступ к invest-public-api.tbank.ru:443.",
                "Попробуйте мобильный интернет (раздача с телефона) или VPN.",
                "Проверьте антивирус, файрвол и настройки роутера.",
            ]
        )
    if settings.tinkoff_https_proxy:
        suggestions.append(f"Используется прокси: {settings.tinkoff_https_proxy}")
    else:
        suggestions.append(
            "Если нужен прокси, укажите TINKOFF_HTTPS_PROXY в backend/.env"
        )

    return {
        "checked_at": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
        "api_host": host,
        "tcp": tcp,
        "api": api,
        "ssl_verify": settings.tinkoff_ssl_verify,
        "proxy": settings.tinkoff_https_proxy,
        "suggestions": suggestions,
        "healthy": tcp["ok"] and api["ok"],
    }
