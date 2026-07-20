from contextlib import asynccontextmanager
from decimal import Decimal
from typing import Optional

from fastapi import FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware

from app.api_client import TinkoffApiError, close_http_client
from app.bond_portfolio import get_portfolio_bond_metrics
from app.bond_screener import ScreenerQuery, get_bond_screener_page
from app.chat import ChatApiError, chat_with_bond, chat_with_portfolio
from app.dfa_screener import DfaScreenerQuery, get_dfa_screener_page
from app.diagnostics import run_network_diagnostics
from app.models import (
    BondChatRequest,
    BondPortfolioMetricsRequest,
    BondPortfolioMetricsResponse,
    ChatRequest,
    ChatResponse,
    DfaScreenerPageResponse,
    OperationsPageResponse,
)
from app.services import get_accounts, get_operations, get_portfolio


@asynccontextmanager
async def lifespan(_: FastAPI):
    yield
    await close_http_client()


app = FastAPI(title="InvestHelper", version="0.1.0", lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173", "http://127.0.0.1:5173"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/api/health")
async def health():
    return {"status": "ok"}


@app.get("/api/diagnostics")
async def diagnostics():
    return await run_network_diagnostics()


@app.get("/api/accounts")
async def list_accounts():
    try:
        return await get_accounts()
    except TinkoffApiError as exc:
        raise HTTPException(status_code=502, detail=str(exc)) from exc
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc


@app.get("/api/portfolio/{account_id}")
async def portfolio(account_id: str):
    try:
        return await get_portfolio(account_id)
    except TinkoffApiError as exc:
        raise HTTPException(status_code=502, detail=str(exc)) from exc
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc


@app.get(
    "/api/portfolio/{account_id}/operations",
    response_model=OperationsPageResponse,
)
async def portfolio_operations(
    account_id: str,
    period: str = Query(default="month"),
    state: Optional[str] = Query(default=None),
):
    try:
        return await get_operations(
            account_id,
            period=period,
            state=state,
        )
    except TinkoffApiError as exc:
        raise HTTPException(status_code=502, detail=str(exc)) from exc
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc


@app.post("/api/portfolio/bond-metrics")
async def portfolio_bond_metrics(body: BondPortfolioMetricsRequest):
    try:
        metrics = await get_portfolio_bond_metrics(body.bonds)
        return BondPortfolioMetricsResponse(metrics=metrics)
    except TinkoffApiError as exc:
        raise HTTPException(status_code=502, detail=str(exc)) from exc
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc


@app.post("/api/chat", response_model=ChatResponse)
async def portfolio_chat(body: ChatRequest):
    try:
        result = await chat_with_portfolio(
            account_id=body.account_id,
            provider=body.provider,
            messages=body.messages,
        )
        return ChatResponse(reply=result.reply, provider=result.provider)
    except ChatApiError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except TinkoffApiError as exc:
        raise HTTPException(status_code=502, detail=str(exc)) from exc
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc


@app.post("/api/chat/bond", response_model=ChatResponse)
async def bond_chat(body: BondChatRequest):
    try:
        result = await chat_with_bond(
            bond=body.bond,
            provider=body.provider,
            messages=body.messages,
        )
        return ChatResponse(reply=result.reply, provider=result.provider)
    except ChatApiError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc


@app.get("/api/dfa/screener", response_model=DfaScreenerPageResponse)
async def dfa_screener(
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=100, ge=1, le=100),
    sort_key: str = Query(default="yield_to_maturity"),
    sort_dir: str = Query(default="desc"),
    search: str = Query(default=""),
    currency: str = Query(default="rub"),
    buy_only: bool = Query(default=False),
    hide_qual: bool = Query(default=True),
    min_yield: Optional[float] = Query(default=None),
    min_years: Optional[float] = Query(default=None),
    max_years: Optional[float] = Query(default=None),
    refresh: bool = Query(default=False),
):
    try:
        query = DfaScreenerQuery(
            page=page,
            page_size=page_size,
            sort_key=sort_key,
            sort_dir=sort_dir,
            search=search,
            currency=currency,
            buy_only=buy_only,
            hide_qual=hide_qual,
            min_yield=Decimal(str(min_yield)) if min_yield is not None else None,
            min_years=Decimal(str(min_years)) if min_years is not None else None,
            max_years=Decimal(str(max_years)) if max_years is not None else None,
            refresh=refresh,
        )
        return await get_dfa_screener_page(query)
    except TinkoffApiError as exc:
        raise HTTPException(status_code=502, detail=str(exc)) from exc
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc


@app.get("/api/bonds/screener")
async def bonds_screener(
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=100, ge=1, le=100),
    sort_key: str = Query(default="yield_to_maturity"),
    sort_dir: str = Query(default="desc"),
    search: str = Query(default=""),
    currency: str = Query(default="rub"),
    sector: str = Query(default="all"),
    ofz_only: bool = Query(default=False),
    hide_qual: bool = Query(default=True),
    hide_floating: bool = Query(default=False),
    min_yield: Optional[float] = Query(default=None),
    min_years: Optional[float] = Query(default=None),
    max_years: Optional[float] = Query(default=None),
    min_rating: str = Query(default="all"),
    refresh: bool = Query(default=False),
):
    try:
        query = ScreenerQuery(
            page=page,
            page_size=page_size,
            sort_key=sort_key,
            sort_dir=sort_dir,
            search=search,
            currency=currency,
            sector=sector,
            ofz_only=ofz_only,
            hide_qual=hide_qual,
            hide_floating=hide_floating,
            min_yield=Decimal(str(min_yield)) if min_yield is not None else None,
            min_years=Decimal(str(min_years)) if min_years is not None else None,
            max_years=Decimal(str(max_years)) if max_years is not None else None,
            min_rating=min_rating,
            refresh=refresh,
        )
        return await get_bond_screener_page(query)
    except TinkoffApiError as exc:
        raise HTTPException(status_code=502, detail=str(exc)) from exc
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc
