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


def dump(url: str) -> None:
    with httpx.Client(verify=_ssl_verify(), timeout=30, follow_redirects=True) as client:
        r = client.get(url, headers=HEADERS)
        Path("expert_release.html").write_text(r.text, encoding="utf-8")
        wrapper = re.search(r'class="b-release__text[^"]*"[^>]*>([\s\S]*?)</div>\s*</div>', r.text)
        if not wrapper:
            wrapper = re.search(r'class="b-content__wrapper"[^>]*>([\s\S]{0,5000})', r.text)
        if wrapper:
            text = re.sub(r"<[^>]+>", " ", wrapper.group(1))
            text = re.sub(r"\s+", " ", text).strip()
            print(text[:800])
        else:
            print("no wrapper")
            for cls in ["b-release", "release", "content__wrapper", "article"]:
                if cls in r.text:
                    print("found class fragment", cls)


if __name__ == "__main__":
    dump("https://raexpert.ru/releases/2026/jul09a")
    dump("https://raexpert.ru/database/companies/pic/mentions/")
