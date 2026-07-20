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


def dump(url: str, out: str) -> None:
    with httpx.Client(verify=_ssl_verify(), timeout=30, follow_redirects=True) as client:
        r = client.get(url, headers=HEADERS)
        Path(out).write_text(r.text, encoding="utf-8")
        print(url, r.status_code, len(r.text), "->", out)


if __name__ == "__main__":
    dump("https://www.acra-ratings.ru/press-releases/6884/", "acra_press.html")
    dump("https://www.acra-ratings.ru/ratings/issuers/20/", "acra_issuer.html")
    dump("https://raexpert.ru/ratings/issuers/?search=%D0%A1%D0%B1%D0%B5%D1%80%D0%B1%D0%B0%D0%BD%D0%BA", "expert_issuers_search.html")
    dump("https://raexpert.ru/search/?q=%D0%A1%D0%B1%D0%B5%D1%80%D0%B1%D0%B0%D0%BD%D0%BA", "expert_search.html")
