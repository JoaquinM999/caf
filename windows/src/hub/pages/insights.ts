// Statistics: words, time saved, speed, dictations, the words of each day and
// the apps you dictate in. Port of FlowHubInsights.swift.

import { h, clear } from "../../views/dom";
import { t } from "../../i18n/i18n";
import { FlowBridge, type FlowStats, type Totals } from "../../core/flow";
import type { HubContext } from "../shell";
import { emptyState } from "../hero";
import { number, segmented, shortCount } from "../ui";

type Period = "week" | "month" | "all";

function duration(minutes: number): string {
  const m = Math.round(minutes);
  if (m >= 60) return t("{0} h {1}", { 0: Math.floor(m / 60), 1: String(m % 60).padStart(2, "0") });
  return t("{0} min", { 0: m });
}

export async function insightsPage(page: HTMLElement, ctx: HubContext) {
  const stats: FlowStats | null = await FlowBridge.stats();
  let cafStats: {
    total_conversations?: number;
    total_user_words?: number;
    total_caf_words?: number;
    total_seconds_talked?: number;
    tools_used?: Record<string, number>;
    daily?: Record<string, number>;
    memory_count?: number;
  } | null = null;

  try {
    const res = await fetch("http://127.0.0.1:8000/stats");
    if (res.ok) {
      const data = await res.json();
      cafStats = data.stats || {};
      if (cafStats) cafStats.memory_count = data.memory_count || 0;
    }
  } catch {}

  let period: Period = "month";
  const body = h("div", { style: "display:flex;flex-direction:column;gap:14px" });
  const picker = segmented<Period>([["week", t("Week")], ["month", t("Month")], ["all", t("All")]], period, (p) => {
    period = p;
    draw();
  });
  page.append(ctx.hero("insights", t("Statistics"), t("What you dictated, how fast, and where."), [picker]), body);

  function stat(labelText: string, value: string, sub: string | null) {
    const el = h("div", { class: "hub-stat" }, h("div", { class: "label", text: labelText }), h("b", { text: value }));
    if (sub) el.append(h("div", { class: "sub", text: sub }));
    return el;
  }

  function draw() {
    clear(body);
    const totals: Totals = stats?.[period] ?? { words: 0, seconds: 0, dictations: 0, wordsPerMinute: 0, minutesSaved: 0 };
    body.append(h("div", { class: "hub-stat-row" },
      stat(t("Words dictated"), shortCount(totals.words), null),
      stat(t("Time saved"), duration(totals.minutesSaved), t("vs typing at 45 words/min")),
      stat(t("Speed"), number(totals.wordsPerMinute), t("words/min")),
      stat(t("Dictations"), number(totals.dictations), null),
    ));

    // Words per day, the last 30 days (or 7).
    const days = (stats?.daily ?? []).slice(period === "week" ? -7 : -30);
    const max = Math.max(1, ...days.map(([, w]) => w));
    const bars = h("div", { class: "hub-bars" });
    for (const [key, words] of days) {
      const bar = h("i", { class: words === 0 ? "zero" : "", title: `${key} · ${number(words)}` });
      bar.style.height = `${Math.max(words === 0 ? 0 : 3, (words / max) * 100)}%`;
      bars.append(bar);
    }
    const axis = h("div", { class: "hub-axis" });
    days.forEach(([key], i) => {
      if (i % (period === "week" ? 1 : 5) === 0 || i === days.length - 1) axis.append(h("span", { text: String(Number(key.split("-")[2])) }));
    });
    const chart = h("div", { class: "hub-card" }, h("div", { class: "title", style: "font:700 14px var(--font)", text: t("Words per day") }), bars, axis);

    const apps = Object.entries(stats?.apps ?? {}).sort((a, b) => b[1] - a[1]).slice(0, 8);
    const total = apps.reduce((s, [, w]) => s + w, 0);
    const appsCard = h("div", { class: "hub-card" }, h("div", { class: "title", style: "font:700 14px var(--font)", text: t("Where you dictate") }));
    if (apps.length === 0) {
      appsCard.append(emptyState(t("Dictate in an app and it shows here."), "idle"));
    } else {
      for (const [name, words] of apps) {
        const share = total > 0 ? words / total : 0;
        appsCard.append(h("div", { class: "hub-app-bar" },
          h("div", { class: "top" }, h("b", { text: name, style: "font-weight:500" }), h("span", { text: `${Math.round(share * 100)} %` })),
          h("div", { class: "track" }, h("i", { style: `width:${Math.max(2, share * 100)}%` })),
        ));
      }
    }
    body.append(h("div", { class: "hub-chart-row" }, chart, appsCard));

    // ── Sección Caf: Asistente de Voz en Vivo ──────────────────────────────────
    const cafTotalConvs = cafStats?.total_conversations ?? 0;
    const cafWords = cafStats?.total_caf_words ?? 0;
    const userWords = cafStats?.total_user_words ?? 0;
    const memoryCount = cafStats?.memory_count ?? 0;
    const toolsUsed = cafStats?.tools_used ?? {};
    const totalTools = Object.values(toolsUsed).reduce((a, b) => a + Number(b), 0);

    const cafHeader = h("div", { style: "display:flex;align-items:center;justify-content:space-between;margin-top:10px;margin-bottom:-4px;" },
      h("div", { style: "font:700 15px var(--font);color:var(--ink);letter-spacing:-0.2px;", text: "Asistente de Voz (Caf)" }),
      h("span", { class: "hub-badge on", style: "font-size:11px;color:var(--hub-green);", text: "● Gemini Live" })
    );

    const cafStatsRow = h("div", { class: "hub-stat-row" },
      stat("Charlas con Caf", number(cafTotalConvs), "sesiones de diálogo"),
      stat("Palabras de Caf", shortCount(cafWords), `tú hablaste ${shortCount(userWords)} palabras`),
      stat("Acciones ejecutadas", number(totalTools), "Spotify, web, mails, etc."),
      stat("Recuerdos activos", number(memoryCount), "en memoria persistente")
    );

    const toolLabels: Record<string, string> = {
      spotify: "Control de Spotify",
      buscar_web: "Búsquedas web",
      preparar_email: "Mails redactados",
      recordar: "Memoria permanente",
      coucou_pills: "Pills de la Isla",
      abrir_programa: "Programas abiertos",
      otros: "Otras acciones"
    };

    const toolEntries = Object.entries(toolsUsed)
      .filter(([, count]) => Number(count) > 0)
      .sort((a, b) => Number(b[1]) - Number(a[1]));

    const toolsCard = h("div", { class: "hub-card" },
      h("div", { class: "title", style: "font:700 14px var(--font);margin-bottom:8px;", text: "Herramientas más usadas por Caf" })
    );

    if (toolEntries.length === 0) {
      toolsCard.append(emptyState("Habla con Caf o pídele acciones y aparecerán aquí.", "idle"));
    } else {
      for (const [cat, count] of toolEntries) {
        const share = totalTools > 0 ? Number(count) / totalTools : 0;
        const name = toolLabels[cat] || cat;
        toolsCard.append(h("div", { class: "hub-app-bar" },
          h("div", { class: "top" }, h("b", { text: name, style: "font-weight:500" }), h("span", { text: `${number(Number(count))} (${Math.round(share * 100)} %)` })),
          h("div", { class: "track" }, h("i", { style: `width:${Math.max(3, share * 100)}%;background:var(--hub-green);` }))
        ));
      }
    }

    body.append(cafHeader, cafStatsRow, toolsCard);
    body.append(h("div", { class: "hub-note", text: t("Counted on this computer, never sent anywhere.") }));
  }
  draw();
}
