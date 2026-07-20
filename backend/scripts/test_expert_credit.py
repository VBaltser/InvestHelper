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


def search_expert(query: str) -> None:
    with httpx.Client(verify=_ssl_verify(), timeout=30, follow_redirects=True) as client:
        r = client.post("https://raexpert.ru/search/", data={"search": query}, headers=HEADERS)
        companies = re.findall(r'href="(/database/companies/[^"?]+)"', r.text)
        print("companies", companies[:10])
        releases = re.findall(r'href="(/releases/[^"]+)"', r.text)
        print("releases", releases[:10])
        for rel in releases[:3]:
            if "кредит" in rel.lower():
                continue
            rr = client.get("https://raexpert.ru" + rel, headers=HEADERS)
            title = re.search(r"<h1[^>]*>([^<]+)", rr.text)
            print("release", rel, title.group(1).strip() if title else None)


def bank_list(query: str) -> None:
    with httpx.Client(verify=_ssl_verify(), timeout=30, follow_redirects=True) as client:
        r = client.get(
            "https://raexpert.ru/ratings/bankcredit_all/",
            params={"search": query},
            headers=HEADERS,
        )
        print("bank list", r.status_code, len(r.text))
        rows = re.findall(r'href="(/database/companies/[^"]+)"[^>]*>([^<]+)', r.text)
        print("rows", rows[:5])
        releases = re.findall(r'href="(/releases/[^"]+)"', r.text)
        print("releases in list", releases[:10])


if __name__ == "__main__":
    search_expert("Газпром")
    bank_list("Газпром")
    search_expert("ПИК")
