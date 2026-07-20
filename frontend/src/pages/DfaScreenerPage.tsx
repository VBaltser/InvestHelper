import { useCallback, useEffect, useState } from "react";
import { getDfaScreener, type DfaScreenerItem } from "../api";
import { ErrorState } from "../components/ErrorState";
import {
  mergeStoredRecord,
  readLocalStorage,
  writeLocalStorage,
} from "../storage";
import { formatMoney, formatPercent, formatYearsMonths } from "../utils";

type SortKey =
  | "ticker"
  | "issuer_name"
  | "price"
  | "price_percent"
  | "yield_to_maturity"
  | "annual_coupon"
  | "maturity_date"
  | "years_to_maturity"
  | "coupon_per_year";

type SortDir = "asc" | "desc";

interface Filters {
  search: string;
  currency: string;
  buyOnly: boolean;
  hideQual: boolean;
  minYield: string;
  minYears: string;
  maxYears: string;
}

const DEFAULT_FILTERS: Filters = {
  search: "",
  currency: "rub",
  buyOnly: false,
  hideQual: true,
  minYield: "",
  minYears: "",
  maxYears: "",
};

const PAGE_SIZE = 100;
const STORAGE_KEY = "investhelper.dfa-screener";

interface DfaScreenerPrefs {
  filters: Filters;
  sortKey: SortKey;
  sortDir: SortDir;
  page: number;
}

const DEFAULT_PREFS: DfaScreenerPrefs = {
  filters: DEFAULT_FILTERS,
  sortKey: "yield_to_maturity",
  sortDir: "desc",
  page: 1,
};

const DFA_SORT_KEYS = new Set<SortKey>([
  "ticker",
  "issuer_name",
  "price",
  "price_percent",
  "yield_to_maturity",
  "annual_coupon",
  "maturity_date",
  "years_to_maturity",
  "coupon_per_year",
]);

function loadDfaScreenerPrefs(): DfaScreenerPrefs {
  const stored = readLocalStorage<Partial<DfaScreenerPrefs> | null>(
    STORAGE_KEY,
    null,
  );
  if (!stored) {
    return DEFAULT_PREFS;
  }

  const sortKey = DFA_SORT_KEYS.has(stored.sortKey as SortKey)
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

export function DfaScreenerPage() {
  const initialPrefs = loadDfaScreenerPrefs();
  const [items, setItems] = useState<DfaScreenerItem[]>([]);
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
        const data = await getDfaScreener({
          page,
          page_size: PAGE_SIZE,
          sort_key: sortKey,
          sort_dir: sortDir,
          search: debouncedSearch,
          currency: filters.currency,
          buy_only: filters.buyOnly,
          hide_qual: filters.hideQual,
          min_yield: filters.minYield,
          min_years: filters.minYears,
          max_years: filters.maxYears,
          refresh,
        });
        setItems(data.items);
        setCachedAt(data.cached_at);
        setTotal(data.total);
        setFilteredTotal(data.filtered_total);
      } catch (err) {
        setError(
          err instanceof Error ? err.message : "Не удалось загрузить ЦФА",
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
      key === "ticker" || key === "maturity_date" ? "asc" : "desc",
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
          placeholder="Поиск по тикеру, эмитенту…"
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
          <option value="all">Все валюты</option>
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
            checked={filters.buyOnly}
            onChange={(event) =>
              updateFilters({ buyOnly: event.target.checked })
            }
          />
          Только доступные к покупке
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
          <strong>Загрузка скринера ЦФА…</strong>
          <p className="state-hint">
            Загружаются долговые ЦФА и актуальные цены.
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
                    <th>Доступность</th>
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
                        onClick={() => toggleSort("yield_to_maturity")}
                      >
                        YTM{sortIndicator("yield_to_maturity")}
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
                    <th>
                      <button
                        className="th-sort"
                        onClick={() => toggleSort("coupon_per_year")}
                      >
                        Куп/год{sortIndicator("coupon_per_year")}
                      </button>
                    </th>
                  </tr>
                </thead>
                <tbody>
                  {items.map((item) => (
                    <tr key={item.uid}>
                      <td>
                        <div className="instrument-name">
                          {item.display_name || item.name}
                        </div>
                        <div className="ticker">{item.ticker}</div>
                        {item.product_type && (
                          <div className="sub-cell">{item.product_type}</div>
                        )}
                      </td>
                      <td>
                        <div className="badge-row">
                          {item.buy_available && (
                            <span className="badge">Покупка</span>
                          )}
                          {item.sell_available && (
                            <span className="badge badge-muted">Продажа</span>
                          )}
                          {!item.buy_available && !item.sell_available && (
                            <span className="badge badge-warn">Недоступен</span>
                          )}
                          {item.for_qual_investor && (
                            <span className="badge badge-warn">Квал.</span>
                          )}
                        </div>
                      </td>
                      <td className="mono">
                        {item.price_percent !== null
                          ? `${Number(item.price_percent).toFixed(2)}%`
                          : "—"}
                        {item.price !== null && (
                          <div className="sub-cell">
                            {formatMoney(item.price, item.currency)}
                          </div>
                        )}
                      </td>
                      <td className="mono positive">
                        {item.yield_to_maturity !== null
                          ? formatPercent(item.yield_to_maturity)
                          : "—"}
                        {item.yield_at_nominal !== null &&
                          item.yield_to_maturity !== null &&
                          Number(item.yield_at_nominal).toFixed(2) !==
                            Number(item.yield_to_maturity).toFixed(2) && (
                            <div className="sub-cell">
                              при ном.: {formatPercent(item.yield_at_nominal)}
                            </div>
                          )}
                      </td>
                      <td className="mono">
                        {item.annual_coupon !== null
                          ? formatMoney(item.annual_coupon, item.currency)
                          : "—"}
                      </td>
                      <td className="mono">{formatDate(item.maturity_date)}</td>
                      <td className="mono term-cell">
                        {formatYearsMonths(item.years_to_maturity)}
                      </td>
                      <td className="mono">
                        {formatMoney(item.nkd, item.currency)}
                      </td>
                      <td className="mono">{item.coupon_per_year || "—"}</td>
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
    </div>
  );
}
