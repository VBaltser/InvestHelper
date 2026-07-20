import json
import re
from dataclasses import dataclass
from typing import Any, Literal

import httpx

from app.bond_portfolio import get_portfolio_bond_metrics
from app.config import settings
from app.models import BondPortfolioMetricInput, BondScreenerItem, ChatMessage, Position
from app.rating_reports import get_issuer_rating_reports
from app.services import get_portfolio

Provider = Literal["gemini", "groq"]

SYSTEM_PROMPT = """Ты финансовый аналитик портфеля InvestHelper. Отвечай на русском языке.
Опирайся только на данные портфеля в JSON ниже. Если данных недостаточно — скажи об этом.
Не выдавай персональные инвестиционные рекомендации как обязательные к исполнению.
Для чисел используй значения из JSON; не пересчитывай метрики самостоятельно без необходимости.
Отвечай структурированно, но всегда завершай мысль. Если ответ длинный — используй списки и краткие формулировки.

Данные портфеля (актуальны на момент запроса):
"""

BOND_SYSTEM_PROMPT = """Ты аналитик облигаций InvestHelper. Отвечай на русском языке.
Задача — сделать summary по отчётам рейтинговых агентств АКРА и Эксперт РА для эмитента облигации.

Опирайся на блок rating_agency_reports в JSON ниже. Там могут быть тексты пресс-релизов/отчётов с сайтов acra-ratings.ru и raexpert.ru.
Если отчёт агентства отсутствует — явно напиши «отчёт не найден» для этого агентства и не выдумывай его содержание.
Параметры самой облигации (цена, YTM, срок) используй из bond только для краткого контекста в начале.

Структура ответа:
1. **Краткое резюме** (1–3 предложения по эмитенту)
2. **АКРА** — текущий рейтинг/прогноз, ключевые факторы, риски, ссылка на источник (url из JSON)
3. **Эксперт РА** — то же самое
4. **Сравнение и вывод** — где мнения совпадают/расходятся; что важно для держателя этой облигации

Не выдумывай цифры и формулировки, которых нет в текстах отчётов.
Не выдавай персональные инвестиционные рекомендации как обязательные к исполнению.

Данные (актуальны на момент запроса):
"""


class ChatApiError(Exception):
    pass


@dataclass
class ChatResult:
    reply: str
    provider: Provider


def _gemini_model_candidates() -> list[str]:
    candidates = [
        settings.gemini_model,
        "gemini-2.5-flash",
        "gemini-2.5-flash-lite",
    ]
    unique: list[str] = []
    for model in candidates:
        if model and model not in unique:
            unique.append(model)
    return unique


def _is_quota_error(message: str) -> bool:
    lowered = message.lower()
    return (
        "quota" in lowered
        or "rate limit" in lowered
        or "resource exhausted" in lowered
        or "429" in lowered
    )


async def build_portfolio_context(account_id: str) -> str:
    portfolio = await get_portfolio(account_id)

    bond_metrics: dict[str, dict[str, Any]] = {}
    bonds = [p for p in portfolio.positions if p.instrument_type == "bond" and p.figi]
    if bonds:
        metrics = await get_portfolio_bond_metrics(
            [
                BondPortfolioMetricInput(
                    figi=bond.figi,
                    ticker=bond.ticker,
                    name=bond.name,
                    average_price=bond.average_price,
                    current_price=bond.current_price,
                    current_nkd=bond.current_nkd,
                    quantity=bond.quantity,
                )
                for bond in bonds
            ]
        )
        for metric in metrics:
            bond_metrics[metric.figi] = {
                "current_yield_to_maturity": metric.current_yield_to_maturity,
                "yield_to_maturity": metric.yield_to_maturity,
                "credit_rating": metric.credit_rating,
                "maturity_income_rub": metric.maturity_income_rub,
            }

    payload = {
        "summary": {
            "account_id": portfolio.account_id,
            "total_amount": str(portfolio.total_amount),
            "expected_yield": str(portfolio.expected_yield),
            "daily_yield": str(portfolio.daily_yield)
            if portfolio.daily_yield is not None
            else None,
            "daily_yield_relative": str(portfolio.daily_yield_relative)
            if portfolio.daily_yield_relative is not None
            else None,
            "currency": portfolio.currency,
            "allocation": [
                item.model_dump(mode="json") for item in portfolio.allocation
            ],
        },
        "positions": [_position_payload(position, bond_metrics) for position in portfolio.positions],
    }
    return json.dumps(payload, ensure_ascii=False, indent=2)


