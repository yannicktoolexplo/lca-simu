// This stage receives only the material selected for the audience by render.py.
// The official Scalian masters supply the cover, page furniture, rules and logos.
const fs = require("node:fs");
let PptxGenJS;
try {
  PptxGenJS = require("pptxgenjs");
} catch {
  console.error("Pour produire le PowerPoint, exécuter npm ci --prefix tools/portfolio.");
  process.exit(1);
}

const [, , jsonPath, outputPath] = process.argv;
const model = JSON.parse(fs.readFileSync(jsonPath, "utf8"));
const pptx = new PptxGenJS();
pptx.layout = "LAYOUT_WIDE";
pptx.author = "Scalian";
pptx.title = model.profile.title;
pptx.subject = model.scope;
pptx.lang = "fr-FR";
pptx.theme = { headFontFace: "Aptos", bodyFontFace: "Aptos Light", lang: "fr-FR" };
const palette = {
  black: "000000", purple: "4B2882", dark: "2A164A", lilac: "CDBBDC",
  gray: "66616D", rule: "AEADBB", light: "F2EFF5", white: "FFFFFF",
};
const seriesColors = [palette.purple, "827889", palette.dark, "A48DB7"];
const X = 0.57, W = 12.20;
const graphic = { x: X, y: 1.56, w: 8.03, h: 4.55 };
const full = { x: X, y: 1.56, w: W, h: 4.43 };

function chunks(items, n) {
  return Array.from({length: Math.ceil(items.length / n)}, (_, i) => items.slice(i * n, (i + 1) * n));
}

function text(slide, value, x, y, w, h, options = {}) {
  slide.addText(value, {
    x, y, w, h, margin: 0, fontFace: "Aptos Light", fontSize: 17,
    color: palette.black, fit: "shrink", valign: "mid", paraSpaceAfterPt: 0, ...options,
  });
}

function line(slide, x, y, w, h, properties = {}) {
  slide.addShape(pptx.ShapeType.line, { x, y, w, h,
    line: { color: palette.rule, width: 0.7, ...properties } });
}

function page(title, subtitle) {
  const slide = pptx.addSlide();
  text(slide, title, X, 0.30, 11.45, 0.58, {
    fontFace: "Aptos", fontSize: title.length < 47 ? 32 : title.length < 71 ? 28 : 25,
  });
  text(slide, subtitle, X, 0.91, W, 0.34, { fontFace: "Aptos", fontSize: 15, color: palette.purple });
  return slide;
}

function note(slide, lines) {
  slide.addNotes(lines.filter(Boolean).join("\n\n"));
}

function sourceNotes(cap) {
  return [cap.name + " · " + cap.status, "Décision. " + cap.decision,
    "Méthode. " + cap.method, "Constat. " + cap.finding, "Limite. " + cap.limit,
    "Essai proposé. " + cap.next_test,
    ...(cap.evidence.length ? ["Pièces du dépôt", ...cap.evidence] : [])];
}

function observation(slide, heading, content, x, y, w, h, fontSize = 17) {
  text(slide, heading, x, y, w, 0.29, {
    fontFace: "Aptos", fontSize: 14, color: palette.purple, bold: true,
  });
  text(slide, content, x, y + 0.39, w, h - 0.39, { fontSize, valign: "top" });
}

function readingColumn(slide, primary, limit) {
  line(slide, 8.85, 1.65, 0, 4.25, { color: palette.lilac, width: 1.1 });
  observation(slide, "Ce que montre le résultat", primary, 9.12, 1.73, 3.58, 2.09, 18);
  observation(slide, "Portée du résultat", limit, 9.12, 4.00, 3.58, 1.97, 15.5);
}

function caption(slide, value) {
  text(slide, value, X, 6.25, W, 0.67, {
    fontSize: 15, color: palette.dark, valign: "mid",
  });
}

