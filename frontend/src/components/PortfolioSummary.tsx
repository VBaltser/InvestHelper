import type { PortfolioSummary } from "../api";
import { formatMoney, formatPercent, unrealizedYieldPercent } from "../utils";

interface Props {
  portfolio: PortfolioSummary;
}

export function PortfolioSummaryCard({ portfolio }: Props) {
  const yieldValue = Number(portfolio.expected_yield);
  const yieldClass = yieldValue >= 0 ? "positive" : "negative";
  const yieldPercent = unrealizedYieldPercent(
    portfolio.expected_yield,
    portfolio.total_amount,
  );

  return (
    <section className="card summary-card">
      <div>
        <div className="metric-label">Стоимость портфеля</div>
        <div className="metric-value">
          {formatMoney(portfolio.total_amount, portfolio.currency)}
        </div>
      </div>
      <div>
        <div className="metric-label">Нереализованный доход</div>
        <div className={`metric-value ${yieldClass}`}>
          {formatMoney(yieldValue, portfolio.currency, true)}
          {yieldPercent !== null && (
            <span className="metric-value small" style={{ marginLeft: 10 }}>
              ({formatPercent(yieldPercent, true)})
            </span>
          )}
        </div>
      </div>
      {portfolio.daily_yield !== null && (
        <div>
          <div className="metric-label">За день</div>
          <div
            className={`metric-value ${
              Number(portfolio.daily_yield) >= 0 ? "positive" : "negative"
            }`}
          >
            {formatMoney(portfolio.daily_yield, portfolio.currency)}
            {portfolio.daily_yield_relative !== null && (
              <span className="metric-value small" style={{ marginLeft: 10 }}>
                ({formatPercent(portfolio.daily_yield_relative, true)})
              </span>
            )}
          </div>
        </div>
      )}
      <div>
        <div className="metric-label">Позиций</div>
        <div className="metric-value">{portfolio.positions.length}</div>
      </div>
    </section>
  );
}
