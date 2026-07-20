export interface Account {
  id: string;
  name: string;
  type: string;
}

export interface AllocationItem {
  key: string;
  label: string;
  amount: string;
  share_percent: string;
}

export interface Position {
  figi: string;
  ticker: string;
  name: string;
  instrument_type: string;
  instrument_type_label: string;
  quantity: string;
  current_price: string;
  average_price: string;
  current_nkd: string;
  current_value: string;
  share_percent: string;
  expected_yield: string;
  currency: string;
  nominal_currency: string;
  days_to_maturity: number | null;
  credit_rating: string | null;
  current_yield_to_maturity: string | null;
  yield_to_maturity: string | null;
  maturity_income_rub: string | null;
}

export interface PortfolioSummary {
  account_id: string;
  total_amount: string;
  expected_yield: string;
  daily_yield: string | null;
  daily_yield_relative: string | null;
  currency: string;
  allocation: AllocationItem[];
  positions: Position[];
}

export interface BondScreenerItem {
  figi: string;
  ticker: string;
  name: string;
  isin: string;
  currency: string;
  sector: string;
  exchange: string;
  nominal: string;
  price_percent: string | null;
  price: string | null;
  nkd: string;
  maturity_date: string | null;
  years_to_maturity: string | null;
  coupon_per_year: number;
  next_coupon_date: string | null;
  annual_coupon: string | null;
  current_yield: string | null;
  floating_coupon: boolean;
  perpetual: boolean;
  amortization: boolean;
  buy_available: boolean;
  for_qual_investor: boolean;
  subordinated: boolean;
  is_ofz: boolean;
  credit_rating: string | null;
  yield_to_maturity: string | null;
  risk_level: string | null;
}

export interface BondScreenerPageResponse {
  bonds: BondScreenerItem[];
  total: number;
  filtered_total: number;
  page: number;
  page_size: number;
  cached_at: string;
  sectors: string[];
}

export interface DfaScreenerItem {
  uid: string;
  ticker: string;
  name: string;
  display_name: string;
  issuer_name: string;
  product_type: string | null;
  currency: string;
  nominal: string;
  price: string | null;
  price_percent: string | null;
  nkd: string;
  maturity_date: string | null;
  years_to_maturity: string | null;
  coupon_per_year: number;
  coupon_value: string | null;
  next_coupon_date: string | null;
  annual_coupon: string | null;
  yield_to_maturity: string | null;
  yield_at_nominal: string | null;
  buy_available: boolean;
  sell_available: boolean;
  for_qual_investor: boolean;
}

export interface DfaScreenerPageResponse {
  items: DfaScreenerItem[];
  total: number;
  filtered_total: number;
  page: number;
  page_size: number;
  cached_at: string;
}

export interface BondPortfolioMetric {
  figi: string;
  current_yield_to_maturity: string | null;
  yield_to_maturity: string | null;
  credit_rating: string | null;
  maturity_income_rub: string | null;
}

export interface BondPortfolioMetricsRequest {
  bonds: Array<{
    figi: string;
    ticker: string;
    name: string;
    average_price: string;
    current_price: string;
    current_nkd: string;
    quantity: string;
  }>;
}

export interface BondPortfolioMetricsResponse {
  metrics: BondPortfolioMetric[];
}

export interface DiagnosticsResult {
  checked_at: string;
  api_host: string;
  tcp: { ok: boolean; message: string };
  api: { ok: boolean; message: string };
  ssl_verify: boolean;
  proxy: string | null;
  suggestions: string[];
  healthy: boolean;
}

const API_BASE = "/api";

async function fetchJson<T>(path: string, init?: RequestInit): Promise<T> {
  const response = await fetch(`${API_BASE}${path}`, init);
  if (!response.ok) {
    const payload = await response.json().catch(() => ({}));
    const detail = payload.detail ?? response.statusText;
    throw new Error(typeof detail === "string" ? detail : "Ошибка запроса");
  }
  return response.json();
}

export function getAccounts(): Promise<Account[]> {
  return fetchJson<Account[]>("/accounts");
}

export function getPortfolio(accountId: string): Promise<PortfolioSummary> {
  return fetchJson<PortfolioSummary>(`/portfolio/${accountId}`);
}

export interface OperationItem {
  id: string;
  date: string;
  type: string;
  type_label: string;
  name: string;
  description: string;
  state: string;
  state_label: string;
  figi: string;
  ticker: string;
  instrument_type: string;
  instrument_type_label: string;
  payment: string;
  payment_currency: string;
  price: string;
  price_currency: string;
  commission: string;
  commission_currency: string;
  quantity: string;
  quantity_done: string;
}

export interface OperationsSummary {
  total_count: number;
  buy_count: number;
  sell_count: number;
  deposits: string;
  withdrawals: string;
  dividends: string;
  coupons: string;
  commissions: string;
  taxes: string;
  currency: string;
}

export type OperationsPeriod = "day" | "week" | "month" | "all";

