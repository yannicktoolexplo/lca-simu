// Input contains only material approved for this audience by render.py.
const fs = require("node:fs");
let PptxGenJS;
try {
  PptxGenJS = require("pptxgenjs");
} catch (error) {
  console.error("Export PowerPoint : installer la dépendance avec npm ci --prefix tools/portfolio.");
  process.exit(1);
}

const [, , jsonPath, outputPath] = process.argv;
const model = JSON.parse(fs.readFileSync(jsonPath, "utf8"));
const pptx = new PptxGenJS();
pptx.layout = "LAYOUT_WIDE";
pptx.author = "Équipe de simulation";
pptx.title = model.profile.title;
pptx.subject = model.scope;
pptx.lang = "fr-FR";
pptx.theme = { headFontFace: "Aptos Display", bodyFontFace: "Aptos", lang: "fr-FR" };
const ink = "15364D", teal = "00796F", gray = "4B6170";
const colors = ["137D83", "A65029", "5C5F9A", "445E75"];
const page = { x: 0.82, w: 11.66 };

function chunks(values, length) {
  return Array.from({length: Math.ceil(values.length / length)}, (_, i) =>
    values.slice(i * length, (i + 1) * length));
}

function label(slide, value, x, y, w, h, options = {}) {
  slide.addText(value, {
    x, y, w, h, fontFace: "Aptos", fontSize: 20, color: ink,
    margin: 0, valign: "mid", breakLine: false, fit: "shrink", ...options,
  });
}

// Long wording stays available verbatim in the notes and meeting brief.
function excerpt(value, limit) {
  if (value.length <= limit) return value;
  const start = value.slice(0, limit - 1);
  const end = start.lastIndexOf(" ");
  return start.slice(0, end > limit * 0.65 ? end : start.length).trimEnd() + "…";
}

function slideWithTitle(section, title) {
  const slide = pptx.addSlide();
  slide.background = { color: "FFFFFF" };
  label(slide, section, page.x, 0.38, 11.6, 0.27,
    { fontSize: 15, color: teal, bold: true });
  label(slide, excerpt(title, 114), page.x, 0.83, page.w, 0.92,
    { fontSize: 32, fontFace: "Aptos Display", bold: true });
  return slide;
}

function note(slide, lines) {
  slide.addNotes(lines.filter(Boolean).join("\n\n"));
}

function notesFor(cap) {
  return [cap.name + " · " + cap.status,
    "Décision. " + cap.decision, "Méthode. " + cap.method, "Constat. " + cap.finding,
    "Limite. " + cap.limit, "Prochain essai. " + cap.next_test,
    ...(cap.evidence.length ? ["Pièces du dépôt", ...cap.evidence] : [])];
}

function summaryBlock(slide, heading, content, x, y, width, height) {
  label(slide, heading, x, y, width, 0.27, { fontSize: 15, bold: true, color: teal });
  label(slide, excerpt(content, width > 8 ? 245 : 162), x, y + 0.43, width, height,
    { fontSize: 21, valign: "top" });
}

const cover = pptx.addSlide();
cover.background = { color: ink };
label(cover, model.scope, 0.84, 0.75, 11.5, 0.48, { fontSize: 18, color: "90DDC8" });
label(cover, model.profile.title, 0.81, 1.72, 11.5, 2.20,
  { fontSize: 52, color: "FFFFFF", bold: true, fontFace: "Aptos Display" });
label(cover, excerpt(model.question, 225), 0.85, 4.43, 10.9, 1.42,
  { fontSize: 25, color: "DCE8E9", valign: "top" });
note(cover, [model.question, ...model.profile.agenda]);

