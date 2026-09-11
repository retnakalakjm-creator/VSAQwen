export type PlainEnglishLegend = {
  code: string;
  family: string;
  frontend_label: string;
  plain_english: string;
  chronological_stage: string;
  chart_reading_order: number;
  chart_reading_role: string;
  example_read: string;
  user_action: string;
  audit_only: boolean;
  production_safe: boolean;
};

export type ChartReadingCycleItem = {
  order: number;
  stage: string;
  family: string;
  plain_english: string;
};

export type LegendRegistryPayload = {
  production_safe: boolean;
  chart_reading_cycle: ChartReadingCycleItem[];
  field_family_aliases: Record<string, string>;
  legends: PlainEnglishLegend[];
};

export type LegendLookupKey = {
  code: string | null | undefined;
  family?: string | null | undefined;
};

export function prettyLegendValue(value: string | null | undefined) {
  return value
    ? value.replaceAll("_", " ").replace(/\b\w/g, (char) => char.toUpperCase())
    : "—";
}

export function sortPlainEnglishLegends(legends: PlainEnglishLegend[]) {
  return legends.slice().sort((left, right) => {
    return (
      left.chart_reading_order - right.chart_reading_order ||
      left.family.localeCompare(right.family) ||
      left.frontend_label.localeCompare(right.frontend_label) ||
      left.code.localeCompare(right.code)
    );
  });
}

export function groupPlainEnglishLegendsByFamily(legends: PlainEnglishLegend[]) {
  return sortPlainEnglishLegends(legends).reduce<Record<string, PlainEnglishLegend[]>>(
    (groups, legend) => {
      groups[legend.family] = groups[legend.family] ?? [];
      groups[legend.family].push(legend);
      return groups;
    },
    {},
  );
}

export function buildPlainEnglishLegendLookup(legends: PlainEnglishLegend[]) {
  return new Map(legends.map((legend) => [`${legend.family}:${legend.code}`, legend]));
}

export function findPlainEnglishLegend(
  lookup: Map<string, PlainEnglishLegend>,
  key: LegendLookupKey,
) {
  const code = key.code?.trim();
  if (!code) return null;

  const family = key.family?.trim();
  if (family) return lookup.get(`${family}:${code}`) ?? null;

  for (const lookupKey of [
    `evidence_code:${code}`,
    `event_label:${code}`,
    `review_marker:${code}`,
    `lifecycle:${code}`,
    `outcome_label:${code}`,
    `cluster:${code}`,
    `transition:${code}`,
    `case_type:${code}`,
    `review_reason:${code}`,
  ]) {
    const legend = lookup.get(lookupKey);
    if (legend) return legend;
  }

  return null;
}

export function plainEnglishLegendText(
  lookup: Map<string, PlainEnglishLegend>,
  key: LegendLookupKey,
) {
  const legend = findPlainEnglishLegend(lookup, key);
  return legend?.plain_english ?? null;
}
