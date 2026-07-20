import asyncio
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.rating_reports import (
    _EXPERT_COMPANY_LINK_RE,
    _HEADERS,
    _MIN_COMPANY_MATCH,
    _MIN_RELEASE_MATCH,
    _score_name_match,
    _ssl_verify,
    _extract_title,
    _find_credit_release_links,
)
import httpx


async def debug(query: str) -> None:
    async with httpx.AsyncClient(timeout=30, verify=_ssl_verify(), follow_redirects=True) as client:
        r = await client.post("https://raexpert.ru/search/", data={"search": query}, headers=_HEADERS)
        seen = set()
        for path in _EXPERT_COMPANY_LINK_RE.findall(r.text):
            normalized = path.rstrip("/")
            if normalized.endswith("/mentions"):
                normalized = normalized[: -len("/mentions")]
            if normalized in seen:
                continue
            seen.add(normalized)
            url = f"https://raexpert.ru{normalized}/"
            page = await client.get(url, headers=_HEADERS)
            title = _extract_title(page.text) or ""
            title_score = _score_name_match(query, title)
            if title_score < _MIN_COMPANY_MATCH:
                continue
            releases = _find_credit_release_links(page.text)
            print(f"\n{normalized} score={title_score}")
            print(" title:", title[:80])
            for rel, rel_title in releases[:3]:
                rel_score = _score_name_match(query, rel_title)
                print(f"  release score={rel_score}: {rel_title[:90]}")


async def main() -> None:
    for query in ["ПИК СЗ", "ПИК"]:
        print("\n====", query)
        await debug(query)


asyncio.run(main())
