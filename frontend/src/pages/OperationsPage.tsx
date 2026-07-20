import { useEffect, useState } from "react";
import {
  getAccounts,
  getOperations,
  type Account,
  type OperationItem,
  type OperationsPeriod,
  type OperationsSummary,
} from "../api";
import { ErrorState } from "../components/ErrorState";
import { formatMoney, formatQuantity } from "../utils";

const PERIOD_OPTIONS: Array<{ value: OperationsPeriod; label: string }> = [
  { value: "month", label: "За последний месяц" },
  { value: "week", label: "За последнюю неделю" },
  { value: "day", label: "За последний день" },
  { value: "all", label: "За всё время" },
];

function formatDateTime(value: string): string {
  if (!value) return "—";
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) return value;
  return date.toLocaleString("ru-RU", {
    day: "2-digit",
    month: "2-digit",
    year: "numeric",
    hour: "2-digit",
    minute: "2-digit",
  });
}

function paymentClass(value: string): string {
  const amount = Number(value);
  if (amount > 0) return "mono positive";
  if (amount < 0) return "mono negative";
  return "mono";
}

function operationTitle(item: OperationItem): string {
  if (item.ticker) return item.ticker;
  if (item.name) return item.name;
  return item.type_label;
}

function operationSubtitle(item: OperationItem): string {
  const parts: string[] = [];
  if (item.ticker && item.name && item.name !== item.ticker) {
    parts.push(item.name);
  } else if (!item.ticker && item.description && item.description !== item.name) {
    parts.push(item.description);
  }
  if (item.instrument_type_label) {
    parts.push(item.instrument_type_label);
  }
  return parts.join(" · ");
}

function OperationsSummaryCard({ summary }: { summary: OperationsSummary }) {
  const income =
    Number(summary.dividends) + Number(summary.coupons);
  const currency = summary.currency;

  return (
    <section className="card summary-card operations-summary-card">
      <div>
        <div className="metric-label">Операций</div>
        <div className="metric-value">{summary.total_count}</div>
        <div className="metric-sub">
          Покупок {summary.buy_count} · Продаж {summary.sell_count}
        </div>
      </div>
      <div>
        <div className="metric-label">Пополнения</div>
        <div className="metric-value positive">
          {formatMoney(summary.deposits, currency)}
        </div>
      </div>
      <div>
        <div className="metric-label">Выводы</div>
        <div className="metric-value negative">
          {formatMoney(summary.withdrawals, currency)}
        </div>
      </div>
      <div>
        <div className="metric-label">Дивиденды и купоны</div>
        <div className={`metric-value ${income > 0 ? "positive" : ""}`}>
          {formatMoney(income, currency)}
        </div>
        <div className="metric-sub">
          Див. {formatMoney(summary.dividends, currency)} · Куп.{" "}
          {formatMoney(summary.coupons, currency)}
        </div>
      </div>
      <div>
        <div className="metric-label">Комиссии</div>
        <div className="metric-value negative">
          {formatMoney(summary.commissions, currency)}
        </div>
      </div>
      <div>
        <div className="metric-label">Налоги</div>
        <div className="metric-value negative">
          {formatMoney(summary.taxes, currency)}
        </div>
      </div>
    </section>
  );
}

