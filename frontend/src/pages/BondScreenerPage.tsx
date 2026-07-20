import { useCallback, useEffect, useState } from "react";
import { getBondScreener, type BondScreenerItem } from "../api";
import { BondAiPanel } from "../components/BondAiPanel";
import { ErrorState } from "../components/ErrorState";
import {
  mergeStoredRecord,
  readLocalStorage,
  writeLocalStorage,
} from "../storage";
import {
  formatMoney,
  formatPercent,
  formatSector,
  formatYearsMonths,
} from "../utils";

type SortKey =
  | "ticker"
  | "current_yield"
  | "yield_to_maturity"
  | "credit_rating"
  | "sector"
  | "years_to_maturity"
  | "price_percent"
  | "maturity_date"
  | "annual_coupon";

type SortDir = "asc" | "desc";

const RATING_FILTER_OPTIONS = [
  { value: "all", label: "Все рейтинги" },
  { value: "gov", label: "Только гос." },
  { value: "AA-", label: "от AA-" },
  { value: "A-", label: "от A-" },
  { value: "BBB-", label: "от BBB-" },
  { value: "BB+", label: "от BB+" },
  { value: "B", label: "от B" },
  { value: "none", label: "Без рейтинга" },
] as const;

interface Filters {
  search: string;
  currency: string;
  sector: string;
  minRating: string;
  ofzOnly: boolean;
  hideQual: boolean;
  hideFloating: boolean;
  minYield: string;
  minYears: string;
  maxYears: string;
}

const DEFAULT_FILTERS: Filters = {
  search: "",
  currency: "rub",
  sector: "all",
  minRating: "all",
  ofzOnly: false,
  hideQual: true,
  hideFloating: false,
  minYield: "",
  minYears: "",
  maxYears: "",
};

const PAGE_SIZE = 100;
const STORAGE_KEY = "investhelper.bond-screener";

interface BondScreenerPrefs {
  filters: Filters;
  sortKey: SortKey;
  sortDir: SortDir;
  page: number;
}

const DEFAULT_PREFS: BondScreenerPrefs = {
  filters: DEFAULT_FILTERS,
  sortKey: "yield_to_maturity",
  sortDir: "desc",
  page: 1,
};

const BOND_SORT_KEYS = new Set<SortKey>([
  "ticker",
  "current_yield",
  "yield_to_maturity",
  "credit_rating",
  "sector",
  "years_to_maturity",
  "price_percent",
  "maturity_date",
  "annual_coupon",
]);

function loadBondScreenerPrefs(): BondScreenerPrefs {
  const stored = readLocalStorage<Partial<BondScreenerPrefs> | null>(
    STORAGE_KEY,
    null,
  );
  if (!stored) {
    return DEFAULT_PREFS;
  }

  const sortKey = BOND_SORT_KEYS.has(stored.sortKey as SortKey)
    ? (stored.sortKey as SortKey)
    : DEFAULT_PREFS.sortKey;
  const sortDir =
    stored.sortDir === "asc" || stored.sortDir === "desc"
      ? stored.sortDir
      : DEFAULT_PREFS.sortDir;
  const page =
    typeof stored.page === "number" && stored.page >= 1
      ? Math.floor(stored.page)
      : DEFAULT_PREFS.page;

  return {
    filters: mergeStoredRecord(DEFAULT_FILTERS, stored.filters),
    sortKey,
    sortDir,
    page,
  };
}

function formatDate(value: string | null): string {
  if (!value) return "—";
  return new Date(value).toLocaleDateString("ru-RU");
}

