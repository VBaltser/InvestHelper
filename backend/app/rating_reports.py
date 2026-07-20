import asyncio
import html
import json
import re
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Optional

import httpx

from app.config import settings
from app.issuer_names import extract_issuer_search_query
from app.models import BondScreenerItem

CACHE_PATH = Path(__file__).resolve().parent.parent / ".cache" / "issuer_rating_reports.json"
CACHE_TTL_SECONDS = 86400
_MAX_COMPANY_CANDIDATES = 8
_MIN_COMPANY_MATCH = 60
_MIN_RELEASE_MATCH = 35
_MAX_REPORT_CHARS = 12000
_HEADERS = {"User-Agent": "InvestHelper/0.1"}

_cache: dict[str, tuple[float, dict[str, Any]]] = {}
_lock = asyncio.Lock()

_ACRA_ISSUER_LINK_RE = re.compile(
    r'href="(/ratings/issuers/\d+/)"[^>]*>([\s\S]{0,300}?)<',
    re.IGNORECASE,
)
_ACRA_PRESS_RELEASE_RE = re.compile(
    r'href="(/press-releases/\d+/)"[^>]*data-type="pressRelease"',
    re.IGNORECASE,
)
_ACRA_TEXT_CONTENT_RE = re.compile(
    r'class="text-content-wrapper"[^>]*>([\s\S]*?)</div>\s*</div>\s*</div>',
    re.IGNORECASE,
)
_EXPERT_COMPANY_LINK_RE = re.compile(
    r'href="(/database/companies/[^"?#]+/?)"',
    re.IGNORECASE,
)
_EXPERT_RELEASE_LINK_RE = re.compile(
    r'href="(/releases/[^"]+)"[^>]*>([\s\S]{0,400}?)</a>',
    re.IGNORECASE,
)
_EXPERT_ARTICLE_BODY_RE = re.compile(
    r'class="b-article__body"[^>]*>([\s\S]*?)</article>',
    re.IGNORECASE,
)


def _ssl_verify():
    if settings.tinkoff_ssl_ca_file:
        return settings.tinkoff_ssl_ca_file
    return settings.tinkoff_ssl_verify


@dataclass
class AgencyReport:
    agency: str
    title: str
    date: Optional[str]
    url: str
    text: str


@dataclass
class IssuerRatingReports:
    issuer_query: Optional[str]
    skipped_reason: Optional[str] = None
    acra: Optional[AgencyReport] = None
    expert_ra: Optional[AgencyReport] = None
    errors: list[str] = field(default_factory=list)

    def to_context(self) -> dict[str, Any]:
        payload: dict[str, Any] = {
            "issuer_query": self.issuer_query,
            "skipped_reason": self.skipped_reason,
            "errors": self.errors,
        }
        if self.acra:
            payload["acra"] = {
                "title": self.acra.title,
                "date": self.acra.date,
                "url": self.acra.url,
                "text": self.acra.text,
            }
        if self.expert_ra:
            payload["expert_ra"] = {
                "title": self.expert_ra.title,
                "date": self.expert_ra.date,
                "url": self.expert_ra.url,
                "text": self.expert_ra.text,
            }
        return payload


def _normalize_text(value: str) -> str:
    cleaned = html.unescape(value)
    cleaned = re.sub(r"\s+", " ", cleaned).strip().lower()
    cleaned = cleaned.replace("«", "").replace("»", "").replace('"', "")
    return cleaned


