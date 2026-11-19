/* Embedded, offline interaction for the dated industrial investigation. */
(function (global) {
  "use strict";

  const DAY = 86400000;
  const LABELS = {
    "1920": "Muret · 1920",
    "1430": "Gien · 1430",
    "1810": "Avène · 1810",
    "1450": "Gaillac · 1450"
  };
  const FORMAT = new Intl.NumberFormat("fr-FR", {maximumFractionDigits: 6});
  const SHORT = new Intl.NumberFormat("fr-FR", {maximumFractionDigits: 1});
  const UNKNOWN = "Inconnu";
  const esc = value => String(value ?? "").replace(/[&<>"']/g, c => ({
    "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;"
  })[c]);
  const isNumber = value => typeof value === "number" && Number.isFinite(value);
  const qty = (value, unit = "") => isNumber(value) ? FORMAT.format(value) + (unit ? " " + unit : "") : UNKNOWN;
  const signedQty = (value, unit = "") => (isNumber(value) && value > 0 ? "+" : "") + qty(value,unit);
  const hasDate = value => typeof value === "string" && /^\d{4}-\d{2}-\d{2}$/.test(value);
  const day = value => hasDate(value) ? Date.parse(value + "T00:00:00Z") / DAY : NaN;
  const dateLabel = value => hasDate(value) ? value.slice(8, 10) + "/" + value.slice(5, 7) + "/" + value.slice(0, 4) : UNKNOWN;
  const shortDate = value => hasDate(value) ? value.slice(8, 10) + "/" + value.slice(5, 7) : UNKNOWN;
  const addDays = (value, n) => Number.isFinite(day(value)) ? new Date((day(value) + n) * DAY).toISOString().slice(0, 10) : null;
  const absGap = (a, b) => Math.abs(day(a) - day(b));
  const weekTitle = week => dateLabel(week.start) + " au " + dateLabel(week.end);
  const afterWeek = week => week.stock_end_date || addDays(week.end, 1);
  const amount = (r, key) => isNumber(r?.[key]) ? r[key] * (r.factor ?? 1) : null;
  const rawUnit = r => r.canonical_unit || r.unit || "";
  const signed = week => isNumber(week.movement?.outbound) ? week.movement.outbound : null;
  const oriented = week => signed(week) === null ? null : -signed(week);
  const codeLabel = value => String(value ?? "").replace(/^item:/, "");
  const pairKey = (site, item) => `${site}/${item}`;
  const jump = (site, item, label) => `<button type="button" data-pair="${esc(pairKey(site,item))}">${esc(label)}</button>`;
  const badge = (label, isAlt = false) => `<span class="flag${isAlt ? " alt" : ""}">${esc(label)}</span>`;
  const caseLink = (product, week) => `#${product}/${week.start}`;
  const initial = (data, product) => {
    const wanted = product === "268967" ? "2025-03-17" : "2025-10-13";
    const weeks = data.products[product].weeks;
    return weeks.some(w => w.start === wanted) ? wanted : weeks[0].start;
  };

  function parseCase(data, hash) {
    const match = /^#?(268967|268091)\/(\d{4}-\d{2}-\d{2})$/.exec(hash || "");
    if (!match || !data.products[match[1]].weeks.some(w => w.start === match[2])) return null;
    return {product: match[1], start: match[2]};
  }

  function indexRows(data) {
    const index = new Map();
    for (const pair of Object.values(data.pairs)) {
      for (const table of ["stocks", "opening_stocks", "movements", "mrp", "opening_orders", "lot_rules", "policies"]) {
        for (const row of pair[table] || []) index.set(row.id, row);
      }
    }
    for (const item of Object.values(data.products)) {
      for (const table of ["demand_actual", "demand_forecast"]) {
        for (const row of item[table] || []) index.set(row.id, row);
      }
    }
    return index;
  }

  function source(data, row, keys) {
    if (!row) return "Pièce source inconnue";
    const ref = data.sources[row.source];
    if (!ref) return esc(row.id || "Source inconnue");
    const cells = keys.map(k => ref.columns?.[k]).filter(Boolean).map(col => col + row.row);
    return `<span class="source">${esc(ref.file)}<br>${esc(ref.sheet)} · ${esc(cells.join(", ") || ("ligne " + row.row))}</span>`;
  }

  function site(data, id) {
    if (LABELS[id]) return LABELS[id];
    const known = data.sites?.[id];
    return typeof known === "string" && known && !known.includes(id) ? `${known} · ${id}` : String(id);
  }

  function previousExplorer(payload, pair, anchor, row) {
    if (!payload.explorer) return "";
    const fields = {item: pair.item, site: pair.site, date: anchor};
    if (row) fields.record = row.id;
    const query = Object.entries(fields).map(([key, value]) => key + "=" + encodeURIComponent(value)).join("&");
    return `<a href="${esc(payload.explorer + "?" + query)}">${row ? "Ouvrir cette ligne" : "Ouvrir dans l’explorateur des sources"}</a>`;
  }

  function wireSources(data, index, ids, fields) {
    const rows = (ids || []).map(id => index.get(id)).filter(Boolean);
    return rows.length ? rows.map(r => source(data,r,fields)).join("<br>") : "Pièce source inconnue";
  }

  function table(caption, heads, rows) {
    const header = heads.map(h => `<th scope="col">${esc(h)}</th>`).join("");
    const body = rows.map(row => "<tr>" + row.map(v => `<td>${v}</td>`).join("") + "</tr>").join("");
    return `<div class="table-scroll"><table><caption>${esc(caption)}</caption><thead><tr>${header}</tr></thead><tbody>${body}</tbody></table></div>`;
  }

  function details(label, content, open = false) {
    return `<details${open ? " open" : ""}><summary>${esc(label)}</summary>${content}</details>`;
  }

  function fact(label, value, showSign = false) {
    return `<div class="fact"><span>${esc(label)}</span><strong>${esc((showSign ? signedQty : qty)(value,"UN"))}</strong></div>`;
  }

  function versionRows(pair, anchor) {
    const versions = [...new Set((pair.mrp || []).map(r => r.version).filter(hasDate))].sort().reverse();
    return {versions, latest: versions.find(v => v <= anchor) || null};
  }

  function nearby(rows, anchor, fields, radius = 28) {
    return rows.filter(row => fields.some(key => absGap(row[key],anchor) <= radius));
  }

  function movements(data, rows, active, drillPair = null) {
    if (!rows.length) return `<p class="status">Aucune ligne de mouvement renseignée pour cette période et ce site.</p>`;
    return table("Mouvements hebdomadaires signés", ["Semaine", "Unité", "Divers", "Entrées", "Sorties", "Prélèvements Scan3", "Source"], rows.map(r => {
      const start = r.week_start || addDays(r.date,1);
      const marker = dateLabel(r.date);
      const date = dateLabel(start);
      return [
        `<button type="button" data-anchor="${esc(start)}"${drillPair ? ` data-pair="${esc(drillPair)}"` : ""}${active === start ? ' aria-current="true"' : ""}>${esc(date)}</button><br><span class="source">Repère fichier ${esc(marker)}</span>`,
        `${esc(rawUnit(r))}${r.factor !== 1 && r.unit ? '<br><span class="source">Source '+esc(r.unit)+'</span>' : ""}`, ...["divers","inbound","outbound","scan3"].map(k => esc(signedQty(amount(r,k)))),
        source(data,r,["date","divers","inbound","outbound","scan3"])
      ];
    }));
  }

  function chartMarkup(product, weeks, active) {
    const x0 = 64, x1 = 906, y0 = 18, y1 = 222;
    const x = i => x0 + i * (x1 - x0) / Math.max(1, weeks.length - 1);
    const values = weeks.flatMap(w => [oriented(w), w.demand]).filter(isNumber);
    const scale = (Math.max(1,...values) - Math.min(0,...values)) / 4;
    const magnitude = 10 ** Math.floor(Math.log10(scale));
    const step = Math.max(1, Math.ceil(scale / magnitude) * magnitude);
    const max = Math.ceil(Math.max(1,...values) / step) * step;
    const min = Math.floor(Math.min(0,...values) / step) * step;
    const y = value => y1 - (value - min) * (y1 - y0) / (max - min);
    const axis = [];
    for (let tick = min; tick <= max; tick += step) {
      axis.push(`<line class="${tick === 0 ? "midline" : "gridline"}" x1="${x0}" y1="${y(tick)}" x2="${x1}" y2="${y(tick)}"></line><text x="${x0-8}" y="${y(tick)+4}" text-anchor="end" class="tick">${esc(SHORT.format(tick/1000))} k</text>`);
    }
    const stepX = (x1-x0) / Math.max(1, weeks.length-1);
    for (let i = 0; i < weeks.length; i++) {
      if (i !== 0 && i !== weeks.length - 1 && i % 8 !== 0) continue;
      axis.push(`<text class="tick" x="${x(i)}" y="242" text-anchor="middle">${shortDate(weeks[i].start)}</text>`);
    }
    const series = [];
    for (const [cls, get] of [["net",oriented],["demand",w => w.demand]]) {
      let current = [];
      const draw = () => {
        if (current.length) series.push(`<polyline class="series series-${cls}" points="${current.join(" ")}"></polyline>`);
        current = [];
      };
      weeks.forEach((week,i) => {
        const value = get(week);
        if (!isNumber(value)) return draw();
        current.push(`${x(i)},${y(value)}`);
        series.push(`<circle class="datum dot-${cls}" cx="${x(i)}" cy="${y(value)}" r="${cls === "net" ? 3.8 : 2.5}"></circle>`);
      });
      draw();
    }
    const bands = weeks.map((week,i) => oriented(week) === null
      ? `<rect class="day-band" x="${x(i)-stepX/2}" y="${y0}" width="${stepX}" height="${y1-y0}"></rect>`
      : "").join("");
    const links = weeks.map((week,i) => {
      const net = oriented(week);
      const current = week.start === active ? ' aria-current="true"' : "";
      return `<a class="week-link" href="${caseLink(product,week)}"${current} tabindex="0"><title>${esc(weekTitle(week))} · Mouvement net de stock (sortie positive) ${esc(signedQty(net,"UN"))} · Demande ${esc(qty(week.demand,"UN"))}</title><rect class="week-marker" x="${x(i)-stepX/2}" y="${y0}" width="${stepX}" height="${y1-y0}"></rect></a>`;
    }).join("");
    return `<svg viewBox="0 0 930 255" aria-label="Quantités en unités par semaine. Choisir une semaine pour consulter les mouvements."><text x="3" y="14" class="tick">UN</text>${bands}${axis.join("")}${series.join("")}${links}</svg>`;
  }

  function selectors(data, state) {
    const options = Object.keys(data.products).sort().reverse().map(product => `<option value="${product}"${product===state.product ? " selected" : ""}>${product}</option>`).join("");
    const weeks = data.products[state.product].weeks;
    const dates = weeks.map(w => `<option value="${w.start}"${w.start===state.start ? " selected" : ""}>${weekTitle(w)}${signed(w)===null ? " · mouvement inconnu" : ""}</option>`).join("");
    const i = weeks.findIndex(w => w.start===state.start);
    const prev = i>0 ? `<a class="quick" href="${caseLink(state.product,weeks[i-1])}">Semaine précédente</a>` : "";
    const next = i<weeks.length-1 ? `<a class="quick" href="${caseLink(state.product,weeks[i+1])}">Semaine suivante</a>` : "";
    return `<label for="product-select">Produit fini<select id="product-select">${options}</select></label><label for="week-select">Semaine du dossier<select id="week-select">${dates}</select></label>${prev}${next}`;
  }

  function shortcuts(data, product) {
    const named = [
      ["268967", "2025-03-17", "268967 · 17 mars"],
      ["268967", "2025-03-24", "268967 · 24 mars"],
      ["268091", "2025-10-13", "268091 · 13 octobre"]
    ].filter(([pf,date]) => data.products[pf].weeks.some(w => w.start===date));
    const examples = named.map(([pf,start,label]) => `<a class="quick" href="${caseLink(pf,{start})}">${label}</a>`).join("");
    const low = data.products[product].weeks.filter(w => isNumber(w.demand) && w.demand>0 && signed(w)!==null)
      .map(w => ({week:w,ratio:Math.abs(signed(w))/w.demand})).sort((a,b) => a.ratio-b.ratio).slice(0,4)
      .map(({week,ratio}) => `<a class="quick" href="${caseLink(product,week)}">${shortDate(week.start)} · ${esc(SHORT.format(100*ratio))} %</a>`).join("");
    return `<div class="presets">${examples}</div>${low ? `<div class="presets"><span class="hint">Creux · amplitude du mouvement net rapportée à la demande</span>${low}</div>` : ""}`;
  }

  function depot(payload, index, product, week) {
    const {data} = payload;
    const key = pairKey("1920",product);
    const pair = data.pairs[key];
    const supplied = [
      ["Demande réelle", week.demand, week.demand_ids, ["date","qty"]],
      ["Stock photo du " + dateLabel(week.start), week.stock_start, week.stock_start_ids, ["date","qty"]],
      ["Stock photo du " + dateLabel(afterWeek(week)), week.stock_end, week.stock_end_ids, ["date","qty"]],
      ["Somme des mouvements signés", week.movement_sum, week.movement_ids, ["divers","inbound","outbound","scan3"]]
    ];
    const trace = table("Pièces du dossier à Muret",["Observation","Valeur","Source"], supplied.map(([label,value,ids,fields]) => [
      esc(label),esc(qty(value,"UN")),wireSources(data,index,ids,fields)
    ]));
    const movementRows = (week.movement_ids || []).map(id => index.get(id)).filter(Boolean);
    const balance = isNumber(week.balance_residual)
      ? "Le résidu est la variation entre photos moins la somme des mouvements signés."
      : "Une photo de borne ou une valeur source manque pour vérifier le bilan.";
    const conditional = `<p class="explain">${badge("Calcul sous hypothèse",true)} Si toute la demande est sortie pendant la semaine et si le périmètre des autres flux est complet, l’apport net nécessaire vaut <strong>${esc(qty(week.conditional_inbound,"UN"))}</strong>. Calcul&nbsp;: variation des photos − ajustements « Divers » + demande réelle. L’identité des expéditions reste inconnue.</p>`;
    return `<h2>Muret · PF ${product}</h2><p><strong>${weekTitle(week)}</strong> ${week.crosses_year_boundary ? badge("Semaine à cheval sur deux années",true) : ""}</p><div class="facts">${[
      fact("Demande réelle",week.demand), fact("Sorties signées dans le fichier",signed(week),true),
      fact("Stock en fin de période",week.stock_end), fact("Variation des photos",week.stock_change,true),
      fact("Résidu de rapprochement",week.balance_residual,true)
    ].join("")}</div><p class="hint">${balance}</p>${conditional}${movements(data,movementRows,week.start,key)}
    ${details("Cellules de demande et de stock",trace)}
    <div class="bar">${jump("1920",product,"MRP et carnet de Muret")}${previousExplorer(payload,pair,week.start)}</div>`;
  }

  function factory(data, index, product, week) {
    const context = data.products[product];
    const at = context.weeks.findIndex(w => w.start===week.start);
    const neighbors = context.weeks.slice(Math.max(0,at-3),at+4);
    const periodRows = neighbors.map(w => [
      `<a href="${caseLink(product,w)}"${w.start===week.start ? ' aria-current="true"' : ""}>${weekTitle(w)}</a>`,
      esc(qty(w.packaging_withdrawals,"UN")), esc(qty(w.estimated_production,"UN")),
      wireSources(data,index,w.packaging_movement_ids,["date","scan3"])
    ]);
    const materials = context.components.map(component => {
      const item = component.item;
      const row = week.components?.[item] || {};
      const unit = row.unit || component.unit;
      return [
        `<strong>${esc(codeLabel(item))}</strong><br><span class="source">${esc(component.kind)}</span>`,
        esc(qty(row.scan3,unit)), esc(qty(row.other_outbound,unit)),
        esc(qty(row.theoretical_from_packaging,unit)),
        `${wireSources(data,index,row.movement_ids,["outbound","scan3"])}<br><span class="source">Nomenclature ${esc(component.bom_id || UNKNOWN)}</span>`,
        jump(component.site || context.factory,item,"Examiner")
      ];
    });
    return `<h2>Usine · ${esc(site(data,context.factory))}</h2>
      <p>Étuis ${esc(context.packaging)}. Les prélèvements de plusieurs semaines renseignent le calendrier apparent du conditionnement. La quantité terminée, la durée du lot et la date exacte de fabrication restent inconnues.</p>
      ${table("Activité de conditionnement autour de la semaine",["Semaine","Étuis prélevés","Équivalent PF estimé","Source"],periodRows)}
      <div class="bar">${jump(context.factory,product,"Examiner le PF à l’usine")}${jump(context.factory,context.packaging,"Examiner les étuis")}</div>
      <h3>Consommations et sorties de composants sur la semaine sélectionnée</h3>
      <p class="hint">Les valeurs source gardent leur signe. La théorie applique la nomenclature à l’estimation par les étuis. Une différence reste à expliquer, notamment en cas d’usages partagés.</p>
      ${table("Matières, semi-finis et emballages",["Composant","Prélèvements Scan3 signés","Autres sorties signées","Théorie d’après les étuis","Sources","Détail"],materials)}`;
  }

  function routeMarkup(data, pair, anchor) {
    const routes = (data.routes || []).filter(r => r.item===pair.item && r.destination_site===pair.site);
    if (!routes.length) return `<p class="status">Aucune liaison amont renseignée dans le périmètre pour ce couple site et article.</p>`;
    const rows = routes.map(route => {
      const upstream = route.source_site;
      const name = upstream ? site(data,upstream) : (route.supplier || "Fournisseur non localisé");
      const link = upstream && data.pairs[pairKey(upstream,pair.item)] ?
        jump(upstream,pair.item,`Remonter vers ${name}`) : esc(name);
      const refs = (route.source_refs || []).map(r => `${esc(r.file)} · ${esc(r.sheet)} · ${esc((r.cells || []).join(", "))}`).join("<br>");
      const category = {
        source_context: "Contexte fournisseur",
        documented_route: "Liaison documentée",
        reconciled_legacy_route: "Liaison ancienne rapprochée"
      }[route.relation] || "Rapprochement de contexte";
      const upstreamPair = data.pairs[pairKey(upstream,pair.item)];
      const candidates = (upstreamPair?.movements || []).filter(r => (r.week_start || addDays(r.date,1))===anchor);
      const sameWeek = candidates.map(r => `<br>${esc(qty(amount(r,"outbound"),rawUnit(r)))} de sorties signées au site amont · ${source(data,r,["outbound"])}`).join("");
      return `<li>${link} ${badge(category,true)}<br><span class="source">${refs}</span>${sameWeek}</li>`;
    }).join("");
    return `<ul class="route-list">${rows}</ul><p class="hint">Ces liaisons donnent des candidats à examiner. L’identité du transfert reste inconnue.</p>`;
  }

  function mrpMarkup(data, pair, anchor, chosen) {
    const {versions,latest} = versionRows(pair,anchor);
    if (!versions.length) return `<p class="status">Aucune version MRP renseignée pour ce site et cet article.</p>`;
    const version = chosen && versions.includes(chosen) ? chosen : latest;
    const selector = `<label for="mrp-version">Version MRP<select id="mrp-version"><option value="">Dernière version au plus tard à la date</option>${versions.map(v=>`<option value="${v}"${chosen===v ? " selected" : ""}>${dateLabel(v)}${v>anchor ? " · postérieure" : ""}</option>`).join("")}</select></label>`;
    if (!version) return selector + `<p class="status">Aucune version MRP du ${dateLabel(anchor)} ou avant. Le menu ouvre les versions postérieures pour comparaison rétrospective.</p>`;
    const rows = (pair.mrp || []).filter(r=>r.version===version && absGap(r.week_start || r.date,anchor)<=28);
    const header = `<p>${badge("Prévu",true)} <strong>Calcul du ${dateLabel(version)}</strong> ${version>anchor ? badge("Version postérieure · lecture rétrospective",true) : ""}</p>`;
    const note = `<p class="hint">Le stock physique mentionné pour une période future peut correspondre à une quantité déjà présente et utilisable plus tard. Réception prévue et disponibilité d’un stock présent doivent être lues séparément.</p>`;
    const result = rows.length ? table("Lignes de plan dans la fenêtre de la fiche",["Repère source","Unité","Entrée prévue","Besoin prévu","Stock physique indiqué","Stock prévu en fin","Source"],rows.map(r=>[
      esc(dateLabel(r.date)),esc(rawUnit(r)),...["inbound","outbound","physical","ending"].map(k=>esc(qty(amount(r,k)))),
      source(data,r,["version","date","inbound","outbound","physical","ending"])
    ])) : `<p class="status">Aucune ligne de cette version sur les semaines affichées.</p>`;
    return selector+header+note+result;
  }

  function upstream(payload, data, product, anchor, focus, version, allOrders) {
    const pair = data.pairs[focus];
    if (!pair) return `<h2 id="upstream-title">Fiche des sources</h2><p>Couple site et article absent.</p>`;
    const ctx = data.products[product];
    const rows = nearby(pair.movements || [],anchor,["week_start","date"]);
    const stocks = nearby(pair.stocks || [],anchor,["date"]);
    const orders = allOrders ? (pair.opening_orders || []) :
      nearby(pair.opening_orders || [],anchor,["delivery_date","available_date"]);
    const stockTable = stocks.length ? table("Photos de stock",["Date","Quantité physique","Source"],stocks.map(r=>[
      esc(dateLabel(r.date)),esc(qty(amount(r,"qty"),rawUnit(r))),source(data,r,["date","qty","unit"])
    ])) : `<p class="status">Aucune photo renseignée dans la fenêtre.</p>`;
    const opening = nearby(pair.opening_stocks || [],anchor,["date"]);
    const openingTable = opening.length ? details("Photos initiales d’une autre source",
      table("Photos initiales conservées séparément",["Date","Quantité physique","Source"],opening.map(r=>[
          esc(dateLabel(r.date)),esc(qty(amount(r,"qty"),rawUnit(r))),source(data,r,["date","qty","unit"])
      ]))) : "";
    const orderTable = orders.length ? table("Carnet partiel",["Livraison prévue","Disponibilité prévue","Quantité prévue","Élément de plan","Source"],orders.map(r=>[
      esc(dateLabel(r.delivery_date)),esc(dateLabel(r.available_date)),esc(qty(amount(r,"qty"),rawUnit(r))),
      esc(r.planning_element || UNKNOWN),source(data,r,["delivery_date","available_date","qty","planning_element"])
    ])) : `<p class="status">Aucune ligne du carnet partiel pour ce filtre.</p>`;
    const related = (data.boms?.[pair.item] || []).filter(r => r.site===pair.site && data.pairs[pairKey(r.site,r.item)])
      .map(r => `${jump(r.site,r.item,`Examiner ${r.item}`)} <span class="source">${esc(qty(r.qty_per_output,r.unit))} théoriques / ${esc(r.output_unit || "unité")} de ${esc(pair.item)} · ${esc(r.bom_id || "")}</span>`).join("");
    const nav = `<div class="bar">${jump("1920",product,"Muret")}${jump(ctx.factory,product,"Usine PF")}${jump(ctx.factory,ctx.packaging,"Étuis")}</div>`;
    return `<h2 id="upstream-title" tabindex="-1">Fiche des sources · ${esc(pair.item)} · ${esc(site(data,pair.site))}</h2>
      ${nav}
      <div class="bar"><label for="context-date">Date repère de la fiche<input type="date" id="context-date" value="${esc(anchor)}"></label>
      <button type="button" id="reset-context">Semaine du dossier</button>
      ${previousExplorer(payload,pair,anchor)}</div>
      <p class="hint">Mouvements, photos et plan dans les quatre semaines de part et d’autre de la date. Cette fenêtre est un choix d’affichage.</p>
      ${routeMarkup(data,pair,anchor)}${related ? '<div class="bar">'+related+"</div>" : ""}
      ${details("Mouvements du site",movements(data,rows,anchor),true)}
      ${details("Photos de stock",stockTable)}
      ${openingTable}
      ${details("Versions MRP",mrpMarkup(data,pair,anchor,version),true)}
      ${details("Ordres du carnet partiel",`<p class="hint">Quantités et dates prévues. Numéro et date de création de l’ordre inconnus.</p><button type="button" id="toggle-orders" aria-pressed="${allOrders}">Toutes les dates du carnet</button>`+orderTable,true)}`;
  }

  function mount(payload, doc, win) {
    const data = payload.data;
    const index = indexRows(data);
    const state = parseCase(data,win.location.hash) || {product:"268967", start:initial(data,"268967")};
    let ctx = null, selected = null, focus = null, anchor = null, version = null, allOrders = false;
    const content = (id, html) => { doc.getElementById(id).innerHTML = html; };
    const redrawSource = () => content("upstream",upstream(payload,data,state.product,anchor,focus,version,allOrders));
    const redrawCase = () => {
      ctx = data.products[state.product];
      selected = ctx.weeks.find(w => w.start===state.start);
      focus = pairKey("1920",state.product);
      anchor = selected.start;
      version = null;
      allOrders = false;
      content("filters",selectors(data,state));
      content("chart",chartMarkup(state.product,ctx.weeks,state.start));
      content("examples",shortcuts(data,state.product));
      content("case",depot(payload,index,state.product,selected));
      content("factory",factory(data,index,state.product,selected));
      redrawSource();
    };
    win.addEventListener("hashchange", () => {
      const result = parseCase(data,win.location.hash);
      if (result) {
        Object.assign(state,result);
        redrawCase();
      }
    });
    doc.addEventListener("change", event => {
      const {id,value} = event.target;
      if (id === "product-select") win.location.hash = caseLink(value,{start:initial(data,value)});
      if (id === "week-select") win.location.hash = caseLink(state.product,{start:value});
      if (id === "mrp-version") { version = value || null; redrawSource(); doc.getElementById(id)?.focus(); }
      if (id === "context-date" && hasDate(value)) { anchor = value; version = null; redrawSource(); doc.getElementById(id)?.focus(); }
    });
    doc.addEventListener("click", event => {
      const control = event.target.closest("button");
      if (!control) return;
      const newPair = control.dataset.pair, newAnchor = control.dataset.anchor;
      if (newPair && data.pairs[newPair]) {
        focus = newPair; version = null; allOrders = false;
        if (hasDate(newAnchor)) anchor = newAnchor;
        redrawSource();
        doc.getElementById("upstream-title").focus();
      } else if (newAnchor && control.closest("#upstream")) {
        anchor = newAnchor; version = null; redrawSource();
        doc.getElementById("context-date")?.focus();
      } else if (control.id === "reset-context") {
        anchor = selected.start; version = null; redrawSource();
        doc.getElementById("context-date")?.focus();
      } else if (control.id === "toggle-orders") {
        allOrders = !allOrders; redrawSource();
        doc.getElementById("toggle-orders")?.focus();
      }
    });
    redrawCase();
  }

  global.MuretTrace = {mount, parseCase, chartMarkup, versionRows, indexRows, depot, factory, upstream};
  if (global.document?.getElementById("muret-data")) {
    const payload = JSON.parse(global.document.getElementById("muret-data").textContent);
    mount(payload,global.document,global);
  }
}(globalThis));