def _position_payload(
    position: Position,
    bond_metrics: dict[str, dict[str, Any]],
) -> dict[str, Any]:
    item: dict[str, Any] = {
        "ticker": position.ticker,
        "name": position.name,
        "instrument_type": position.instrument_type,
        "instrument_type_label": position.instrument_type_label,
        "quantity": str(position.quantity),
        "current_price": str(position.current_price),
        "average_price": str(position.average_price),
        "current_value": str(position.current_value),
        "share_percent": str(position.share_percent),
        "expected_yield": str(position.expected_yield),
        "currency": position.currency,
        "nominal_currency": position.nominal_currency,
    }
    if position.instrument_type == "bond":
        metrics = bond_metrics.get(position.figi, {})
        item.update(
            {
                "days_to_maturity": position.days_to_maturity,
                "current_yield_to_maturity": _optional_decimal(
                    metrics.get("current_yield_to_maturity")
                ),
                "yield_to_maturity": _optional_decimal(metrics.get("yield_to_maturity")),
                "credit_rating": metrics.get("credit_rating"),
                "maturity_income_rub": _optional_decimal(
                    metrics.get("maturity_income_rub")
                ),
            }
        )
    return item


def _optional_decimal(value: Any) -> str | None:
    if value is None:
        return None
    return str(value)


def _require_api_key(provider: Provider) -> str:
    if provider == "gemini":
        if not settings.gemini_api_key:
            raise ChatApiError(
                "Не задан GEMINI_API_KEY. Добавьте ключ в backend/.env "
                "(получить: https://aistudio.google.com/apikey)"
            )
        return settings.gemini_api_key

    if not settings.groq_api_key:
        raise ChatApiError(
            "Не задан GROQ_API_KEY. Добавьте ключ в backend/.env "
            "(получить: https://console.groq.com/keys)"
        )
    return settings.groq_api_key


async def build_bond_context(bond: BondScreenerItem) -> str:
    reports = await get_issuer_rating_reports(bond)
    payload = {
        "bond": bond.model_dump(mode="json"),
        "rating_agency_reports": reports.to_context(),
    }
    return json.dumps(payload, ensure_ascii=False, indent=2)


async def _chat_with_provider(
    provider: Provider,
    system_text: str,
    messages: list[ChatMessage],
) -> ChatResult:
    if provider == "gemini":
        try:
            reply = await _chat_gemini(system_text, messages)
            return ChatResult(reply=reply, provider="gemini")
        except ChatApiError as exc:
            if settings.groq_api_key and _is_quota_error(str(exc)):
                reply = await _chat_groq(settings.groq_api_key, system_text, messages)
                return ChatResult(reply=reply, provider="groq")
            raise

    api_key = _require_api_key("groq")
    reply = await _chat_groq(api_key, system_text, messages)
    return ChatResult(reply=reply, provider="groq")


async def chat_with_portfolio(
    *,
    account_id: str,
    provider: Provider,
    messages: list[ChatMessage],
) -> ChatResult:
    if not messages or messages[-1].role != "user":
        raise ChatApiError("Последнее сообщение должно быть от пользователя")

    context = await build_portfolio_context(account_id)
    system_text = f"{SYSTEM_PROMPT}{context}"
    return await _chat_with_provider(provider, system_text, messages)


async def chat_with_bond(
    *,
    bond: BondScreenerItem,
    provider: Provider,
    messages: list[ChatMessage],
) -> ChatResult:
    if not messages or messages[-1].role != "user":
        raise ChatApiError("Последнее сообщение должно быть от пользователя")

    context = await build_bond_context(bond)
    system_text = f"{BOND_SYSTEM_PROMPT}{context}"
    return await _chat_with_provider(provider, system_text, messages)


async def _chat_gemini(
    system_text: str,
    messages: list[ChatMessage],
) -> str:
    api_key = _require_api_key("gemini")
    last_error = "Gemini: неизвестная ошибка"

    for model in _gemini_model_candidates():
        try:
            return await _chat_gemini_with_continuation(
                api_key,
                model,
                system_text,
                messages,
            )
        except ChatApiError as exc:
            last_error = str(exc)
            if not _is_quota_error(last_error):
                raise
            continue

    raise ChatApiError(
        f"{last_error}\n\n"
        "Бесплатный тариф Gemini больше не поддерживает gemini-2.0-flash. "
        "Укажите в .env: GEMINI_MODEL=gemini-2.5-flash "
        "или переключите чат на Groq."
    )


async def _chat_gemini_with_continuation(
    api_key: str,
    model: str,
    system_text: str,
    messages: list[ChatMessage],
) -> str:
    conversation = list(messages)
    reply_parts: list[str] = []
    truncated = False

    for attempt in range(settings.chat_max_continuations + 1):
        data = await _request_gemini(api_key, model, system_text, conversation)
        chunk = _extract_gemini_text(data)
        reply_parts.append(chunk)

        if _gemini_was_truncated(data):
            truncated = True
            if attempt >= settings.chat_max_continuations:
                break
            conversation = [
                *conversation,
                ChatMessage(role="assistant", content=chunk),
                ChatMessage(
                    role="user",
                    content="Продолжи ответ с того места, где остановился. "
                    "Не повторяй уже написанное.",
                ),
            ]
            continue
        truncated = False
        break

    reply = "".join(reply_parts).strip()
    if not reply:
        raise ChatApiError("Gemini вернул пустой ответ")
    if truncated:
        reply += "\n\n… (ответ обрезан лимитом модели)"
    return reply