def _score_name_match(query: str, candidate: str) -> int:
    query_norm = _normalize_text(query)
    candidate_norm = _normalize_text(candidate)
    if not query_norm or not candidate_norm:
        return 0
    if query_norm == candidate_norm:
        return 200
    if query_norm in candidate_norm:
        extra = candidate_norm.replace(query_norm, " ").strip()
        extra_words = [word for word in re.split(r"[^\w]+", extra) if len(word) > 2]
        penalty = min(len(extra_words) * 15, 90)
        return max(160 - penalty, 60)
    if candidate_norm in query_norm:
        return 130

    query_words = {word for word in re.split(r"[^\w]+", query_norm) if len(word) > 2}
    candidate_words = {
        word for word in re.split(r"[^\w]+", candidate_norm) if len(word) > 2
    }
    if not query_words:
        return 0
    overlap = len(query_words & candidate_words)
    if overlap == 0:
        return 0
    extra_words = len(candidate_words - query_words)
    return max(overlap * 25 - extra_words * 10, 0)


def _html_to_text(raw_html: str, max_length: int = _MAX_REPORT_CHARS) -> str:
    cleaned = re.sub(r"<(script|style)[^>]*>[\s\S]*?</\1>", " ", raw_html, flags=re.I)
    cleaned = re.sub(r"<br\s*/?>", "\n", cleaned, flags=re.I)
    cleaned = re.sub(r"</(?:p|div|h\d|li|tr|td|th|ul|ol|table)>", "\n", cleaned, flags=re.I)
    cleaned = re.sub(r"<[^>]+>", " ", cleaned)
    cleaned = html.unescape(cleaned)
    cleaned = re.sub(r"[ \t\r\f\v]+", " ", cleaned)
    cleaned = re.sub(r"\n{3,}", "\n\n", cleaned)
    cleaned = cleaned.strip()
    if len(cleaned) > max_length:
        cleaned = cleaned[:max_length] + "\n\n… (текст обрезан)"
    return cleaned


def _is_credit_rating_release(title: str) -> bool:
    lowered = _normalize_text(title)
    if "кредит" not in lowered or "рейтинг" not in lowered:
        return False
    if "esg" in lowered and "кредит" not in lowered.replace("esg", ""):
        return False
    return True


def _extract_title(html_text: str) -> Optional[str]:
    h1_match = re.search(
        r'<h1[^>]*class="[^"]*b-title[^"]*"[^>]*>([\s\S]*?)</h1>',
        html_text,
        re.IGNORECASE,
    )
    if h1_match:
        chunk = re.sub(r"<a[\s\S]*$", "", h1_match.group(1), flags=re.IGNORECASE)
        title = _html_to_text(chunk, max_length=300)
        if title:
            return title.split("\n")[0].strip()

    for pattern in (
        r"<meta name=\"description\" content=\"([^\"]+)\"",
        r"<h1[^>]*>([\s\S]*?)</h1>",
    ):
        match = re.search(pattern, html_text, re.IGNORECASE)
        if match:
            title = _html_to_text(match.group(1), max_length=500)
            if title:
                return title.split("\n")[0].strip()
    return None


def _extract_publication_date(html_text: str) -> Optional[str]:
    for pattern in (
        r'<time class="publication_date"[^>]*datetime="([^"]+)"',
        r'<time class="publication_date"[^>]*>\s*Дата публикации:\s*([^<]+)',
        r'class="b-subheader__date"[^>]*>([^<]+)',
    ):
        match = re.search(pattern, html_text, re.IGNORECASE)
        if match:
            return _html_to_text(match.group(1), max_length=80)
    return None


def _find_credit_release_links(html_text: str) -> list[tuple[str, str]]:
    seen: set[str] = set()
    results: list[tuple[str, str]] = []
    for path, title_html in _EXPERT_RELEASE_LINK_RE.findall(html_text):
        title = _html_to_text(title_html, max_length=300)
        if not title or not _is_credit_rating_release(title):
            continue
        if path in seen:
            continue
        seen.add(path)
        results.append((path, title))
    return results


def _load_file_cache() -> None:
    global _cache
    if not CACHE_PATH.exists():
        return
    try:
        data = json.loads(CACHE_PATH.read_text(encoding="utf-8"))
        now = time.time()
        for key, payload in data.items():
            if now - payload.get("ts", 0) < CACHE_TTL_SECONDS:
                _cache[key] = (payload["ts"], payload["data"])
    except (json.JSONDecodeError, KeyError, OSError):
        pass


