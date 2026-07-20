from decimal import Decimal
from typing import List, Literal, Optional

from pydantic import BaseModel, Field


class BondMetadata(BaseModel):
    nominal_currency: str
    days_to_maturity: Optional[int] = None


class Account(BaseModel):
    id: str
    name: str
    type: str


class AllocationItem(BaseModel):
    key: str
    label: str
    amount: Decimal
    share_percent: Decimal = Field(default=Decimal(0))


class Position(BaseModel):
    figi: str = ""
    ticker: str
    name: str
    instrument_type: str
    instrument_type_label: str
    quantity: Decimal
    current_price: Decimal
    average_price: Decimal
    current_nkd: Decimal = Field(default=Decimal(0))
    current_value: Decimal
    share_percent: Decimal
    expected_yield: Decimal
    currency: str
    nominal_currency: str = "rub"
    days_to_maturity: Optional[int] = None
    credit_rating: Optional[str] = None
    yield_to_maturity: Optional[Decimal] = None


class PortfolioSummary(BaseModel):
    account_id: str
    total_amount: Decimal
    expected_yield: Decimal
    daily_yield: Optional[Decimal] = None
    daily_yield_relative: Optional[Decimal] = None
    currency: str
    allocation: List[AllocationItem]
    positions: List[Position]


class OperationItem(BaseModel):
    id: str
    date: str
    type: str
    type_label: str
    name: str
    description: str = ""
    state: str
    state_label: str
    figi: str = ""
    ticker: str = ""
    instrument_type: str = ""
    instrument_type_label: str = ""
    payment: Decimal
    payment_currency: str = "rub"
    price: Decimal = Field(default=Decimal(0))
    price_currency: str = "rub"
    commission: Decimal = Field(default=Decimal(0))
    commission_currency: str = "rub"
    quantity: Decimal = Field(default=Decimal(0))
    quantity_done: Decimal = Field(default=Decimal(0))


class OperationsSummary(BaseModel):
    total_count: int = 0
    buy_count: int = 0
    sell_count: int = 0
    deposits: Decimal = Field(default=Decimal(0))
    withdrawals: Decimal = Field(default=Decimal(0))
    dividends: Decimal = Field(default=Decimal(0))
    coupons: Decimal = Field(default=Decimal(0))
    commissions: Decimal = Field(default=Decimal(0))
    taxes: Decimal = Field(default=Decimal(0))
    currency: str = "rub"


class OperationsPageResponse(BaseModel):
    account_id: str
    period: str = "all"
    items: List[OperationItem]
    summary: OperationsSummary


class BondScreenerItem(BaseModel):
    figi: str
    ticker: str
    name: str
    isin: str
    currency: str
    sector: str
    exchange: str
    nominal: Decimal
    price_percent: Optional[Decimal] = None
    price: Optional[Decimal] = None
    nkd: Decimal
    maturity_date: Optional[str] = None
    years_to_maturity: Optional[Decimal] = None
    coupon_per_year: int
    next_coupon_date: Optional[str] = None
    annual_coupon: Optional[Decimal] = None
    current_yield: Optional[Decimal] = None
    floating_coupon: bool
    perpetual: bool
    amortization: bool
    buy_available: bool
    for_qual_investor: bool
    subordinated: bool
    is_ofz: bool
    credit_rating: Optional[str] = None
    yield_to_maturity: Optional[Decimal] = None
    risk_level: Optional[str] = None


class BondScreenerResponse(BaseModel):
    bonds: List[BondScreenerItem]
    cached_at: str
    total: int


class BondScreenerPageResponse(BaseModel):
    bonds: List[BondScreenerItem]
    total: int
    filtered_total: int
    page: int
    page_size: int
    cached_at: str
    sectors: List[str]


class DfaScreenerItem(BaseModel):
    uid: str
    ticker: str
    name: str
    display_name: str
    issuer_name: str
    product_type: Optional[str] = None
    currency: str
    nominal: Decimal
    price: Optional[Decimal] = None
    price_percent: Optional[Decimal] = None
    nkd: Decimal
    maturity_date: Optional[str] = None
    years_to_maturity: Optional[Decimal] = None
    coupon_per_year: int
    coupon_value: Optional[Decimal] = None
    next_coupon_date: Optional[str] = None
    annual_coupon: Optional[Decimal] = None
    yield_to_maturity: Optional[Decimal] = None
    yield_at_nominal: Optional[Decimal] = None
    buy_available: bool
    sell_available: bool
    for_qual_investor: bool


class DfaScreenerPageResponse(BaseModel):
    items: List[DfaScreenerItem]
    total: int
    filtered_total: int
    page: int
    page_size: int
    cached_at: str


class BondPortfolioMetricInput(BaseModel):
    figi: str
    ticker: str
    name: str
    average_price: Decimal
    current_price: Decimal
    current_nkd: Decimal = Field(default=Decimal(0))
    quantity: Decimal


class BondPortfolioMetric(BaseModel):
    figi: str
    current_yield_to_maturity: Optional[Decimal] = None
    yield_to_maturity: Optional[Decimal] = None
    credit_rating: Optional[str] = None
    maturity_income_rub: Optional[Decimal] = None


class BondPortfolioMetricsRequest(BaseModel):
    bonds: List[BondPortfolioMetricInput]


class BondPortfolioMetricsResponse(BaseModel):
    metrics: List[BondPortfolioMetric]


class ChatMessage(BaseModel):
    role: Literal["user", "assistant"]
    content: str = Field(min_length=1, max_length=8000)


class ChatRequest(BaseModel):
    account_id: str
    provider: Literal["gemini", "groq"] = "gemini"
    messages: List[ChatMessage] = Field(min_length=1, max_length=40)


class ChatResponse(BaseModel):
    reply: str
    provider: Literal["gemini", "groq"]


class BondChatRequest(BaseModel):
    bond: BondScreenerItem
    provider: Literal["gemini", "groq"] = "gemini"
    messages: List[ChatMessage] = Field(min_length=1, max_length=40)