export function BondScreenerPage() {
  const initialPrefs = loadBondScreenerPrefs();
  const [bonds, setBonds] = useState<BondScreenerItem[]>([]);
  const [sectors, setSectors] = useState<string[]>([]);
  const [cachedAt, setCachedAt] = useState<string | null>(null);
  const [total, setTotal] = useState(0);
  const [filteredTotal, setFilteredTotal] = useState(0);
  const [page, setPage] = useState(initialPrefs.page);
  const [loading, setLoading] = useState(true);
  const [refreshing, setRefreshing] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [filters, setFilters] = useState<Filters>(initialPrefs.filters);
  const [debouncedSearch, setDebouncedSearch] = useState(initialPrefs.filters.search);
  const [sortKey, setSortKey] = useState<SortKey>(initialPrefs.sortKey);
  const [sortDir, setSortDir] = useState<SortDir>(initialPrefs.sortDir);
  const [aiBond, setAiBond] = useState<BondScreenerItem | null>(null);

  useEffect(() => {
    writeLocalStorage(STORAGE_KEY, { filters, sortKey, sortDir, page });
  }, [filters, sortKey, sortDir, page]);

  useEffect(() => {
    const timer = window.setTimeout(() => {
      setDebouncedSearch(filters.search);
    }, 300);
    return () => window.clearTimeout(timer);
  }, [filters.search]);

  const totalPages = Math.max(1, Math.ceil(filteredTotal / PAGE_SIZE));

  const load = useCallback(
    async (refresh = false) => {
      if (refresh) {
        setRefreshing(true);
      } else {
        setLoading(true);
      }
      setError(null);
      try {
        const data = await getBondScreener({
          page,
          page_size: PAGE_SIZE,
          sort_key: sortKey,
          sort_dir: sortDir,
          search: debouncedSearch,
          currency: filters.currency,
          sector: filters.sector,
          min_rating: filters.minRating,
          ofz_only: filters.ofzOnly,
          hide_qual: filters.hideQual,
          hide_floating: filters.hideFloating,
          min_yield: filters.minYield,
          min_years: filters.minYears,
          max_years: filters.maxYears,
          refresh,
        });
        setBonds(data.bonds);
        setSectors(data.sectors);
        setCachedAt(data.cached_at);
        setTotal(data.total);
        setFilteredTotal(data.filtered_total);
      } catch (err) {
        setError(
          err instanceof Error ? err.message : "Не удалось загрузить облигации",
        );
      } finally {
        setLoading(false);
        setRefreshing(false);
      }
    },
    [page, sortKey, sortDir, debouncedSearch, filters],
  );

  useEffect(() => {
    load();
  }, [load]);

  function updateFilters(patch: Partial<Filters>) {
    setPage(1);
    setFilters((prev) => ({ ...prev, ...patch }));
  }

  function toggleSort(key: SortKey) {
    setPage(1);
    if (sortKey === key) {
      setSortDir((dir) => (dir === "asc" ? "desc" : "asc"));
      return;
    }
    setSortKey(key);
    setSortDir(
      key === "ticker" || key === "sector" || key === "maturity_date"
        ? "asc"
        : "desc",
    );
  }

  function sortIndicator(key: SortKey): string {
    if (sortKey !== key) return "";
    return sortDir === "asc" ? " ↑" : " ↓";
  }

  return (
    <div className="content screener-content">
      <div className="page-toolbar screener-toolbar">
        <input
          className="filter-input search-input"
          placeholder="Поиск по тикеру, названию, ISIN…"
          value={filters.search}
          onChange={(event) =>
            updateFilters({ search: event.target.value })
          }
        />
        <select
          className="filter-input"
          value={filters.currency}
          onChange={(event) =>
            updateFilters({ currency: event.target.value })
          }
        >
          <option value="rub">RUB</option>
          <option value="usd">USD</option>
          <option value="eur">EUR</option>
          <option value="all">Все валюты</option>
        </select>
        <select
          className="filter-input sector-select"
          value={filters.sector}
          onChange={(event) => updateFilters({ sector: event.target.value })}
        >
          <option value="all">Все секторы</option>
          {sectors.map((sector) => (
            <option key={sector} value={sector}>
              {formatSector(sector)}
            </option>
          ))}
        </select>
        <select
          className="filter-input rating-select"
          value={filters.minRating}
          onChange={(event) =>
            updateFilters({ minRating: event.target.value })
          }
        >
          {RATING_FILTER_OPTIONS.map((option) => (
            <option key={option.value} value={option.value}>
              {option.label}
            </option>
          ))}
        </select>
        <input
          className="filter-input filter-number"
          placeholder="Мин. YTM %"
          value={filters.minYield}
          onChange={(event) =>
            updateFilters({ minYield: event.target.value })
          }
        />
        <input
          className="filter-input filter-number"
          placeholder="Срок от, лет"
          value={filters.minYears}
          onChange={(event) =>
            updateFilters({ minYears: event.target.value })
          }
        />
        <input
          className="filter-input filter-number"
          placeholder="Срок до, лет"
          value={filters.maxYears}
          onChange={(event) =>
            updateFilters({ maxYears: event.target.value })
          }
        />
        <label className="filter-check">
          <input
            type="checkbox"
            checked={filters.ofzOnly}
            onChange={(event) =>
              updateFilters({ ofzOnly: event.target.checked })
            }
          />
          Только ОФЗ
        </label>
        <label className="filter-check">
          <input
            type="checkbox"
            checked={filters.hideQual}
            onChange={(event) =>
              updateFilters({ hideQual: event.target.checked })
            }
          />
          Без квалиф.
        </label>
        <label className="filter-check">
          <input
            type="checkbox"
            checked={filters.hideFloating}
            onChange={(event) =>
              updateFilters({ hideFloating: event.target.checked })
            }
          />
          Без плавающих
        </label>
        <button
          className="btn-secondary"
          disabled={refreshing}
          onClick={() => load(true)}
        >
          {refreshing ? "Обновление…" : "Обновить"}
        </button>
        <span className="toolbar-meta">
          {filteredTotal} из {total}
          {cachedAt && (
            <>
              {" · "}
              кэш: {new Date(cachedAt).toLocaleTimeString("ru-RU")}
            </>
          )}
        </span>
      </div>

      {loading && (
        <div className="state-box screener-state">
          <strong>Загрузка скринера…</strong>
          <p className="state-hint">
            Сначала подгружается список и цены, затем детали по 100 облигаций на
            страницу.
          </p>
        </div>
      )}

      {!loading && error && <ErrorState error={error} />}

      {!loading && !error && (
        <>
          <section className="card screener-card">
            <div className="table-wrap screener-table-wrap">
              <table className="screener-table">
                <thead>
                  <tr>
                    <th>
                      <button
                        className="th-sort"
                        onClick={() => toggleSort("ticker")}
                      >
                        Инструмент{sortIndicator("ticker")}
                      </button>
                    </th>
                    <th>Тип</th>
                    <th>
                      <button
                        className="th-sort"
                        onClick={() => toggleSort("price_percent")}
                      >
                        Цена %{sortIndicator("price_percent")}
                      </button>
                    </th>
                    <th>
                      <button
                        className="th-sort"
                        onClick={() => toggleSort("sector")}
                      >
                        Сектор{sortIndicator("sector")}
                      </button>
                    </th>
                    <th>
                      <button
                        className="th-sort"
                        onClick={() => toggleSort("credit_rating")}
                      >
                        Рейтинг{sortIndicator("credit_rating")}
                      </button>
                    </th>
                    <th>
                      <button
                        className="th-sort"
                        onClick={() => toggleSort("yield_to_maturity")}
                      >
                        YTM{sortIndicator("yield_to_maturity")}
                      </button>
                    </th>
                    <th>
                      <button
                        className="th-sort"
                        onClick={() => toggleSort("current_yield")}
                      >
                        Тек. дох.{sortIndicator("current_yield")}
                      </button>
                    </th>
                    <th>
                      <button
                        className="th-sort"
                        onClick={() => toggleSort("annual_coupon")}
                      >
                        Купон/год{sortIndicator("annual_coupon")}
                      </button>
                    </th>
                    <th>
                      <button
                        className="th-sort"
                        onClick={() => toggleSort("maturity_date")}
                      >
                        Погашение{sortIndicator("maturity_date")}
                      </button>
                    </th>
                    <th>
                      <button
                        className="th-sort"
                        onClick={() => toggleSort("years_to_maturity")}
                      >
                        Лет до погаш.{sortIndicator("years_to_maturity")}
                      </button>
                    </th>
                    <th>НКД</th>
                    <th>Куп/год</th>
                    <th>AI</th>
                  </tr>
                </thead>
                <tbody>
                  {bonds.map((bond) => (
                    <tr key={bond.figi}>
                      <td>
                        <div className="ticker">{bond.ticker}</div>
                        <div className="instrument-name">{bond.name}</div>
                      </td>
                      <td>
                        <div className="badge-row">
                          {bond.is_ofz && <span className="badge">ОФЗ</span>}
                          {bond.floating_coupon && (
                            <span className="badge badge-warn">Плавающий</span>
                          )}
                          {bond.amortization && (
                            <span className="badge badge-muted">Аморт.</span>
                          )}
                          {bond.for_qual_investor && (
                            <span className="badge badge-warn">Квал.</span>
                          )}
                        </div>
                      </td>
                      <td className="mono">
                        {bond.price_percent !== null
                          ? `${Number(bond.price_percent).toFixed(2)}%`
                          : "—"}
                        {bond.price !== null && (
                          <div className="sub-cell">
                            {formatMoney(bond.price, bond.currency)}
                          </div>
                        )}
                      </td>
                      <td>{formatSector(bond.sector)}</td>
                      <td className="mono">
                        {bond.credit_rating ?? "—"}
                        {bond.risk_level && bond.risk_level !== "—" && (
                          <div className="sub-cell">Риск: {bond.risk_level}</div>
                        )}
                      </td>
                      <td className="mono positive">
                        {bond.floating_coupon || bond.amortization
                          ? "—"
                          : bond.yield_to_maturity !== null
                            ? formatPercent(bond.yield_to_maturity)
                            : "—"}
                      </td>
                      <td className="mono">
                        {bond.floating_coupon
                          ? "—"
                          : bond.current_yield !== null
                            ? formatPercent(bond.current_yield)
                            : "—"}
                      </td>
                      <td className="mono">
                        {bond.annual_coupon !== null
                          ? formatMoney(bond.annual_coupon, bond.currency)
                          : "—"}
                      </td>
                      <td className="mono">{formatDate(bond.maturity_date)}</td>
                      <td className="mono term-cell">
                        {formatYearsMonths(bond.years_to_maturity)}
                      </td>
                      <td className="mono">
                        {formatMoney(bond.nkd, bond.currency)}
                      </td>
                      <td className="mono">{bond.coupon_per_year || "—"}</td>
                      <td>
                        <button
                          type="button"
                          className="btn-ai"
                          onClick={() => setAiBond(bond)}
                          title="Summary по отчётам АКРА и Эксперт РА"
                        >
                          AI
                        </button>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </section>

          {totalPages > 1 && (
            <div className="pagination">
              <button
                className="btn-secondary"
                disabled={page <= 1 || loading}
                onClick={() => setPage((value) => Math.max(1, value - 1))}
              >
                Назад
              </button>
              <span className="pagination-meta mono">
                Страница {page} из {totalPages}
              </span>
              <button
                className="btn-secondary"
                disabled={page >= totalPages || loading}
                onClick={() =>
                  setPage((value) => Math.min(totalPages, value + 1))
                }
              >
                Вперёд
              </button>
            </div>
          )}
        </>
      )}

      {aiBond && (
        <BondAiPanel bond={aiBond} onClose={() => setAiBond(null)} />
      )}
    </div>
  );
}
