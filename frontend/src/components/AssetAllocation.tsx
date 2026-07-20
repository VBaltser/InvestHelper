import {
  Cell,
  Pie,
  PieChart,
  ResponsiveContainer,
  Tooltip,
} from "recharts";
import type { AllocationItem } from "../api";
import { CHART_COLORS, formatMoney, formatPercent } from "../utils";

interface Props {
  allocation: AllocationItem[];
  currency: string;
  compact?: boolean;
}

export function AssetAllocation({ allocation, currency, compact = false }: Props) {
  const chartData = allocation.map((item) => ({
    name: item.label,
    value: Number(item.amount),
    share: Number(item.share_percent),
  }));

  if (chartData.length === 0) {
    return (
      <section
        className={`card allocation-card${compact ? " allocation-card-compact" : ""}`}
      >
        <h2>Структура портфеля</h2>
        <div className="state-box">Нет данных для отображения</div>
      </section>
    );
  }

  return (
    <section
      className={`card allocation-card${compact ? " allocation-card-compact" : ""}`}
    >
      <h2>Структура портфеля</h2>
      <div className="chart-container">
        <ResponsiveContainer width="100%" height="100%">
          <PieChart>
            <Pie
              data={chartData}
              dataKey="value"
              nameKey="name"
              innerRadius="52%"
              outerRadius="78%"
              paddingAngle={2}
            >
            {chartData.map((_, index) => (
              <Cell
                key={index}
                fill={CHART_COLORS[index % CHART_COLORS.length]}
              />
            ))}
          </Pie>
          <Tooltip
            formatter={(value: number, _name, item) => [
              formatMoney(value, currency),
              `${item.payload.share.toFixed(2)}%`,
            ]}
          />
        </PieChart>
      </ResponsiveContainer>
      </div>
      <div className="legend">
        {allocation.map((item, index) => (
          <div className="legend-item" key={item.key}>
            <div className="legend-left">
              <span
                className="legend-dot"
                style={{
                  background: CHART_COLORS[index % CHART_COLORS.length],
                }}
              />
              <span>{item.label}</span>
            </div>
            <div className="legend-right">
              <div className="legend-percent">
                {formatPercent(item.share_percent)}
              </div>
              <div className="legend-amount">
                {formatMoney(item.amount, currency)}
              </div>
            </div>
          </div>
        ))}
      </div>
    </section>
  );
}