function table(slide, columns, rows, area, widths, fontSize = 15) {
  const lengths = columns.map((c, i) => {
    const cells = [c, ...rows.map(r => r[i])].map(t => t.length);
    return Math.max(9, Math.sqrt(Math.max(...cells)) * 4);
  });
  const weights = widths || lengths;
  const total = weights.reduce((a, b) => a + b, 0);
  const header = columns.map(c => ({ text: c, options: {
    fontFace: "Aptos", bold: true, color: palette.white, fill: { color: palette.purple },
  }}));
  const body = rows.map((r, i) => r.map((c, j) => ({ text: c, options: {
    fontFace: j === 0 ? "Aptos" : "Aptos Light", bold: j === 0,
    fill: { color: i % 2 === 0 ? palette.light : palette.white },
  }})));
  slide.addTable([header, ...body], {
    ...area, colW: weights.map(v => v / total * area.w), autoPage: false,
    margin: [0.07, 0.12, 0.07, 0.12], valign: "middle", fontSize, color: palette.black,
    border: { type: "solid", pt: 0.8, color: palette.white }, paraSpaceAfterPt: 0,
  });
}

const chartStyle = {
  chartColors: seriesColors, showTitle: false, showLegend: true, legendPos: "b",
  legendFontFace: "Aptos", legendFontSize: 12, legendColor: palette.black,
  catAxisLabelFontFace: "Aptos", catAxisLabelFontSize: 12, catAxisLabelColor: palette.black,
  valAxisLabelFontFace: "Aptos", valAxisLabelFontSize: 11, valAxisLabelColor: palette.black,
  valGridLine: { color: "E5E1E9", size: 0.7, style: "solid" },
  showBorder: false, showValue: false, showCatName: false, showCatNameLegendKeys: false,
  valAxisTitleFontFace: "Aptos", catAxisTitleFontFace: "Aptos",
  valAxisTitleFontSize: 12, catAxisTitleFontSize: 12,
};

function chartPanels(v) {
  const batches = v.kind === "bar" ? chunks(v.categories, 7) : [v.categories];
  const panels = [];
  let first = 0;
  for (const labels of batches) {
    for (const lines of chunks(v.series, 4)) {
      panels.push({ labels, series: lines.map(s => ({
        name: s.name, labels, values: s.values.slice(first, first + labels.length),
      })) });
    }
    first += labels.length;
  }
  return panels;
}

function drawChart(slide, v, panel, paginate) {
  const { labels, series } = panel;
  const isBar = v.kind === "bar";
  const options = {
    ...chartStyle, ...graphic, chartColors: series.length === 1 ? [palette.purple] : seriesColors,
    barDir: "col", barGrouping: "clustered",
    showCatAxisTitle: true, catAxisTitle: v.x_label, showValAxisTitle: true, valAxisTitle: v.unit,
    showLegend: series.length > 1, catAxisLabelFrequency: Math.max(1, Math.ceil(labels.length / 8)),
    lineSize: 2.7, lineDataSymbol: labels.length > 18 ? "none" : "circle", lineDataSymbolSize: 5,
    showValue: isBar && labels.length <= 6 && series.length <= 3, dataLabelPosition: "outEnd",
    dataLabelFormatCode: "0.##", dataLabelFormatBold: true, dataLabelFormatFontSize: 13,
  };
  const values = v.series.flatMap(s => s.values);
  const min = values.reduce((a, b) => Math.min(a,b), 0);
  const max = values.reduce((a, b) => Math.max(a,b), 0);
  if (isBar || paginate) {
    options.valAxisMinVal = min;
    if (max === 0 || paginate) options.valAxisMaxVal = max === min ? min + 1 : max;
    if (v.unit === "%" && min >= 0 && max > 75 && max <= 100) options.valAxisMaxVal = 100;
  }
  const xValues = labels.map(label => label.trim() === "" ? NaN : Number(label));
  if (!isBar && labels.length > 12 && xValues.every((x,i) => Number.isFinite(x) && (i === 0 || x > xValues[i - 1]))) {
    const span = xValues[xValues.length - 1] - xValues[0];
    const magnitude = 10 ** Math.floor(Math.log10(span / 8));
    const interval = [1,2,5,10].find(n => n * magnitude >= span / 8) * magnitude;
    slide.addChart(pptx.ChartType.scatter, [
      {name: v.x_label, values: xValues}, ...series.map(r => ({name:r.name, values:r.values})),
    ], {...options, catAxisMinVal:xValues[0], catAxisMaxVal:xValues[xValues.length - 1],
      catAxisMajorUnit:interval, lineDataSymbol:"none", showLegend:series.length > 1});
  } else if (!isBar && series.length > 1) {
    const symbols = ["circle", "diamond", "triangle", "square"];
    const dashes = ["solid", "dash", "lgDashDot", "dot"];
    const traces = series.map((row, i) => ({ type: pptx.ChartType.line, data: [row],
      options: { chartColors: [seriesColors[i]], lineDash: dashes[i], lineSize: 2.5,
        lineDataSymbol: labels.length > 18 ? "none" : symbols[i], lineDataSymbolSize: 6 } }));
    slide.addChart(traces, options);
  } else {
    slide.addChart(isBar ? pptx.ChartType.bar : pptx.ChartType.line, series, options);
  }
}

