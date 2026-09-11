"use client";

import { useEffect, useMemo, useState } from "react";
import styles from "./legends.module.css";

type PlainEnglishLegend = {
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

type ChartReadingCycleItem = {
  order: number;
  stage: string;
  family: string;
  plain_english: string;
};

type LegendRegistryPayload = {
  production_safe: boolean;
  chart_reading_cycle: ChartReadingCycleItem[];
  field_family_aliases: Record<string, string>;
  legends: PlainEnglishLegend[];
};

const API = process.env.NEXT_PUBLIC_API_URL ?? "http://127.0.0.1:8000";
const IMPORTANT_FIELDS = [
  "_outcome_label",
  "_review_reason",
  "_classify_cluster",
  "_classify_transition",
  "_case_type_for_transition",
];

function pretty(value: string | null | undefined) {
  return value ? value.replaceAll("_", " ").replace(/\b\w/g, (char) => char.toUpperCase()) : "—";
}

function sortLegends(legends: PlainEnglishLegend[]) {
  return legends.slice().sort((left, right) => {
    return (
      left.chart_reading_order - right.chart_reading_order ||
      left.family.localeCompare(right.family) ||
      left.frontend_label.localeCompare(right.frontend_label) ||
      left.code.localeCompare(right.code)
    );
  });
}

function groupByFamily(legends: PlainEnglishLegend[]) {
  return sortLegends(legends).reduce<Record<string, PlainEnglishLegend[]>>((groups, legend) => {
    groups[legend.family] = groups[legend.family] ?? [];
    groups[legend.family].push(legend);
    return groups;
  }, {});
}

async function fetchLegendRegistry(): Promise<LegendRegistryPayload> {
  const response = await fetch(`${API}/api/vsa/legends`);
  if (!response.ok) {
    throw new Error("Plain-English legend registry failed to load.");
  }
  return (await response.json()) as LegendRegistryPayload;
}

export default function PlainEnglishLegendsPage() {
  const [registry, setRegistry] = useState<LegendRegistryPayload | null>(null);
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    let cancelled = false;
    setLoading(true);
    setError("");

    fetchLegendRegistry()
      .then((payload) => {
        if (!cancelled) setRegistry(payload);
      })
      .catch((err) => {
        if (!cancelled) setError(err instanceof Error ? err.message : "Plain-English legend registry failed to load.");
      })
      .finally(() => {
        if (!cancelled) setLoading(false);
      });

    return () => {
      cancelled = true;
    };
  }, []);

  const legendsByFamily = useMemo(() => groupByFamily(registry?.legends ?? []), [registry]);
  const families = Object.keys(legendsByFamily);

  return (
    <main className={styles.shell}>
      <header className={styles.hero}>
        <a className={styles.backLink} href="/">← Back to ProVSA</a>
        <span className={styles.kicker}>Plain-English legend registry</span>
        <h1>Every internal code should have a trader-readable explanation.</h1>
        <p>
          This page consumes <code>/api/vsa/legends</code> and shows each lifecycle,
          outcome, cluster, transition, casebook, and review marker code beside its
          plain-English meaning.
        </p>
        <div className={styles.guardrails}>
          <span>Read-only frontend display</span>
          <span>No scanner activation</span>
          <span>No chart replay change</span>
          <span>No scoring/ranking change</span>
        </div>
      </header>

      {loading ? <section className={styles.status}>Loading legend explanations...</section> : null}
      {error ? <section className={styles.status} role="alert">{error}</section> : null}

      {registry ? (
        <>
          <section className={styles.panel} aria-label="Chronological chart reading cycle">
            <div className={styles.sectionHeading}>
              <span>Chronological reading cycle</span>
              <strong>{registry.production_safe ? "Production-safe" : "Review required"}</strong>
            </div>
            <div className={styles.cycleGrid}>
              {registry.chart_reading_cycle.map((item) => (
                <article className={styles.cycleCard} key={`${item.order}-${item.stage}`}>
                  <b>{item.order}</b>
                  <h2>{pretty(item.stage)}</h2>
                  <small>{pretty(item.family)}</small>
                  <p>{item.plain_english}</p>
                </article>
              ))}
            </div>
          </section>

          <section className={styles.panel} aria-label="Important internal field aliases">
            <div className={styles.sectionHeading}>
              <span>Fields called out for chart reading</span>
              <strong>Internal field → legend family</strong>
            </div>
            <div className={styles.aliasGrid}>
              {IMPORTANT_FIELDS.map((field) => (
                <div className={styles.aliasCard} key={field}>
                  <code>{field}</code>
                  <span>{pretty(registry.field_family_aliases[field])}</span>
                </div>
              ))}
            </div>
          </section>

          {families.map((family) => (
            <section className={styles.panel} key={family} aria-label={`${pretty(family)} legends`}>
              <div className={styles.sectionHeading}>
                <span>{pretty(family)}</span>
                <strong>{legendsByFamily[family].length} explanations</strong>
              </div>
              <div className={styles.legendList}>
                {legendsByFamily[family].map((legend) => (
                  <article className={styles.legendCard} key={`${legend.family}-${legend.code}`}>
                    <div className={styles.legendHeader}>
                      <div>
                        <h2>{legend.frontend_label}</h2>
                        <code>{legend.code}</code>
                      </div>
                      <span>{pretty(legend.chronological_stage)}</span>
                    </div>
                    <p>{legend.plain_english}</p>
                    <dl>
                      <div>
                        <dt>Chart reading role</dt>
                        <dd>{legend.chart_reading_role}</dd>
                      </div>
                      <div>
                        <dt>Example</dt>
                        <dd>{legend.example_read}</dd>
                      </div>
                      <div>
                        <dt>User action</dt>
                        <dd>{legend.user_action}</dd>
                      </div>
                    </dl>
                    <div className={styles.badges}>
                      <span>{legend.audit_only ? "Audit-only" : "Production code"}</span>
                      <span>{legend.production_safe ? "Production-safe" : "Not production-safe"}</span>
                    </div>
                  </article>
                ))}
              </div>
            </section>
          ))}
        </>
      ) : null}
    </main>
  );
}
