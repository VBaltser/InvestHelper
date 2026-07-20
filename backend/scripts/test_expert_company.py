import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import httpx
from app.config import settings

HEADERS = {"User-Agent": "InvestHelper/0.1"}


def _ssl_verify():
    if settings.tinkoff_ssl_ca_file:
        return settings.tinkoff_ssl_ca_file
    return settings.tinkoff_ssl_verify


def dump_expert_company(slug: str) -> None:
    url = f"https://raexpert.ru/database/companies/{slug}"
    with httpx.Client(verify=_ssl_verify(), timeout=30, follow_redirects=True) as client:
        r = client.get(url, headers=HEADERS)
        print(url, r.status_code, len(r.text))
        Path(f"expert_{slug}.html").write_text(r.text, encoding="utf-8")
        for p in [
            r'href="(/database/[^"]+)"',
            r'href="(/release/[^"]+)"',
            r'href="(/ratings/[^"]+)"',
            r'рейтинг[^<]{0,80}',
            r'Прогноз',
            r'Обоснование',
            r'Ключев',
        ]:
            found = re.findall(p, r.text, re.I)
            if found:
                print(p, "->", found[:8])


if __name__ == "__main__":
    dump_expert_company("sberbank_rossii")