def _save_file_cache() -> None:
    CACHE_PATH.parent.mkdir(parents=True, exist_ok=True)
    payload = {
        key: {"ts": ts, "data": data}
        for key, (ts, data) in _cache.items()
    }
    CACHE_PATH.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )


async def _fetch_acra_report(
    client: httpx.AsyncClient,
    issuer_query: str,
) -> Optional[AgencyReport]:
    search_response = await client.get(
        "https://www.acra-ratings.ru/search/",
        params={"q": issuer_query, "count": 20},
        headers=_HEADERS,
    )
    search_response.raise_for_status()

    issuer_candidates: list[tuple[int, str, str]] = []
    for path, name_html in _ACRA_ISSUER_LINK_RE.findall(search_response.text):
        name = _html_to_text(name_html, max_length=200)
        score = _score_name_match(issuer_query, name)
        if score > 0:
            issuer_candidates.append((score, path, name))

    if not issuer_candidates:
        return None

    issuer_candidates.sort(key=lambda item: item[0], reverse=True)
    issuer_path = issuer_candidates[0][1]
    issuer_url = f"https://www.acra-ratings.ru{issuer_path}"
    issuer_response = await client.get(issuer_url, headers=_HEADERS)
    issuer_response.raise_for_status()

    press_links = _ACRA_PRESS_RELEASE_RE.findall(issuer_response.text)
    if not press_links:
        return None

    press_path = press_links[0]
    press_url = f"https://www.acra-ratings.ru{press_path}"
    press_response = await client.get(press_url, headers=_HEADERS)
    press_response.raise_for_status()

    content_match = _ACRA_TEXT_CONTENT_RE.search(press_response.text)
    if not content_match:
        return None

    title = _extract_title(press_response.text) or "Пресс-релиз АКРА"
    return AgencyReport(
        agency="ACRA",
        title=title,
        date=_extract_publication_date(press_response.text),
        url=press_url,
        text=_html_to_text(content_match.group(1)),
    )


async def _fetch_expert_ra_report(
    client: httpx.AsyncClient,
    issuer_query: str,
) -> Optional[AgencyReport]:
    search_response = await client.post(
        "https://raexpert.ru/search/",
        data={"search": issuer_query},
        headers=_HEADERS,
    )
    search_response.raise_for_status()

    company_paths: list[str] = []
    seen_paths: set[str] = set()
    for path in _EXPERT_COMPANY_LINK_RE.findall(search_response.text):
        normalized = path.rstrip("/")
        if normalized.endswith("/mentions"):
            normalized = normalized[: -len("/mentions")]
        if normalized in seen_paths:
            continue
        seen_paths.add(normalized)
        company_paths.append(normalized)

    if not company_paths:
        return None

    scored_companies: list[tuple[int, str, str]] = []
    for company_path in company_paths[: _MAX_COMPANY_CANDIDATES * 2]:
        company_url = f"https://raexpert.ru{company_path}/"
        company_response = await client.get(company_url, headers=_HEADERS)
        if company_response.status_code != 200:
            continue

        page_title = _extract_title(company_response.text) or ""
        title_score = _score_name_match(issuer_query, page_title)
        slug = company_path.rsplit("/", 1)[-1]
        slug_score = _score_name_match(issuer_query, slug.replace("_", " "))
        if slug.lower() == "pic" and _normalize_text(issuer_query).startswith("пик"):
            slug_score = max(slug_score, 120)
        score = max(title_score, slug_score)
        if score >= _MIN_COMPANY_MATCH or (not slug.isdigit() and slug_score > 0):
            scored_companies.append((score, company_path, company_response.text))

    scored_companies.sort(key=lambda item: item[0], reverse=True)
    if not scored_companies or scored_companies[0][0] < _MIN_COMPANY_MATCH:
        return None

    candidate_companies = [scored_companies[0]]

    for title_score, company_path, company_html in candidate_companies:

        mentions_html = ""
        mentions_response = await client.get(
            f"https://raexpert.ru{company_path}/mentions/",
            headers=_HEADERS,
        )
        if mentions_response.status_code == 200:
            mentions_html = mentions_response.text

        for page_html in (company_html, mentions_html):
            if not page_html:
                continue

            for release_path, release_title in _find_credit_release_links(page_html):
                if _score_name_match(issuer_query, release_title) < _MIN_RELEASE_MATCH:
                    continue

                release_url = f"https://raexpert.ru{release_path}"
                release_response = await client.get(release_url, headers=_HEADERS)
                if release_response.status_code != 200:
                    continue

                body_match = _EXPERT_ARTICLE_BODY_RE.search(release_response.text)
                if not body_match:
                    continue

                report_title = _extract_title(release_response.text) or release_title
                if _score_name_match(issuer_query, report_title) < _MIN_RELEASE_MATCH:
                    continue

                return AgencyReport(
                    agency="Expert RA",
                    title=report_title,
                    date=_extract_publication_date(release_response.text),
                    url=release_url,
                    text=_html_to_text(body_match.group(1)),
                )

    return None