// Editable vector envelope. Constructing the polygon from both quantiles
// also handles intervals that cross zero without stacking signed areas.
function drawBand(slide, v) {
  const [lo, mid, hi] = v.series;
  const n = v.categories.length;
  const rawMin = lo.values.reduce((a, b) => Math.min(a, b), Infinity);
  const rawMax = hi.values.reduce((a, b) => Math.max(a, b), -Infinity);
  const rawStep = Math.max((rawMax - rawMin) / 4, Math.abs(rawMax) * 0.01, 1e-9);
  const mag = 10 ** Math.floor(Math.log10(rawStep));
  const step = [1, 2, 2.5, 5, 10].find(i => i * mag >= rawStep) * mag;
  const min = Math.floor(rawMin / step) * step;
  const max = Math.max(Math.ceil(rawMax / step) * step, min + step);
  const a = { x: 1.45, y: 2.05, w: 6.85, h: 2.90 };
  const points = ys => ys.map((y, i) => ({ x: a.w * i / (n - 1), y: a.h * (max - y) / (max - min) }));
  text(slide, v.unit, X, 1.56, 7.5, 0.33, { fontSize: 14, fontFace: "Aptos" });
  const formatter = new Intl.NumberFormat("fr-FR", {maximumFractionDigits: Math.min(12, Math.max(0, 1 - Math.floor(Math.log10(step))))});
  for (let k = 0; k <= Math.round((max - min) / step); k++) {
    const t = min + k * step, y = a.y + a.h * (max - t) / (max - min);
    text(slide, formatter.format(t), X, y - 0.12, a.x - X - 0.12, 0.23, {align: "right", fontSize: 11});
    line(slide, a.x, y, a.w, 0, {color: "E0DAE7"});
  }
  slide.addShape(pptx.ShapeType.custGeom, { ...a,
    points: [...points(hi.values), ...points(lo.values).reverse(), {close: true}],
    fill: {color: palette.lilac, transparency: 12}, line: {color: palette.white, transparency: 100},
  });
  slide.addShape(pptx.ShapeType.custGeom, { ...a, points: points(mid.values),
    fill: {color: palette.white, transparency: 100}, line: {color: palette.purple, width: 2.2},
  });
  const labels = Math.min(6, n);
  for (let i = 0; i < labels; i++) {
    const index = Math.round(i * (n - 1) / (labels - 1));
    const x = a.x + a.w * index / (n - 1);
    text(slide, v.categories[index], x - 0.43, 5.01, 0.86, 0.27, {fontSize: 11, align: "center"});
  }
  text(slide, v.x_label, a.x, 5.32, a.w, 0.27, {fontSize: 13, align: "center"});
  slide.addShape(pptx.ShapeType.rect, {x: 1.62, y: 5.79, w: 0.26, h: 0.13,
    fill: {color: palette.lilac}, line: {color: palette.white, transparency: 100}});
  text(slide, lo.name + " – " + hi.name, 1.98, 5.67, 3.10, 0.37, {fontSize: 12});
  line(slide, 5.23, 5.85, 0.27, 0, {color: palette.purple, width: 2});
  text(slide, mid.name, 5.63, 5.67, 2.54, 0.37, {fontSize: 12});
}