async def _request_gemini(
    api_key: str,
    model: str,
    system_text: str,
    messages: list[ChatMessage],
) -> dict[str, Any]:
    contents = []
    for message in messages:
        role = "user" if message.role == "user" else "model"
        contents.append({"role": role, "parts": [{"text": message.content}]})

    payload = {
        "systemInstruction": {"parts": [{"text": system_text}]},
        "contents": contents,
        "generationConfig": {
            "temperature": 0.4,
            "maxOutputTokens": settings.chat_max_output_tokens,
        },
    }

    url = (
        f"https://generativelanguage.googleapis.com/v1beta/models/"
        f"{model}:generateContent"
    )

    async with httpx.AsyncClient(timeout=120.0) as client:
        response = await client.post(
            url,
            params={"key": api_key},
            json=payload,
        )

    if response.status_code != 200:
        raise ChatApiError(_parse_provider_error("Gemini", response, model=model))

    return response.json()


def _extract_gemini_text(data: dict[str, Any]) -> str:
    candidates = data.get("candidates") or []
    if not candidates:
        raise ChatApiError("Gemini не вернул ответ")

    parts = candidates[0].get("content", {}).get("parts") or []
    text_parts = [part.get("text", "") for part in parts if part.get("text")]
    return "".join(text_parts)


def _gemini_was_truncated(data: dict[str, Any]) -> bool:
    candidates = data.get("candidates") or []
    if not candidates:
        return False
    reason = (candidates[0].get("finishReason") or "").upper()
    return reason == "MAX_TOKENS"


async def _chat_groq(
    api_key: str,
    system_text: str,
    messages: list[ChatMessage],
) -> str:
    conversation = list(messages)
    reply_parts: list[str] = []
    truncated = False

    for attempt in range(settings.chat_max_continuations + 1):
        data = await _request_groq(api_key, system_text, conversation)
        choice = (data.get("choices") or [{}])[0]
        chunk = ((choice.get("message") or {}).get("content") or "").strip()
        if not chunk and not reply_parts:
            raise ChatApiError("Groq вернул пустой ответ")
        if chunk:
            reply_parts.append(chunk)

        if _groq_was_truncated(choice):
            truncated = True
            if attempt >= settings.chat_max_continuations:
                break
            conversation = [
                *conversation,
                ChatMessage(role="assistant", content=chunk),
                ChatMessage(
                    role="user",
                    content="Продолжи ответ с того места, где остановился. "
                    "Не повторяй уже написанное.",
                ),
            ]
            continue
        truncated = False
        break

    reply = "".join(reply_parts).strip()
    if not reply:
        raise ChatApiError("Groq вернул пустой ответ")
    if truncated:
        reply += "\n\n… (ответ обрезан лимитом модели)"
    return reply


async def _request_groq(
    api_key: str,
    system_text: str,
    messages: list[ChatMessage],
) -> dict[str, Any]:
    api_messages = [{"role": "system", "content": system_text}]
    for message in messages:
        api_messages.append({"role": message.role, "content": message.content})

    payload = {
        "model": settings.groq_model,
        "messages": api_messages,
        "temperature": 0.4,
        "max_tokens": settings.chat_max_output_tokens,
    }

    async with httpx.AsyncClient(timeout=120.0) as client:
        response = await client.post(
            "https://api.groq.com/openai/v1/chat/completions",
            headers={
                "Authorization": f"Bearer {api_key}",
                "Content-Type": "application/json",
            },
            json=payload,
        )

    if response.status_code != 200:
        raise ChatApiError(_parse_provider_error("Groq", response))

    return response.json()


def _groq_was_truncated(choice: dict[str, Any]) -> bool:
    reason = (choice.get("finish_reason") or "").lower()
    return reason == "length"


def _parse_provider_error(
    provider: str,
    response: httpx.Response,
    *,
    model: str | None = None,
) -> str:
    try:
        payload = response.json()
    except ValueError:
        return f"{provider}: ошибка {response.status_code}"

    error = payload.get("error")
    message = None
    if isinstance(error, dict):
        message = error.get("message")
    if not message:
        detail = payload.get("detail")
        if isinstance(detail, str):
            message = detail

    if not message:
        return f"{provider}: ошибка {response.status_code}"

    if provider == "Gemini" and _is_quota_error(message):
        retry_hint = _extract_retry_seconds(message)
        model_hint = f" (модель {model})" if model else ""
        base = (
            f"Gemini{model_hint}: исчерпана квота бесплатного тарифа."
        )
        if retry_hint:
            base += f" Повторите через ~{retry_hint} сек."
        base += (
            " Проверьте лимиты: https://ai.dev/rate-limit. "
            "Рекомендуется GEMINI_MODEL=gemini-2.5-flash или переключение на Groq."
        )
        return base

    return f"{provider}: {message}"


def _extract_retry_seconds(message: str) -> int | None:
    match = re.search(r"retry in ([0-9]+(?:\.[0-9]+)?)s", message, re.IGNORECASE)
    if not match:
        return None
    return max(1, int(float(match.group(1))))
