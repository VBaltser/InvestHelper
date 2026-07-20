import asyncio
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import httpx
from app.rating_reports import _EXPERT_COMPANY_LINK_RE, _HEADERS, _ssl_verify


async def main() -> None:
    for query in ["ПИК СЗ", "ПИК"]:
        async with httpx.AsyncClient(timeout=30, verify=_ssl_verify(), follow_redirects=True) as client:
            r = await client.post("https://raexpert.ru/search/", data={"search": query}, headers=_HEADERS)
            paths = _EXPERT_COMPANY_LINK_RE.findall(r.text)
            print(query, paths[:10])


asyncio.run(main())
