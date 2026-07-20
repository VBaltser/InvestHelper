const CURRENCY_SYMBOLS: Record<string, string> = {
  rub: "₽",
  usd: "$",
  eur: "€",
  cny: "¥",
  hkd: "HK$",
};

export function currencySymbol(currency: string): string {
  return CURRENCY_SYMBOLS[currency.toLowerCase()] ?? currency.toUpperCase();
}

export function formatMoney(
  value: string | number,
  currency = "rub",
  signed = false,
): string {
  const amount = typeof value === "string" ? Number(value) : value;
  const prefix = signed && amount > 0 ? "+" : "";
  const formatted = new Intl.NumberFormat("ru-RU", {
    minimumFractionDigits: 2,
    maximumFractionDigits: 2,
  }).format(amount);
  return `${prefix}${formatted} ${currencySymbol(currency)}`;
}

export function purchaseReturnPercent(
  currentPrice: string | number,
  averagePrice: string | number,
): number | null {
  const current = Number(currentPrice);
  const average = Number(averagePrice);
  if (average <= 0) return null;
  return ((current - average) / average) * 100;
}

export function unrealizedYieldPercent(
  expectedYield: string | number,
  currentValue: string | number,
): number | null {
  const yieldAmount = Number(expectedYield);
  const value = Number(currentValue);
  const costBasis = value - yieldAmount;
  if (costBasis <= 0) return null;
  return (yieldAmount / costBasis) * 100;
}

export function formatPercent(value: string | number, signed = false): string {
  const amount = typeof value === "string" ? Number(value) : value;
  const prefix = signed && amount > 0 ? "+" : "";
  return `${prefix}${amount.toFixed(2)}%`;
}

export function formatQuantity(value: string | number): string {
  const amount = typeof value === "string" ? Number(value) : value;
  return new Intl.NumberFormat("ru-RU", {
    maximumFractionDigits: 4,
  }).format(amount);
}

export const CHART_COLORS = [
  "#4f8cff",
  "#34d399",
  "#f59e0b",
  "#f472b6",
  "#a78bfa",
  "#22d3ee",
  "#fb7185",
  "#84cc16",
];

const SECTOR_LABELS: Record<string, string> = {
  financial: "Финансы",
  consumer: "Потребительский",
  real_estate: "Недвижимость",
  materials: "Ресурсы",
  utilities: "Коммунальный",
  telecom: "Телекоммуникации",
  industrials: "Промышленность",
  other: "Другое",
  health_care: "Здравоохранение",
  it: "ИТ",
  energy: "Энергетика",
  municipal: "Муниципальный",
  government: "Государственный",
};

const RATING_BASE: Record<string, number> = {
  AAA: 22,
  AA: 20,
  A: 17,
  BBB: 14,
  BB: 11,
  B: 8,
  CCC: 5,
  CC: 3,
  C: 2,
  D: 1,
};

export function formatSector(sector: string): string {
  if (!sector) return "—";
  return SECTOR_LABELS[sector] ?? sector;
}

export function ratingSortKey(rating: string | null, forAsc = false): number {
  if (!rating) return forAsc ? 999 : -1;
  if (rating === "Гос.") return 100;

  const normalized = rating.toUpperCase().trim();
  const match = normalized.match(/^([A-Z]{1,3})([+-])?$/);
  if (!match) return forAsc ? 998 : 0;

  const [, base, modifier] = match;
  const baseScore = RATING_BASE[base];
  if (baseScore === undefined) return forAsc ? 998 : 0;

  if (modifier === "+") return baseScore + 1;
  if (modifier === "-") return baseScore - 1;
  return baseScore;
}

const RATING_SCORE_LABELS: Array<{ score: number; label: string }> = [
  { score: 100, label: "Гос." },
  { score: 22, label: "AAA" },
  { score: 21, label: "AA+" },
  { score: 20, label: "AA" },
  { score: 19, label: "AA-" },
  { score: 18, label: "A+" },
  { score: 17, label: "A" },
  { score: 16, label: "A-" },
  { score: 15, label: "BBB+" },
  { score: 14, label: "BBB" },
  { score: 13, label: "BBB-" },
  { score: 12, label: "BB+" },
  { score: 11, label: "BB" },
  { score: 10, label: "BB-" },
  { score: 9, label: "B+" },
  { score: 8, label: "B" },
  { score: 7, label: "B-" },
  { score: 6, label: "CCC+" },
  { score: 5, label: "CCC" },
  { score: 4, label: "CCC-" },
  { score: 3, label: "CC" },
  { score: 2, label: "C" },
  { score: 1, label: "D" },
];

export function scoreToRating(score: number): string {
  let closest = RATING_SCORE_LABELS[RATING_SCORE_LABELS.length - 1];
  let minDiff = Number.POSITIVE_INFINITY;
  for (const entry of RATING_SCORE_LABELS) {
    const diff = Math.abs(entry.score - score);
    if (diff < minDiff) {
      minDiff = diff;
      closest = entry;
    }
  }
  return closest.label;
}

export function averageCreditRating(
  items: Array<{ rating: string | null; weight: number }>,
): string | null {
  let totalWeight = 0;
  let totalScore = 0;

  for (const { rating, weight } of items) {
    if (!rating || weight <= 0) continue;
    const score = ratingSortKey(rating);
    if (score <= 0) continue;
    totalScore += score * weight;
    totalWeight += weight;
  }

  if (totalWeight <= 0) return null;
  return scoreToRating(totalScore / totalWeight);
}

export function weightedAverage(
  items: Array<{ value: number | null; weight: number }>,
): number | null {
  let totalWeight = 0;
  let totalValue = 0;

  for (const { value, weight } of items) {
    if (value === null || weight <= 0) continue;
    totalValue += value * weight;
    totalWeight += weight;
  }

  if (totalWeight <= 0) return null;
  return totalValue / totalWeight;
}

function pluralYears(n: number): string {
  const mod10 = n % 10;
  const mod100 = n % 100;
  if (mod10 === 1 && mod100 !== 11) return `${n} год`;
  if (mod10 >= 2 && mod10 <= 4 && (mod100 < 10 || mod100 >= 20)) {
    return `${n} года`;
  }
  return `${n} лет`;
}

function pluralMonths(n: number): string {
  const mod10 = n % 10;
  const mod100 = n % 100;
  if (mod10 === 1 && mod100 !== 11) return `${n} месяц`;
  if (mod10 >= 2 && mod10 <= 4 && (mod100 < 10 || mod100 >= 20)) {
    return `${n} месяца`;
  }
  return `${n} месяцев`;
}

export function formatYearsMonths(value: string | number | null): string {
  if (value === null || value === "") return "—";

  const totalMonths = Math.max(0, Math.round(Number(value) * 12));
  const years = Math.floor(totalMonths / 12);
  const months = totalMonths % 12;

  if (years === 0 && months === 0) return "0 месяцев";
  if (years === 0) return pluralMonths(months);
  if (months === 0) return pluralYears(years);
  return `${pluralYears(years)} ${pluralMonths(months)}`;
}