function drawFlow(slide, steps, start) {
  const gap = 0.33;
  const sw = (W - (steps.length - 1) * gap) / steps.length;
  steps.forEach((s, i) => {
    const x = X + i * (sw + gap);
    text(slide, String(start + i + 1).padStart(2, "0"), x, 1.67, sw, 0.36,
      {fontFace: "Aptos", fontSize: 19, bold: true, color: palette.purple});
    line(slide, x, 2.19, sw - 0.04, 0, {color: palette.lilac, width: 2.3});
    if (i < steps.length - 1) line(slide, x + sw - 0.02, 2.19, 0.27, 0,
      {color: palette.purple, width: 1.8, endArrowType: "triangle"});
    text(slide, s.label, x, 2.42, sw, 0.82, {fontFace: "Aptos", fontSize: 20, bold: true, valign: "top"});
    text(slide, s.detail, x, 3.35, sw, 1.80, {fontSize: 16, valign: "top"});
  });
}

function exhibitPages(cap, v) {
  const finding = v.observation || cap.finding;
  const limit = v.limit || cap.limit;
  const sub = (v.title === cap.name ? cap.family : cap.name) + "  ·  " + (v.status || cap.status);
  const newPage = () => page(v.title, sub);
  const notes = [v.title, v.caption, "Lecture de la figure. " + finding, "Portée. " + limit, ...sourceNotes(cap)];
  if (v.kind === "image") {
    const s = newPage();
    const imageHeight = 4.10;
    const scale = Math.min(full.w / v.width, imageHeight / v.height);
    const w = scale * v.width, h = scale * v.height;
    s.addImage({data: "image/png;base64," + v.data, x: X + (W-w)/2, y: full.y + (imageHeight-h)/2, w, h, altText:v.title});
    text(s, v.caption, X, 5.71, W, 0.55, {fontSize: 14.5, color: palette.gray});
    caption(s, finding);
    note(s, notes);
  } else if (v.kind === "flow") {
    let start = 0;
    for (const group of chunks(v.steps, 5)) {
      const s = newPage();
      drawFlow(s, group, start);
      text(s, v.caption, X, 5.36, W, 0.64, {fontFace: "Aptos", fontSize: 18, color: palette.dark});
      caption(s, finding);
      note(s, [...group.map(t => t.label + ". " + t.detail), ...notes]);
      start += group.length;
    }
  } else if (v.kind === "table") {
    for (const group of chunks(v.rows, 5)) {
      const s = newPage();
      table(s, v.columns, group, {x: X, y: 1.66, w: W, h: 3.96}, null,
        v.columns.length > 4 ? 13.5 : 16);
      text(s, v.caption, X, 5.73, W, 0.52, {fontSize: 14.5, color: palette.gray});
      caption(s, finding);
      note(s, [v.columns.join(" / "), ...group.map(r => r.join(" / ")), ...notes]);
    }
  } else {
    const panels = v.kind === "band" ? [null] : chartPanels(v);
    for (const panel of panels) {
      const s = newPage();
      if (panel) drawChart(s, v, panel, panels.length > 1); else drawBand(s, v);
      readingColumn(s, finding, limit);
      caption(s, v.caption);
      note(s, [v.x_label + " · " + v.unit, ...notes]);
    }
  }
}

const cover = pptx.addSlide();
text(cover, model.profile.title, 0.69, 1.45, 11.21, 1.8, {
  fontFace: "Aptos", fontSize: 48, color: palette.white, bold: true,
});
text(cover, model.question, 0.68, 5.37, 11.50, 0.90, {fontFace: "Aptos", fontSize: 25});
text(cover, model.scope, 0.68, 6.72, 8.25, 0.31, {fontFace: "Aptos", fontSize: 14, color: palette.dark});
note(cover, [model.question, ...model.profile.agenda]);

const agenda = model.profile.agenda.map((stage, i) => [["5 min", "15 min", "10 min"][i], stage]);
if (model.caps.length > 5) {
  const s = page("Où en sont les méthodes examinées ?", model.caps.length + " capacités retenues pour cette revue");
  const counts = model.statuses.map(status => model.caps.filter(c => c.status === status).length);
  s.addChart(pptx.ChartType.bar, [{name: "Fiches", labels: model.statuses, values: counts}], {
    ...chartStyle, x:X, y:1.78, w:6.02, h:4.38, barDir:"bar", barGrouping:"clustered",
    chartColors:[palette.purple], showLegend:false, showValue:true, dataLabelPosition:"outEnd",
    dataLabelFormatFontSize:14, valAxisMinVal:0, valAxisMaxVal:Math.max(...counts)+1,
    valAxisMajorUnit:Math.max(1, Math.ceil(Math.max(...counts)/5)), showValAxisTitle:true, valAxisTitle:"Nombre de fiches",
  });
  table(s, ["Durée","Ordre du jour"], agenda, {x:6.88, y:1.85, w:5.86, h:3.83}, [1,4.6], 15);
  caption(s, "Chaque fiche est comptée au niveau de preuve atteint. Un résultat archivé dispose d’une sortie conservée. Un résultat reproduit exige un rejeu vérifié.");
  note(s, [...model.profile.agenda, ...model.caps.map(c => c.name + " · " + c.status)]);
} else {
  const s = page("Les décisions à examiner en réunion", "Périmètre du rendez-vous  ·  30 minutes");
  table(s, ["Cas","Question opérationnelle","Pièce disponible"],
    model.caps.map(c => [c.name, c.decision, c.status]),
    {x:X, y:1.66, w:W, h:3.66}, [2.8,5.9,2], 16);
  text(s, model.profile.agenda.map((a,i) => agenda[i][0] + " — " + a).join("     "),
    X,5.59,W,1.08,{fontSize:15.5,color:palette.dark});
  note(s, [...model.profile.agenda, ...model.caps.map(c => c.method)]);
}

for (const cap of model.caps) {
  const exhibits = [cap.visual, ...(cap.exhibits || [])].filter(Boolean);
  if (!exhibits.length) {
    exhibits.push({kind:"table", title:cap.name, columns:["Question à instruire","Élément disponible"],
      rows:[["Décision",cap.decision],["Méthode",cap.method],["Limite",cap.limit]],
      caption:"Prochain essai. " + cap.next_test});
  }
  for (const exhibit of exhibits) exhibitPages(cap, exhibit);
}

for (const group of chunks(model.gaps, 3)) {
  const s = page("Quels essais faut-il mener ensuite ?", "Hypothèses à vérifier et conséquences pour la décision");
  table(s, ["Priorité","Question ouverte","Enjeu","Essai proposé"],
    group.map(g => [g.priority, g.title, g.impact, g.test]), full, [1.0,2.4,3.4,4.2], 15);
  note(s, group.map(g => [g.title, g.priority, g.impact, g.test].join("\n")));
}

const last = page(model.profile.closing, "Décisions à consigner en séance");
table(last, ["Question à trancher","Réponse à consigner"],
  model.profile.questions.map((q, i) => [q, ["Périmètre et décision concernée",
    "Scénario témoin, indicateur et critère de réussite","Données, responsable et échéance"][i]]),
  {x:X,y:1.70,w:W,h:4.42}, [6.6,4.4], 17);
note(last, [...model.profile.questions, ...model.caps.map(c => c.name + ". " + c.next_test)]);
pptx.writeFile({fileName: outputPath}).catch(error => {console.error(error); process.exitCode = 1;});