const commonChart = {
  chartColors: colors, showTitle: false, showLegend: true, legendPos: "b",
  legendFontFace: "Aptos", legendFontSize: 12, legendColor: ink,
  catAxisLabelFontFace: "Aptos", catAxisLabelFontSize: 13, catAxisLabelColor: ink,
  valAxisLabelFontFace: "Aptos", valAxisLabelFontSize: 12, valAxisLabelColor: gray,
  valGridLine: { color: "D8E2E4", size: 0.8, style: "solid" }, showBorder: false,
  showCatName: false, showValue: false, showCatNameLegendKeys: false,
};
const families = [...new Set(model.caps.map(c => c.family))].sort((a,b) => a.localeCompare(b,"fr"));
const totals = families.map(f => model.caps.filter(c => c.family === f).length);
for (const group of chunks(families, 6)) {
  const slide = slideWithTitle("Panorama des capacités", "Quelles familles de méthodes a-t-on examinées ?");
  const series = model.statuses.map(name => ({
    name, labels: group,
    values: group.map(f => model.caps.filter(c => c.family === f && c.status === name).length)
  }));
  const largest = Math.max(...totals);
  slide.addChart(pptx.ChartType.bar, series, {
    ...commonChart, x: 0.9, y: 1.78, w: 11.5, h: 4.36, barDir: "bar",
    barGrouping: "stacked", catAxisLabelFontSize: 14, gapSizePct: 55,
    valAxisMinVal: 0, valAxisMaxVal: largest, valAxisMajorUnit: Math.max(1, Math.ceil(largest / 5)),
    showValAxisTitle: true, valAxisTitle: "Nombre de capacités relues", valAxisTitleFontSize: 12,
    chartColors: ["C9D6DC", "8499A9", "41798D", "00796F"],
  });
  label(slide, "Chaque capacité compte une fois, au niveau de preuve retenu pour ce dossier.",
        page.x, 6.28, page.w, 0.65, { color: gray, fontSize: 17 });
  note(slide, ["Une fiche documentée décrit la méthode. Une fiche implémentée renvoie à son code. " +
    "Un résultat archivé repose sur une exécution conservée. Un résultat reproduit a fait l’objet d’un rejeu vérifié.",
    ...group.map(f => f + " : " + model.caps.filter(c => c.family === f).map(c => c.name).join(", "))]);
}

