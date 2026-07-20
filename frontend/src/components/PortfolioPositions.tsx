import type { BondPortfolioMetric, Position } from "../api";
import { PositionGroup } from "./PositionGroup";

function isRubBond(position: Position): boolean {
  return position.nominal_currency.toLowerCase() === "rub";
}

const POSITION_GROUPS: Array<{
  key: string;
  title: string;
  types: string[];
  filter?: (position: Position) => boolean;
  variant?: "default" | "bonds";
}> = [
  { key: "shares", title: "Акции", types: ["share"] },
  {
    key: "bonds",
    title: "Облигации",
    types: ["bond"],
    filter: (position) => isRubBond(position),
    variant: "bonds",
  },
  {
    key: "bonds_fx",
    title: "Валютные облигации",
    types: ["bond"],
    filter: (position) => !isRubBond(position),
    variant: "bonds",
  },
  { key: "etf", title: "Фонды", types: ["etf"] },
  { key: "currency", title: "Валюта", types: ["currency"] },
  {
    key: "other",
    title: "Прочее",
    types: ["futures", "option", "sp", "commodity"],
  },
];

interface Props {
  positions: Position[];
  currency: string;
  bondMetrics?: Record<string, BondPortfolioMetric>;
  bondMetricsLoading?: boolean;
}

function withBondMetrics(
  positions: Position[],
  bondMetrics: Record<string, BondPortfolioMetric>,
): Position[] {
  return positions.map((position) => {
    const metric = bondMetrics[position.figi];
    if (!metric) return position;
    return {
      ...position,
      current_yield_to_maturity: metric.current_yield_to_maturity ?? null,
      yield_to_maturity: metric.yield_to_maturity ?? null,
      credit_rating: metric.credit_rating ?? null,
      maturity_income_rub: metric.maturity_income_rub ?? null,
    };
  });
}

export function PortfolioPositions({
  positions,
  currency,
  bondMetrics = {},
  bondMetricsLoading = false,
}: Props) {
  if (positions.length === 0) {
    return (
      <section className="card positions-card">
        <h2>Позиции</h2>
        <div className="state-box">Портфель пуст</div>
      </section>
    );
  }

  const enrichedPositions = withBondMetrics(positions, bondMetrics);
  const knownTypes = new Set(POSITION_GROUPS.flatMap((group) => group.types));
  const grouped = POSITION_GROUPS.map((group) => ({
    ...group,
    positions: enrichedPositions.filter(
      (position) =>
        group.types.includes(position.instrument_type) &&
        (!group.filter || group.filter(position)),
    ),
  }));

  const unknown = enrichedPositions.filter(
    (position) => !knownTypes.has(position.instrument_type),
  );
  if (unknown.length > 0) {
    const other = grouped.find((group) => group.key === "other");
    if (other) {
      other.positions = [...other.positions, ...unknown];
    }
  }

  return (
    <div className="portfolio-positions">
      {grouped.map((group) => (
        <PositionGroup
          key={group.key}
          title={group.title}
          positions={group.positions}
          currency={currency}
          variant={group.variant ?? "default"}
          bondMetricsLoading={
            group.variant === "bonds" ? bondMetricsLoading : false
          }
        />
      ))}
    </div>
  );
}