export function OperationsPage() {
  const [accounts, setAccounts] = useState<Account[]>([]);
  const [selectedAccountId, setSelectedAccountId] = useState("");
  const [items, setItems] = useState<OperationItem[]>([]);
  const [summary, setSummary] = useState<OperationsSummary | null>(null);
  const [period, setPeriod] = useState<OperationsPeriod>("month");
  const [stateFilter, setStateFilter] = useState("OPERATION_STATE_EXECUTED");
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    let cancelled = false;

    async function loadAccounts() {
      setLoading(true);
      setError(null);
      try {
        const data = await getAccounts();
        if (cancelled) return;
        setAccounts(data);
        if (data.length > 0) {
          setSelectedAccountId(data[0].id);
        } else {
          setLoading(false);
        }
      } catch (err) {
        if (!cancelled) {
          setError(
            err instanceof Error ? err.message : "Не удалось загрузить счета",
          );
          setLoading(false);
        }
      }
    }

    loadAccounts();
    return () => {
      cancelled = true;
    };
  }, []);

  useEffect(() => {
    if (!selectedAccountId) return;

    let cancelled = false;

    async function loadOperations() {
      setLoading(true);
      setError(null);
      try {
        const data = await getOperations(selectedAccountId, {
          period,
          state: stateFilter || undefined,
        });
        if (cancelled) return;
        setItems(data.items);
        setSummary(data.summary);
      } catch (err) {
        if (!cancelled) {
          setItems([]);
          setSummary(null);
          setError(
            err instanceof Error
              ? err.message
              : "Не удалось загрузить операции",
          );
        }
      } finally {
        if (!cancelled) setLoading(false);
      }
    }

    loadOperations();
    return () => {
      cancelled = true;
    };
  }, [selectedAccountId, period, stateFilter]);

  return (
    <div className="content">
      <div className="page-toolbar screener-toolbar">
        {accounts.length > 0 && (
          <select
            className="account-select"
            value={selectedAccountId}
            onChange={(event) => setSelectedAccountId(event.target.value)}
          >
            {accounts.map((account) => (
              <option key={account.id} value={account.id}>
                {account.name}
              </option>
            ))}
          </select>
        )}
        <select
          className="filter-input period-select"
          value={period}
          onChange={(event) =>
            setPeriod(event.target.value as OperationsPeriod)
          }
        >
          {PERIOD_OPTIONS.map((option) => (
            <option key={option.value} value={option.value}>
              {option.label}
            </option>
          ))}
        </select>
        <select
          className="filter-input"
          value={stateFilter}
          onChange={(event) => setStateFilter(event.target.value)}
        >
          <option value="OPERATION_STATE_EXECUTED">Исполненные</option>
          <option value="OPERATION_STATE_CANCELED">Отменённые</option>
          <option value="OPERATION_STATE_PROGRESS">В процессе</option>
          <option value="">Все статусы</option>
        </select>
      </div>

      {loading && <div className="state-box">Загрузка операций…</div>}

      {!loading && error && (
        <ErrorState
          error={error}
          hint="Backend запущен, но T-Invest API недоступен из вашей сети. Попробуйте VPN или мобильный интернет."
        />
      )}

      {!loading && !error && summary && (
        <div className="operations-layout">
          <OperationsSummaryCard summary={summary} />

          <section className="card positions-card">
            <div className="operations-header">
              <h2>Операции</h2>
              <span className="pagination-meta">
                {items.length > 0
                  ? `${items.length} записей`
                  : "Нет операций"}
              </span>
            </div>
            <div className="table-wrap">
              <table className="operations-table">
                <thead>
                  <tr>
                    <th>Дата</th>
                    <th>Тип</th>
                    <th>Инструмент</th>
                    <th>Кол-во</th>
                    <th>Цена</th>
                    <th>Сумма</th>
                    <th>Комиссия</th>
                    <th>Статус</th>
                  </tr>
                </thead>
                <tbody>
                  {items.map((item) => {
                    const qty = Number(item.quantity_done || item.quantity);
                    const price = Number(item.price);
                    const commission = Number(item.commission);
                    return (
                      <tr key={`${item.id}-${item.date}`}>
                        <td className="mono">{formatDateTime(item.date)}</td>
                        <td>
                          <span className="badge">{item.type_label}</span>
                        </td>
                        <td>
                          <div className="ticker">{operationTitle(item)}</div>
                          {operationSubtitle(item) && (
                            <div className="instrument-name">
                              {operationSubtitle(item)}
                            </div>
                          )}
                        </td>
                        <td className="mono">
                          {qty !== 0 ? formatQuantity(qty) : "—"}
                        </td>
                        <td className="mono">
                          {price !== 0
                            ? formatMoney(item.price, item.price_currency)
                            : "—"}
                        </td>
                        <td className={paymentClass(item.payment)}>
                          {formatMoney(
                            item.payment,
                            item.payment_currency,
                            true,
                          )}
                        </td>
                        <td className="mono">
                          {commission !== 0
                            ? formatMoney(
                                item.commission,
                                item.commission_currency,
                              )
                            : "—"}
                        </td>
                        <td>
                          <span className="badge badge-muted">
                            {item.state_label}
                          </span>
                        </td>
                      </tr>
                    );
                  })}
                </tbody>
              </table>
            </div>
          </section>
        </div>
      )}
    </div>
  );
}
