import {
  plainEnglishLegendText,
  type PlainEnglishLegend,
} from "./plain-english-legend-client";

export type SelectedEvidenceLegendInput = {
  code: string | null | undefined;
  description?: string | null | undefined;
  observation?: string | null | undefined;
};

function fallbackText(value: string | null | undefined) {
  const text = value?.trim();
  return text ? text : null;
}

export function selectedEvidencePlainEnglish(
  lookup: Map<string, PlainEnglishLegend>,
  evidence: SelectedEvidenceLegendInput | null | undefined,
) {
  if (!evidence) return null;

  return (
    fallbackText(plainEnglishLegendText(lookup, { code: evidence.code, family: "evidence_code" })) ??
    fallbackText(plainEnglishLegendText(lookup, { code: evidence.code, family: "event_label" })) ??
    fallbackText(plainEnglishLegendText(lookup, { code: evidence.code })) ??
    fallbackText(evidence.description) ??
    fallbackText(evidence.observation)
  );
}
