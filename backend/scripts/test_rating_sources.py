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


def test_urls(query: str) -> None:
    urls = [
        ("acra issuers text", f"https://www.acra-ratings.ru/ratings/issuers/?text={query}"),
        ("acra search", f"https://www.acra-ratings.ru/search/?q={query}&count=10"),
        ("expert post search", "https://raexpert.ru/search/"),
        ("expert bank search", f"https://raexpert.ru/ratings/bankcredit_all/?search={query}"),
        ("expert credits search", f"https://raexpert.ru/ratings/credits_all/?search={query}"),
        ("smartlab bond", "https://smart-lab.ru/q/bonds/SBER23/"),
    ]
    with httpx.Client(verify=_ssl_verify(), timeout=30, follow_redirects=True) as client:
        for label, url in urls:
            if label == "expert post search":
                r = client.post(url, data={"search": query}, headers=HEADERS)
            else:
                r = client.get(url, headers=HEADERS)
            print("\n===", label, r.status_code, len(r.text))
            patterns = [
                r'href="(/ratings/issuers/\d+/)"',
                r'href="(/ratings/[^"]+/)"',
                r'href="(/release/[^"]+)"',
                r'href="(/database/[^"]+)"',
                r'Кредитный\s+рейтинг',
                r'press-releases',
            ]
            for p in patterns:
                found = re.findall(p, r.text)
                if found:
                    print(" ", p, "->", found[:5])


if __name__ == "__main__":
    test_urls("Сбербанк")