for (const cap of model.caps) {
  const s = slideWithTitle(cap.family + "  /  " + cap.status, cap.name);
  const fields = model.audience === "science" ? ["method", "decision"] : ["decision", "method"];
  summaryBlock(s, model.profile.primary, cap[fields[0]], page.x, 1.95, 5.52, 1.17);
  summaryBlock(s, model.profile.secondary, cap[fields[1]], 6.98, 1.95, 5.48, 1.17);
  label(s, "Ce que montre la pièce examinée", page.x, 3.95, page.w, 0.3,
    { fontSize: 16, color: teal, bold: true });
  label(s, excerpt(cap.finding, 245), page.x, 4.42, page.w, 1.18,
    { fontSize: 26, bold: true, valign: "top" });
  label(s, "Limite. " + excerpt(cap.limit, 191), page.x, 6.00, page.w, 0.88,
    { fontSize: 17, color: gray, valign: "top" });
  note(s, notesFor(cap));

  const v = cap.visual;
  if (!v) continue;
  if (v.kind === "image") {
    const figure = slideWithTitle(cap.name + "  /  " + cap.status, v.title);
    const scale = Math.min(page.w / v.width, 3.95 / v.height);
    const w = v.width * scale, h = v.height * scale;
    figure.addImage({data: "image/png;base64," + v.data, x: page.x + (page.w - w) / 2,
      y: 1.78 + (3.95 - h) / 2, w, h, altText: v.title});
    label(figure, excerpt(v.caption, 235), page.x, 5.92, page.w, 0.68, {fontSize: 18, bold: true});
    label(figure, "Limite. " + excerpt(cap.limit, 185), page.x, 6.65, page.w, 0.53,
      {color: gray, fontSize: 15});
    note(figure, [v.title, v.caption, ...notesFor(cap)]);
    continue;
  }
  const ranges = v.kind === "bar" ? chunks(v.categories, 8) : [v.categories];
  let min = Infinity, max = -Infinity;
  for (const series of v.series) {
    for (const y of series.values) {
      min = Math.min(min, y); max = Math.max(max, y);
    }
  }
  let first = 0;
  for (const labels of ranges) {
    for (const part of chunks(v.series, 4)) {
      const series = part.map(row => ({
        name: row.name, labels, values: row.values.slice(first, first + labels.length),
      }));
      const chart = slideWithTitle(cap.name + "  /  " + cap.status, v.title);
      const options = { ...commonChart, x: 0.83, y: 1.8, w: 11.66, h: 3.96,
        chartColors: part.length === 1 ? [colors[0]] : colors,
        barDir: "col", barGrouping: "clustered", showCatAxisTitle: true, catAxisTitle: v.x_label,
        catAxisTitleFontSize: 12, showValAxisTitle: true, valAxisTitle: v.unit, valAxisTitleFontSize: 12,
        catAxisLabelFrequency: String(Math.max(1, Math.ceil(labels.length / 9))),
        lineDataSymbol: labels.length > 40 ? "none" : "circle", lineDataSymbolSize: 5, lineSize: 2.4 };
      if (v.kind === "bar") {
        // Bar length encodes magnitude; its baseline must include zero.
        if (min >= 0) options.valAxisMinVal = 0;
        if (max <= 0) options.valAxisMaxVal = 0;
        options.showValue = labels.length <= 6 && part.length <= 3;
        options.dataLabelPosition = "outEnd";
        options.dataLabelFormatCode = "0.##";
      }
      if (ranges.length > 1 || v.series.length > 4) {
        options.valAxisMinVal = Math.min(0, min);
        options.valAxisMaxVal = Math.max(0, max);
        if (options.valAxisMaxVal === options.valAxisMinVal) options.valAxisMaxVal += 1;
      }
      chart.addChart(v.kind === "bar" ? pptx.ChartType.bar : pptx.ChartType.line, series, options);
      label(chart, excerpt(v.caption, 235), page.x, 5.92, page.w, 0.68, { fontSize: 18, bold: true });
      label(chart, "Limite. " + excerpt(cap.limit, 185), page.x, 6.65, page.w, 0.53,
        { color: gray, fontSize: 15 });
      note(chart, [v.title, v.caption, "Abscisse : " + v.x_label + ". Unité : " + v.unit, ...notesFor(cap)]);
    }
    first += labels.length;
  }
}

for (const group of chunks(model.gaps, 2)) {
  const slide = slideWithTitle("Suite des travaux", "Quelles lacunes faut-il lever ?");
  group.forEach((g, i) => {
    const y = 2.0 + 2.45 * i;
    label(slide, excerpt(g.title, 95), page.x, y, page.w, 0.54, { fontSize: 24, bold: true });
    label(slide, "Priorité " + g.priority + ". " + excerpt(g.impact, 175), page.x, y + 0.62,
      page.w, 0.64, { color: gray, fontSize: 17 });
    label(slide, "Essai proposé. " + excerpt(g.test, 165), page.x, y + 1.35,
      page.w, 0.7, { fontSize: 20, color: teal });
  });
  note(slide, group.map(g => [g.title, g.priority, g.impact, g.test].join("\n")));
}

const last = slideWithTitle("Discussion", model.profile.closing);
model.profile.questions.forEach((q, i) =>
  label(last, q, page.x, 2.05 + 1.18 * i, page.w, 0.81, { fontSize: 25 }));
label(last, "À consigner en séance : essai retenu, critère de réussite, responsable et échéance.",
  page.x, 6.21, page.w, 0.65, { fontSize: 18, color: teal, bold: true });
note(last, [...model.profile.questions, ...model.caps.map(c => c.name + " : " + c.next_test)]);
pptx.writeFile({fileName: outputPath}).catch(error => { console.error(error); process.exitCode = 1; });
