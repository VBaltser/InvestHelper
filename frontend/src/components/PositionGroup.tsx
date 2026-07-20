import { useMemo, useState } from "react";
import type { Position } from "../api";
import {
  averageCreditRating,
  formatMoney,
  formatPercent,
  formatQuantity,
  purchaseReturnPercent,
  ratingSortKey,
  unrealizedYieldPercent,
  weightedAverage,
} from "../utils";

interface Props {
  title: string;
  positions: Position[];
  currency: string;
  variant?: "default" | "bonds";
  bondMetricsLoading?: boolean;
}

type SortKey =
  | "instrument"
  | "quantity"
  | "current_price"
  | "average_price"
  | "current_value"
  | "share_percent"
  | "purchase_return"
  | "current_yield_to_maturity"
  | "yield_to_maturity"
  | "days_to_maturity"
  | "credit_rating"
  | "expected_yield";

type SortDir = "asc" | "desc";

function comparePositions(
  a: Position,
  b: Position,
  key: SortKey,
  dir: SortDir,
): number {
  const sign = dir === "asc" ? 1 : -1;

  if (key === "instrument") {
    const byName = a.name.localeCompare(b.name, "ru");
    if (byName !== 0) return byName * sign;
    return a.ticker.localeCompare(b.ticker, "ru") * sign;
  }

  if (key === "credit_rating") {
    const aRating = ratingSortKey(a.credit_rating, dir === "asc");
    const bRating = ratingSortKey(b.credit_rating, dir === "asc");
    return (aRating - bRating) * sign;
  }

  let aValue: number | null;
  let bValue: number | null;

  switch (key) {
    case "quantity":
      aValue = Number(a.quantity);
      bValue = Number(b.quantity);
      break;
    case "current_price":
      aValue = Number(a.current_price);
      bValue = Number(b.current_price);
      break;
    case "average_price":
      aValue = Number(a.average_price);
      bValue = Number(b.average_price);
      break;
    case "current_value":
      aValue = Number(a.current_value);
      bValue = Number(b.current_value);
      break;
    case "share_percent":
      aValue = Number(a.share_percent);
      bValue = Number(b.share_percent);
      break;
    case "purchase_return":
      aValue = purchaseReturnPercent(a.current_price, a.average_price);
      bValue = purchaseReturnPercent(b.current_price, b.average_price);
      break;
    case "current_yield_to_maturity":
      aValue =
        a.current_yield_to_maturity != null && a.current_yield_to_maturity !== ""
          ? Number(a.current_yield_to_maturity)
          : null;
      bValue =
        b.current_yield_to_maturity != null && b.current_yield_to_maturity !== ""
          ? Number(b.current_yield_to_maturity)
          : null;
      break;
    case "yield_to_maturity":
      aValue =
        a.yield_to_maturity != null && a.yield_to_maturity !== ""
          ? Number(a.yield_to_maturity)
          : null;
      bValue =
        b.yield_to_maturity != null && b.yield_to_maturity !== ""
          ? Number(b.yield_to_maturity)
          : null;
      break;
    case "days_to_maturity":
      aValue = a.days_to_maturity;
      bValue = b.days_to_maturity;
      break;
    case "expected_yield":
      aValue = Number(a.expected_yield);
      bValue = Number(b.expected_yield);
      break;
    default:
      return 0;
  }

  if (aValue === null && bValue === null) return 0;
  if (aValue === null) return 1;
  if (bValue === null) return -1;
  if (aValue === bValue) return 0;
  return (aValue < bValue ? -1 : 1) * sign;
}

function priceCompareClass(currentPrice: string, averagePrice: string): string {
  const current = Number(currentPrice);
  const average = Number(averagePrice);
  if (average <= 0) return "";
  return current > average ? "negative" : "positive";
}

function currentYtmCompareClass(
  currentYtm: string | null,
  entryYtm: string | null,
): string {
  if (
    currentYtm == null ||
    currentYtm === "" ||
    entryYtm == null ||
    entryYtm === ""
  ) {
    return "";
  }
  const current = Number(currentYtm);
  const entry = Number(entryYtm);
  if (!Number.isFinite(current) || !Number.isFinite(entry)) return "";
  return current > entry ? "positive" : "negative";
}