export interface OperationsPageResponse {
  account_id: string;
  period: OperationsPeriod;
  items: OperationItem[];
  summary: OperationsSummary;
}

export interface OperationsParams {
  period?: OperationsPeriod;
  state?: string;
}

export function getOperations(
  accountId: string,
  params: OperationsParams = {},
): Promise<OperationsPageResponse> {
  const query = new URLSearchParams();
  if (params.period) query.set("period", params.period);
  if (params.state) query.set("state", params.state);

  const suffix = query.toString() ? `?${query.toString()}` : "";
  return fetchJson<OperationsPageResponse>(
    `/portfolio/${accountId}/operations${suffix}`,
  );
}

export function getPortfolioBondMetrics(
  bonds: BondPortfolioMetricsRequest["bonds"],
): Promise<BondPortfolioMetricsResponse> {
  return fetchJson<BondPortfolioMetricsResponse>("/portfolio/bond-metrics", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ bonds }),
  });
}

export interface BondScreenerParams {
  page?: number;
  page_size?: number;
  sort_key?: string;
  sort_dir?: "asc" | "desc";
  search?: string;
  currency?: string;
  sector?: string;
  ofz_only?: boolean;
  hide_qual?: boolean;
  hide_floating?: boolean;
  min_yield?: string;
  min_years?: string;
  max_years?: string;
  min_rating?: string;
  refresh?: boolean;
}

export function getBondScreener(
  params: BondScreenerParams = {},
): Promise<BondScreenerPageResponse> {
  const query = new URLSearchParams();
  if (params.page) query.set("page", String(params.page));
  if (params.page_size) query.set("page_size", String(params.page_size));
  if (params.sort_key) query.set("sort_key", params.sort_key);
  if (params.sort_dir) query.set("sort_dir", params.sort_dir);
  if (params.search) query.set("search", params.search);
  if (params.currency) query.set("currency", params.currency);
  if (params.sector) query.set("sector", params.sector);
  if (params.ofz_only) query.set("ofz_only", "true");
  if (params.hide_qual === false) query.set("hide_qual", "false");
  if (params.hide_floating) query.set("hide_floating", "true");
  if (params.min_yield) query.set("min_yield", params.min_yield);
  if (params.min_years) query.set("min_years", params.min_years);
  if (params.max_years) query.set("max_years", params.max_years);
  if (params.min_rating && params.min_rating !== "all") {
    query.set("min_rating", params.min_rating);
  }
  if (params.refresh) query.set("refresh", "true");

  const suffix = query.toString() ? `?${query.toString()}` : "";
  return fetchJson<BondScreenerPageResponse>(`/bonds/screener${suffix}`);
}

export interface DfaScreenerParams {
  page?: number;
  page_size?: number;
  sort_key?: string;
  sort_dir?: "asc" | "desc";
  search?: string;
  currency?: string;
  buy_only?: boolean;
  hide_qual?: boolean;
  min_yield?: string;
  min_years?: string;
  max_years?: string;
  refresh?: boolean;
}

export function getDfaScreener(
  params: DfaScreenerParams = {},
): Promise<DfaScreenerPageResponse> {
  const query = new URLSearchParams();
  if (params.page) query.set("page", String(params.page));
  if (params.page_size) query.set("page_size", String(params.page_size));
  if (params.sort_key) query.set("sort_key", params.sort_key);
  if (params.sort_dir) query.set("sort_dir", params.sort_dir);
  if (params.search) query.set("search", params.search);
  if (params.currency) query.set("currency", params.currency);
  if (params.buy_only) query.set("buy_only", "true");
  if (params.hide_qual === false) query.set("hide_qual", "false");
  if (params.min_yield) query.set("min_yield", params.min_yield);
  if (params.min_years) query.set("min_years", params.min_years);
  if (params.max_years) query.set("max_years", params.max_years);
  if (params.refresh) query.set("refresh", "true");

  const suffix = query.toString() ? `?${query.toString()}` : "";
  return fetchJson<DfaScreenerPageResponse>(`/dfa/screener${suffix}`);
}

export function getDiagnostics(): Promise<DiagnosticsResult> {
  return fetchJson<DiagnosticsResult>("/diagnostics");
}

export type ChatProvider = "gemini" | "groq";

export interface ChatMessage {
  role: "user" | "assistant";
  content: string;
}

export interface ChatRequest {
  account_id: string;
  provider: ChatProvider;
  messages: ChatMessage[];
}

export interface ChatResponse {
  reply: string;
  provider: ChatProvider;
}

export function sendPortfolioChat(body: ChatRequest): Promise<ChatResponse> {
  return fetchJson<ChatResponse>("/chat", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(body),
  });
}

export function sendBondChat(body: BondChatRequest): Promise<ChatResponse> {
  return fetchJson<ChatResponse>("/chat/bond", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(body),
  });
}

export interface BondChatRequest {
  bond: BondScreenerItem;
  provider: ChatProvider;
  messages: ChatMessage[];
}