async def get_issuer_rating_reports(bond: BondScreenerItem) -> IssuerRatingReports:
    issuer_query = extract_issuer_search_query(
        ticker=bond.ticker,
        name=bond.name,
        sector=bond.sector,
        is_ofz=bond.is_ofz,
    )
    if not issuer_query:
        return IssuerRatingReports(
            issuer_query=None,
            skipped_reason="Государственный или муниципальный эмитент — отчёты АКРА/Эксперт РА не применяются.",
        )

    cache_key = _normalize_text(issuer_query)
    async with _lock:
        if not _cache:
            _load_file_cache()
        cached = _cache.get(cache_key)
        if cached and time.time() - cached[0] < CACHE_TTL_SECONDS:
            data = cached[1]
            return IssuerRatingReports(
                issuer_query=issuer_query,
                skipped_reason=data.get("skipped_reason"),
                acra=_report_from_cache(data.get("acra")),
                expert_ra=_report_from_cache(data.get("expert_ra")),
                errors=list(data.get("errors") or []),
            )

    result = IssuerRatingReports(issuer_query=issuer_query)
    proxy = settings.tinkoff_https_proxy

    async with httpx.AsyncClient(
        timeout=30.0,
        verify=_ssl_verify(),
        proxy=proxy,
        trust_env=True,
        follow_redirects=True,
    ) as client:
        acra_task = asyncio.create_task(_safe_fetch(_fetch_acra_report, client, issuer_query, result, "ACRA"))
        expert_task = asyncio.create_task(
            _safe_fetch(_fetch_expert_ra_report, client, issuer_query, result, "Expert RA")
        )
        result.acra, result.expert_ra = await asyncio.gather(acra_task, expert_task)

    cache_payload = result.to_context()
    async with _lock:
        _cache[cache_key] = (time.time(), cache_payload)
        _save_file_cache()

    return result


def _report_from_cache(data: Optional[dict[str, Any]]) -> Optional[AgencyReport]:
    if not data:
        return None
    return AgencyReport(
        agency="ACRA" if "acra-ratings.ru" in data.get("url", "") else "Expert RA",
        title=data.get("title") or "",
        date=data.get("date"),
        url=data.get("url") or "",
        text=data.get("text") or "",
    )


async def _safe_fetch(
    fetcher,
    client: httpx.AsyncClient,
    issuer_query: str,
    result: IssuerRatingReports,
    agency_label: str,
) -> Optional[AgencyReport]:
    try:
        return await fetcher(client, issuer_query)
    except httpx.HTTPError as exc:
        result.errors.append(f"{agency_label}: ошибка загрузки ({exc.__class__.__name__})")
        return None
    except Exception as exc:
        result.errors.append(f"{agency_label}: {exc}")
        return None
