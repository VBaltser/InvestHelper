import { useEffect, useState } from "react";
import {
  getAccounts,
  getPortfolio,
  getPortfolioBondMetrics,
  type Account,
  type BondPortfolioMetric,
  type PortfolioSummary,
} from "../api";
import { AssetAllocation } from "../components/AssetAllocation";
import { ErrorState } from "../components/ErrorState";
import { PortfolioChat } from "../components/PortfolioChat";
import { PortfolioPositions } from "../components/PortfolioPositions";
import { PortfolioSummaryCard } from "../components/PortfolioSummary";

export function PortfolioPage() {
  const [accounts, setAccounts] = useState<Account[]>([]);
  const [selectedAccountId, setSelectedAccountId] = useState("");
  const [portfolio, setPortfolio] = useState<PortfolioSummary | null>(null);
  const [bondMetrics, setBondMetrics] = useState<
    Record<string, BondPortfolioMetric>
  >({});
  const [loading, setLoading] = useState(true);
  const [bondMetricsLoading, setBondMetricsLoading] = useState(false);
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
        }
      } catch (err) {
        if (!cancelled) {
          setError(
            err instanceof Error ? err.message : "Не удалось загрузить счета",
          );
        }
      } finally {
        if (!cancelled) setLoading(false);
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

    async function loadPortfolio() {
      setLoading(true);
      setError(null);
      setBondMetrics({});
      setBondMetricsLoading(false);
      try {
        const data = await getPortfolio(selectedAccountId);
        if (cancelled) return;
        setPortfolio(data);
        setLoading(false);

        const bonds = data.positions.filter(
          (position) => position.instrument_type === "bond",
        );
        if (bonds.length === 0) return;

        setBondMetricsLoading(true);
        try {
          const metricsResponse = await getPortfolioBondMetrics(
            bonds.map((bond) => ({
              figi: bond.figi,
              ticker: bond.ticker,
              name: bond.name,
              average_price: bond.average_price,
              current_price: bond.current_price,
              current_nkd: bond.current_nkd,
              quantity: bond.quantity,
            })),
          );
          if (cancelled) return;

          const nextMetrics: Record<string, BondPortfolioMetric> = {};
          for (const metric of metricsResponse.metrics) {
            nextMetrics[metric.figi] = metric;
          }
          setBondMetrics(nextMetrics);
        } catch (err) {
          if (!cancelled) {
            console.error("Не удалось загрузить метрики облигаций:", err);
            setBondMetrics({});
          }
        } finally {
          if (!cancelled) setBondMetricsLoading(false);
        }
      } catch (err) {
        if (!cancelled) {
          setPortfolio(null);
          setBondMetrics({});
          setError(
            err instanceof Error
              ? err.message
              : "Не удалось загрузить портфель",
          );
          setLoading(false);
        }
      }
    }

    loadPortfolio();
    return () => {
      cancelled = true;
    };
  }, [selectedAccountId]);

  return (
    <div className="content">
      {accounts.length > 0 && (
        <div className="page-toolbar">
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
        </div>
      )}

      {loading && <div className="state-box">Загрузка портфеля…</div>}

      {!loading && error && (
        <ErrorState
          error={error}
          hint="Backend запущен, но T-Invest API недоступен из вашей сети. Попробуйте VPN или мобильный интернет."
        />
      )}

      {!loading && !error && portfolio && (
        <div className="dashboard">
          <div className="dashboard-header">
            <PortfolioSummaryCard portfolio={portfolio} />
            <AssetAllocation
              allocation={portfolio.allocation}
              currency={portfolio.currency}
              compact
            />
          </div>
          <div className="dashboard-body">
            <PortfolioPositions
              positions={portfolio.positions}
              currency={portfolio.currency}
              bondMetrics={bondMetrics}
              bondMetricsLoading={bondMetricsLoading}
            />
            <PortfolioChat accountId={selectedAccountId} />
          </div>
        </div>
      )}
    </div>
  );
}
