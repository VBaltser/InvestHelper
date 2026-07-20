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


url = "https://raexpert.ru/releases/2026/jul09a"
with httpx.Client(verify=_ssl_verify(), timeout=30, follow_redirects=True) as client:
    r = client.get(url, headers=HEADERS)
    Path("expert_release_jul09a.html").write_text(r.text, encoding="utf-8")
    print("final url", r.url, len(r.text))
    for pat in [r'class="b-article__body"[\s\S]{0,3000}', r'<h1[^>]*>([^<]+)', r'Ключев[\s\S]{0,500}']:
        m = re.search(pat, r.text)
        if m:
            print("MATCH", pat[:30], m.group(0)[:400])
