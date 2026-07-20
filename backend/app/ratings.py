import asyncio
import json
import re
import time
from pathlib import Path
from typing import Optional

import httpx

from app.config import settings

CACHE_PATH = Path(__file__).resolve().parent.parent / ".cache" / "bond_ratings.json"
CACHE_TTL_SECONDS = 86400
_FETCH_CONCURRENCY = 8

_cache: dict[str, tuple[float, str]] = {}
_lock = asyncio.Lock()

_RATING_RE = re.compile(
    r"Кредитный\s+рейтинг</div>[\s\S]{0,1200}?linear-progress-bar__text\">\s*([^<]+?)\s*</div>",
    re.IGNORECASE,
)
_RATING_PLAIN_RE = re.compile(
    r"Кредитный\s+рейтинг</div>[\s\S]{0,400}?quotes-simple-table__item\">\s*([^<]+?)\s*</div>",
    re.IGNORECASE,
)


def _ssl_verify():
    if settings.tinkoff_ssl_ca_file:
        return settings.tinkoff_ssl_ca_file
    return settings.tinkoff_ssl_verify


def _normalize_rating(value: str) -> Optional[str]:
    cleaned = value.strip()
    if not cleaned or cleaned in {"—", "-", "–", "нет", "Н/д", "н/д"}:
        return None
    return cleaned


def _parse_rating(html: str) -> Optional[str]:
    for pattern in (_RATING_RE, _RATING_PLAIN_RE):
        match = pattern.search(html)
        if match:
            rating = _normalize_rating(match.group(1))
            if rating:
                return rating
    return None


def _load_file_cache() -> None:
    global _cache
    if not CACHE_PATH.exists():
        return
    try:
        data = json.loads(CACHE_PATH.read_text(encoding="utf-8"))
        now = time.time()
        for secid, payload in data.items():
            if now - payload.get("ts", 0) < CACHE_TTL_SECONDS:
                _cache[secid] = (payload["ts"], payload["rating"])
    except (json.JSONDecodeError, KeyError, OSError):
        pass


def _save_file_cache() -> None:
    CACHE_PATH.parent.mkdir(parents=True, exist_ok=True)
    payload = {
        secid: {"ts": ts, "rating": rating}
        for secid, (ts, rating) in _cache.items()
    }
    CACHE_PATH.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )


async def _fetch_rating(secid: str, client: httpx.AsyncClient) -> Optional[str]:
    url = f"https://smart-lab.ru/q/bonds/{secid}/"
    try:
        response = await client.get(
            url,
            headers={"User-Agent": "InvestHelper/0.1"},
            follow_redirects=True,
        )
        if response.status_code != 200:
            return None
        return _parse_rating(response.text)
    except httpx.HTTPError:
        return None


async def get_credit_ratings(secids: list[str]) -> dict[str, Optional[str]]:
    if not secids:
        return {}

    async with _lock:
        if not _cache:
            _load_file_cache()

    now = time.time()
    result: dict[str, Optional[str]] = {}
    to_fetch: list[str] = []

    for secid in secids:
        cached = _cache.get(secid)
        if cached and now - cached[0] < CACHE_TTL_SECONDS:
            result[secid] = cached[1] or None
        else:
            to_fetch.append(secid)

    if to_fetch:
        proxy = settings.tinkoff_https_proxy
        batch_size = 80

        async with httpx.AsyncClient(
            timeout=20.0,
            verify=_ssl_verify(),
            proxy=proxy,
            trust_env=True,
        ) as client:
            for batch_start in range(0, len(to_fetch), batch_size):
                batch = to_fetch[batch_start : batch_start + batch_size]
                semaphore = asyncio.Semaphore(_FETCH_CONCURRENCY)

                async def fetch_one(secid: str) -> tuple[str, Optional[str]]:
                    async with semaphore:
                        rating = await _fetch_rating(secid, client)
                        await asyncio.sleep(0.2)
                        return secid, rating

                fetched = await asyncio.gather(*(fetch_one(secid) for secid in batch))

                async with _lock:
                    for secid, rating in fetched:
                        result[secid] = rating
                        if rating:
                            _cache[secid] = (now, rating)
                    _save_file_cache()

    return result