export function PositionGroup({
  title,
  positions,
  currency,
  variant = "default",
  bondMetricsLoading = false,
}: Props) {
  const [sortKey, setSortKey] = useState<SortKey>("current_value");
  const [sortDir, setSortDir] = useState<SortDir>("desc");

  const sortedPositions = useMemo(() => {
    return [...positions].sort((a, b) => comparePositions(a, b, sortKey, sortDir));
  }, [positions, sortKey, sortDir]);

  function toggleSort(key: SortKey) {
    if (sortKey === key) {
      setSortDir((dir) => (dir === "asc" ? "desc" : "asc"));
      return;
    }
    setSortKey(key);
    setSortDir(key === "instrument" ? "asc" : "desc");
  }

  function sortIndicator(key: SortKey): string {
    if (sortKey !== key) return "";
    return sortDir === "asc" ? " ↑" : " ↓";
  }

  if (positions.length === 0) return null;

  const isBonds = variant === "bonds";
  const totalValue = positions.reduce(
    (sum, position) => sum + Number(position.current_value),
    0,
  );
  const totalShare = positions.reduce(
    (sum, position) => sum + Number(position.share_percent),
    0,
  );

  const avgCurrentYtm = isBonds
    ? weightedAverage(
        positions.map((position) => ({
          value:
            position.current_yield_to_maturity !== null
              ? Number(position.current_yield_to_maturity)
              : null,
          weight: Number(position.current_value),
        })),
      )
    : null;

  const avgEntryYtm = isBonds
    ? weightedAverage(
        positions.map((position) => ({
          value:
            position.yield_to_maturity !== null
              ? Number(position.yield_to_maturity)
              : null,
          weight: Number(position.current_value),
        })),
      )
    : null;

  const avgCreditRating = isBonds
    ? averageCreditRating(
        positions.map((position) => ({
          rating: position.credit_rating,
          weight: Number(position.current_value),
        })),
      )
    : null;

  const totalMaturityIncome = isBonds
    ? positions.reduce((sum, position) => {
        if (
          position.maturity_income_rub == null ||
          position.maturity_income_rub === ""
        ) {
          return sum;
        }
        return sum + Number(position.maturity_income_rub);
      }, 0)
    : null;

  const hasMaturityIncome = isBonds
    ? positions.some(
        (position) =>
          position.maturity_income_rub != null &&
          position.maturity_income_rub !== "",
      )
    : false;

  return (
    <section className="card position-group-card">
      <div className="position-group-header">
        <h2>{title}</h2>
        <div className="position-group-summary">
          <div className="position-group-stat">
            <span className="position-group-stat-label">Позиций</span>
            <span className="position-group-stat-value">{positions.length}</span>
          </div>
          <div className="position-group-stat">
            <span className="position-group-stat-label">Стоимость</span>
            <span className="position-group-stat-value">
              {formatMoney(totalValue, currency)}
            </span>
          </div>
          <div className="position-group-stat">
            <span className="position-group-stat-label">Доля</span>
            <span className="position-group-stat-value">
              {formatPercent(totalShare)}
            </span>
          </div>
          {isBonds && (
            <div className="position-group-stat">
              <span className="position-group-stat-label">Ср. YTM</span>
              <span className="position-group-stat-value">
                {bondMetricsLoading && avgCurrentYtm === null
                  ? "…"
                  : avgCurrentYtm !== null
                    ? formatPercent(avgCurrentYtm)
                    : "—"}
              </span>
            </div>
          )}
          {isBonds && (
            <div className="position-group-stat">
              <span className="position-group-stat-label">YTM от входа</span>
              <span className="position-group-stat-value">
                {bondMetricsLoading && avgEntryYtm === null
                  ? "…"
                  : avgEntryYtm !== null
                    ? formatPercent(avgEntryYtm)
                    : "—"}
              </span>
            </div>
          )}
          {isBonds && (
            <div className="position-group-stat">
              <span className="position-group-stat-label">Ср. рейтинг</span>
              <span className="position-group-stat-value">
                {bondMetricsLoading && avgCreditRating === null
                  ? "…"
                  : (avgCreditRating ?? "—")}
              </span>
            </div>
          )}
          {isBonds && (
            <div className="position-group-stat position-group-stat-highlight">
              <span className="position-group-stat-label">
                Доход к погашению, ₽
              </span>
              <span
                className={`position-group-stat-value ${
                  totalMaturityIncome !== null && totalMaturityIncome >= 0
                    ? "positive"
                    : totalMaturityIncome !== null && totalMaturityIncome < 0
                      ? "negative"
                      : ""
                }`}
              >
                {bondMetricsLoading && !hasMaturityIncome
                  ? "…"
                  : hasMaturityIncome
                    ? formatMoney(totalMaturityIncome ?? 0, "rub", true)
                    : "—"}
              </span>
            </div>
          )}
        </div>
      </div>
      <div className="table-wrap position-group-table-wrap">
        <table>
          <thead>
            <tr>
              <th>
                <button
                  type="button"
                  className="th-sort"
                  onClick={() => toggleSort("instrument")}
                >
                  Инструмент{sortIndicator("instrument")}
                </button>
              </th>
              <th>
                <button
                  type="button"
                  className="th-sort"
                  onClick={() => toggleSort("quantity")}
                >
                  Кол-во{sortIndicator("quantity")}
                </button>
              </th>
              <th>
                <button
                  type="button"
                  className="th-sort"
                  onClick={() => toggleSort("current_price")}
                >
                  Цена{sortIndicator("current_price")}
                </button>
              </th>
              <th>
                <button
                  type="button"
                  className="th-sort"
                  onClick={() => toggleSort("average_price")}
                >
                  Ср. цена входа{sortIndicator("average_price")}
                </button>
              </th>
              <th>
                <button
                  type="button"
                  className="th-sort"
                  onClick={() => toggleSort("current_value")}
                >
                  Стоимость{sortIndicator("current_value")}
                </button>
              </th>
              <th>
                <button
                  type="button"
                  className="th-sort"
                  onClick={() => toggleSort("share_percent")}
                >
                  Доля{sortIndicator("share_percent")}
                </button>
              </th>
              <th>
                <button
                  type="button"
                  className="th-sort"
                  onClick={() => toggleSort("purchase_return")}
                >
                  От покупки{sortIndicator("purchase_return")}
                </button>
              </th>
              {isBonds && (
                <th>
                  <button
                    type="button"
                    className="th-sort"
                    onClick={() => toggleSort("current_yield_to_maturity")}
                  >
                    Тек. YTM{sortIndicator("current_yield_to_maturity")}
                  </button>
                </th>
              )}
              {isBonds && (
                <th>
                  <button
                    type="button"
                    className="th-sort"
                    onClick={() => toggleSort("yield_to_maturity")}
                  >
                    YTM от входа{sortIndicator("yield_to_maturity")}
                  </button>
                </th>
              )}
              {isBonds && (
                <th>
                  <button
                    type="button"
                    className="th-sort"
                    onClick={() => toggleSort("days_to_maturity")}
                  >
                    Дней до погаш.{sortIndicator("days_to_maturity")}
                  </button>
                </th>
              )}
              {isBonds && (
                <th>
                  <button
                    type="button"
                    className="th-sort"
                    onClick={() => toggleSort("credit_rating")}
                  >
                    Рейтинг{sortIndicator("credit_rating")}
                  </button>
                </th>
              )}
              <th>
                <button
                  type="button"
                  className="th-sort"
                  onClick={() => toggleSort("expected_yield")}
                >
                  Доход{sortIndicator("expected_yield")}
                </button>
              </th>
            </tr>
          </thead>
          <tbody>
            {sortedPositions.map((position) => {
              const yieldValue = Number(position.expected_yield);
              const yieldClass = yieldValue >= 0 ? "positive" : "negative";
              const yieldPercent = unrealizedYieldPercent(
                position.expected_yield,
                position.current_value,
              );
              const purchaseReturn = purchaseReturnPercent(
                position.current_price,
                position.average_price,
              );
              const purchaseClass =
                purchaseReturn === null
                  ? ""
                  : purchaseReturn >= 0
                    ? "positive"
                    : "negative";
              const priceClass = priceCompareClass(
                position.current_price,
                position.average_price,
              );
              const currentYtmClass = isBonds
                ? currentYtmCompareClass(
                    position.current_yield_to_maturity,
                    position.yield_to_maturity,
                  )
                : "";

              return (
                <tr key={`${position.ticker}-${position.instrument_type}`}>
                  <td>
                    <div className="ticker">{position.name}</div>
                    <div className="instrument-name">{position.ticker}</div>
                  </td>
                  <td className="mono">{formatQuantity(position.quantity)}</td>
                  <td className={`mono ${priceClass}`}>
                    {formatMoney(position.current_price, position.currency)}
                  </td>
                  <td className="mono">
                    {formatMoney(position.average_price, position.currency)}
                  </td>
                  <td className="mono">
                    {formatMoney(position.current_value, currency)}
                  </td>
                  <td className="mono">
                    {formatPercent(position.share_percent)}
                  </td>
                  <td className={`mono ${purchaseClass}`}>
                    {purchaseReturn !== null
                      ? formatPercent(purchaseReturn, true)
                      : "—"}
                  </td>
                  {isBonds && (
                    <td
                      className={`mono ${
                        bondMetricsLoading &&
                        (position.current_yield_to_maturity == null ||
                          position.current_yield_to_maturity === "")
                          ? ""
                          : currentYtmClass
                      }`}
                    >
                      {bondMetricsLoading &&
                      (position.current_yield_to_maturity == null ||
                        position.current_yield_to_maturity === "")
                        ? "…"
                        : position.current_yield_to_maturity != null &&
                            position.current_yield_to_maturity !== ""
                          ? formatPercent(position.current_yield_to_maturity)
                          : "—"}
                    </td>
                  )}
                  {isBonds && (
                    <td className="mono">
                      {bondMetricsLoading &&
                      (position.yield_to_maturity == null ||
                        position.yield_to_maturity === "")
                        ? "…"
                        : position.yield_to_maturity != null &&
                            position.yield_to_maturity !== ""
                          ? formatPercent(position.yield_to_maturity)
                          : "—"}
                    </td>
                  )}
                  {isBonds && (
                    <td className="mono">
                      {position.days_to_maturity !== null
                        ? position.days_to_maturity
                        : "—"}
                    </td>
                  )}
                  {isBonds && (
                    <td className="mono">
                      {bondMetricsLoading && position.credit_rating === null
                        ? "…"
                        : (position.credit_rating ?? "—")}
                    </td>
                  )}
                  <td className={`mono ${yieldClass}`}>
                    {formatMoney(yieldValue, position.currency, true)}
                    {yieldPercent !== null && (
                      <span className="sub-cell">
                        ({formatPercent(yieldPercent, true)})
                      </span>
                    )}
                  </td>
                </tr>
              );
            })}
          </tbody>
        </table>
      </div>
    </section>
  );
}
