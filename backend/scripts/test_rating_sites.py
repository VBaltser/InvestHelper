import httpx
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.config import settings

HEADERS = {"User-Agent": "InvestHelper/0.1"}


def _ssl_verify():
    if settings.tinkoff_ssl_ca_file:
        return settings.tinkoff_ssl_ca_file
    return settings.tinkoff_ssl_verify


def test_acra(query: str) -> None:
    with httpx.Client(verify=_ssl_verify(), timeout=30, follow_redirects=True) as client:
        r = client.get(
            "https://www.acra-ratings.ru/search/",
            params={"q": query, "count": 10},
            headers=HEADERS,
        )
        print("ACRA", query, r.status_code, len(r.text))
        pattern = r'href="(/ratings/issuers/\d+/)"[^>]*>([^<]+)'
        links = re.findall(pattern, r.text)
        print("  issuer links:", links[:5])
        if not links:
            return
        issuer_url = "https://www.acra-ratings.ru" + links[0][0]
        ir = client.get(issuer_url, headers=HEADERS)
        print("  issuer page", ir.status_code, len(ir.text))
        press = re.findall(r'href="(/press-releases/\d+/)"', ir.text)
        print("  press releases:", press[:5])
        if not press:
            return
        pr = client.get("https://www.acra-ratings.ru" + press[0], headers=HEADERS)
        print("  press page", pr.status_code, len(pr.text))
        title = re.search(r"<h1[^>]*>([^<]+)", pr.text)
        print("  title:", title.group(1).strip() if title else None)
        body = re.search(r'class="press-release__text[^"]*"[^>]*>([\s\S]{0,2000})', pr.text)
        print("  body preview:", (body.group(1)[:300] if body else None))


def test_expert(query: str) -> None:
    with httpx.Client(verify=_ssl_verify(), timeout=30, follow_redirects=True) as client:
        for url in [
            f"https://raexpert.ru/search/?query={query}",
            "https://raexpert.ru/ratings/issuers/",
        ]:
            try:
                r = client.get(url, headers=HEADERS)
                print("Expert", url, r.status_code, len(r.text))
                links = re.findall(r'href="([^"]*issuer[^"]*)"', r.text, re.I)
                print("  issuer-ish links:", links[:5])
            except Exception as exc:
                print("Expert error", url, exc)


if __name__ == "__main__":
    test_acra("Сбербанк")
    test_acra("Газпром")
    test_expert("Сбербанк")
