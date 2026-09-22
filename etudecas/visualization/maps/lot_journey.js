// Read-only navigation: directed genealogy, never the full history of a shared stock.
let lotJourneyState = {anchor: '', focus: '', direction: 'downstream', detail: '', limit: 60};
let lotJourneyIndex = null;

function journeyIndex() {
  if (lotJourneyIndex) return lotJourneyIndex;
  const parents = new Map(), children = new Map(), events = new Map();
  (LOT_TRACE.events || []).forEach(row => {
    if (!events.has(row.lot_id)) events.set(row.lot_id, []);
    events.get(row.lot_id).push(row);
  });
  (LOT_TRACE.genealogy || []).forEach((row, index) => {
    if (!['production', 'transport'].includes(row.link_type) || !(Number(row.parent_qty) > 0)) return;
    const link = {...row, journey_id: index};
    for (const [map, key] of [[parents, row.child_lot_id], [children, row.parent_lot_id]]) {
      if (!map.has(key)) map.set(key, []);
      map.get(key).push(link);
    }
  });
  lotJourneyIndex = {parents, children, events};
  return lotJourneyIndex;
}

function journeyScope(root, direction) {
  const index = journeyIndex(), ids = new Set([root]), links = new Map();
  function walk(map, endpoint) {
    const visited = new Set([root]), queue = [root];
    for (let i = 0; i < queue.length; i++) {
      (map.get(queue[i]) || []).forEach(link => {
        links.set(link.journey_id, link);
        const next = link[endpoint];
        ids.add(next);
        if (!visited.has(next)) { visited.add(next); queue.push(next); }
      });
    }
  }
  if (direction !== 'downstream') walk(index.parents, 'parent_lot_id');
  if (direction !== 'upstream') walk(index.children, 'child_lot_id');
  return {root, direction, lot_ids: [...ids], links: [...links.values()]};
}

function journeyRole(lot) {
  if (lot.created_event_type === 'production_output') return 'Fabrication';
  const type = (nodeById[lot.node_id] || {}).type;
  if (type === 'customer') return 'Réception client';
  if (type === 'distribution_center') return 'Stock au dépôt';
  if (type === 'supplier_dc') return 'Origine fournisseur';
  return lot.created_event_type === 'opening_stock' ? 'Stock initial' : 'Réception / stock usine';
}

function journeyDay(value) {
  return value === undefined || value === null || value === '' ? 'date inconnue' : 'J' + escapeTableHtml(value);
}

function journeyLinkDates(link) {
  const matching = (journeyIndex().events.get(link.parent_lot_id) || []).filter(e => e.event_type === 'lane_ship' &&
    (link.shipment_id ? e.shipment_id === link.shipment_id : e.source_id === link.source_id && String(e.arrival_day) === String(link.day)));
  const departures = [...new Set(matching.map(e => e.departure_day === '' || e.departure_day == null ? e.day : e.departure_day))];
  const departure = link.departure_day !== '' && link.departure_day != null ? link.departure_day : departures.length === 1 ? departures[0] : null;
  return {departure, arrival: link.arrival_day !== '' && link.arrival_day != null ? link.arrival_day : link.day};
}

function journeyGroups(scope) {
  // Longest-path levels preserve actual operation order, including intermediate
  // products. Keep every stock occurrence separate: merging two depot stocks
  // would visually invent cross-paths between their productions and customers.
  const indegree = new Map(scope.lot_ids.map(id => [id, 0])), levels = new Map(scope.lot_ids.map(id => [id, 0])), outgoing = new Map();
  scope.links.forEach(link => {
    indegree.set(link.child_lot_id, indegree.get(link.child_lot_id) + 1);
    if (!outgoing.has(link.parent_lot_id)) outgoing.set(link.parent_lot_id, []);
    outgoing.get(link.parent_lot_id).push(link.child_lot_id);
  });
  const queue = scope.lot_ids.filter(id => indegree.get(id) === 0);
  for (let i = 0; i < queue.length; i++) {
    const parent = queue[i];
    (outgoing.get(parent) || []).forEach(child => {
      levels.set(child, Math.max(levels.get(child), levels.get(parent) + 1));
      indegree.set(child, indegree.get(child) - 1);
      if (indegree.get(child) === 0) queue.push(child);
    });
  }
  if (queue.length !== scope.lot_ids.length) throw new Error('Cycle dans la généalogie : parcours non affichable.');
  const groups = new Map(), groupByLot = new Map();
  scope.lot_ids.forEach(id => {
    const lot = lotTraceLotInfo(id), role = journeyRole(lot), level = levels.get(id);
    const key = 'lot:' + id;
    if (!groups.has(key)) groups.set(key, {id: 'JG' + groups.size, key, role, level, lots: [], lot});
    groups.get(key).lots.push(id); groupByLot.set(id, groups.get(key).id);
  });
  const edges = new Map();
  scope.links.forEach(link => {
    const source = groupByLot.get(link.parent_lot_id), target = groupByLot.get(link.child_lot_id);
    if (source !== target) edges.set(source + '|' + target, {source, target, type: link.link_type});
  });
  return {groups: [...groups.values()].sort((a,b) => a.level-b.level || Number(a.lot.created_day)-Number(b.lot.created_day) || a.key.localeCompare(b.key)), edges: [...edges.values()]};
}

function journeyLotBalance(id, atDay = null) {
  const lot = lotTraceLotInfo(id);
  let events = [...(journeyIndex().events.get(id) || [])];
  if (!events.length) return {status: 'unavailable', reason: 'Aucun événement de stock disponible.'};
  const entries = new Set(['opening_stock', 'production_output', 'opening_production_order', 'lane_receipt', 'external_procurement_receipt', 'stock_reconciliation', 'estimated_source_receipt', 'estimated_capacity_receipt']);
  const totals = {entered: 0, consumed: 0, shipped: 0, served: 0, written_off: 0, pending: 0, remaining: 0};
  const dates = {}, seen = new Set(), reserved = new Map();
  const numeric = value => value !== '' && value != null && Number.isFinite(Number(value));
  const close = (a,b) => Math.abs(a-b) <= 0.00002;
  let balance = 0, creation = null;
  function add(key, qty, day) {
    totals[key] += qty;
    if (!dates[key]) dates[key] = {first: day, last: day};
    dates[key].last = day;
  }
  try {
    if (events.some(row => !numeric(row.day))) throw new Error('Date de mouvement manquante ou invalide.');
    if (atDay !== null) {
      events = events.filter(row => Number(row.day) <= atDay);
      if (!events.length) return {status:'not_created', reason:'Occurrence pas encore créée à cette date.'};
    }
    events.sort((a,b) => Number(a.day)-Number(b.day)); // Stable order within a day.
    for (const row of events) {
      const qty = Number(row.qty), after = Number(row.qty_after), day = Number(row.day), type = row.event_type;
      if (!row.event_id || seen.has(row.event_id)) throw new Error('Identifiant de mouvement absent ou dupliqué.');
      seen.add(row.event_id);
      if (row.item_id !== lot.item_id || row.node_id !== lot.node_id || row.uom !== lot.uom) throw new Error('Article, site ou unité incohérents.');
      if (!numeric(row.qty) || !numeric(row.qty_after) || qty < 0 || after < -0.00002) throw new Error('Quantité manquante ou invalide.');
      if (lot.uom === 'UN' && (!close(qty, Math.round(qty)) || !close(after, Math.round(after)))) throw new Error('Quantité physique non entière en UN.');
      let delta = 0;
      if (entries.has(type)) {
        if (creation || seen.size !== 1) throw new Error('Entrée initiale absente ou multiple.');
        creation = row; delta = qty; add('entered', qty, day);
      } else {
        if (!creation) throw new Error('Entrée initiale absente.');
        if (type === 'production_consume' || type === 'production_consume_reference_transition') { delta = -qty; add('consumed', qty, day); }
        else if (type === 'demand_service') { delta = -qty; add('served', qty, day); }
        else if (type === 'writeoff' || type === 'stock_writeoff') { delta = -qty; add('written_off', qty, day); }
        else if (type === 'shipment_reserve') {
          if (!row.shipment_id) throw new Error('Réservation sans expédition identifiée.');
          delta = -qty; reserved.set(row.shipment_id, (reserved.get(row.shipment_id) || 0) + qty);
        } else if (type === 'lane_ship') {
          add('shipped', qty, day);
          if (reserved.has(row.shipment_id)) {
            const left = reserved.get(row.shipment_id)-qty;
            if (left < -0.00002) throw new Error('Départ supérieur à la réservation.');
            reserved.set(row.shipment_id, left);
          } else delta = -qty;
        } else throw new Error('Type de mouvement non pris en charge : ' + type);
      }
      balance += delta;
      if (!close(balance, after)) throw new Error('Le solde enregistré ne correspond pas aux mouvements.');
    }
    totals.pending = [...reserved.values()].reduce((sum,qty)=>sum+qty,0);
    totals.remaining = Number(events.at(-1).qty_after);
    if (!numeric(lot.qty) || !close(totals.entered, Number(lot.qty))) throw new Error('Quantité initiale différente de la fiche du registre.');
    return {status:'balanced', totals, dates, entry_type:creation.event_type, last_day:Number(events.at(-1).day), event_count:events.length};
  } catch (error) { return {status:'invalid', reason:error.message}; }
}

function journeyLotSummaryHtml(id) {
  const lot = lotTraceLotInfo(id), result = journeyLotBalance(id, journeyExplorer.day), e = escapeTableHtml;
  const receipts = (LOT_TRACE.material_traceability?.receipt_ids_by_lot[id] || []).map(key=>LOT_TRACE.material_traceability.receipts[key]);
  const origins = [...new Set(receipts.flatMap(r=>r.origins.map(p=>p.origin_id)))].map(key=>LOT_TRACE.material_traceability.origins[key]);
  const identity = lot.created_event_type==='production_output' ? 'Fabrication simulée identifiée par son lot métier ; matières à consulter en amont'
    : origins.length ? origins.map(o=>`${e(o.batch_number)} (${o.status==='observed'?'documenté':'simulé'})`).join(', ') + ' ; allocations détaillées dans le registre matières' : 'Non documentée';
  const entryNames = {opening_stock:'Stock initial', production_output:'Quantité produite', opening_production_order:'Production issue du carnet initial', lane_receipt:'Quantité reçue', external_procurement_receipt:'Approvisionnement reçu', stock_reconciliation:'Entrée de régularisation', estimated_source_receipt:'Entrée estimée', estimated_capacity_receipt:'Entrée estimée'};
  const labels = {entered:entryNames[result.entry_type], consumed:'Consommée en fabrication', shipped:'Expédiée', served:'Affectée au service client', written_off:'Sortie en perte / rebut', pending:'Réservée, en attente de départ', remaining:'Solde au site'};
  const dates = key => {
    const d=result.dates[key];
    return d ? (d.first===d.last ? journeyDay(d.first) : journeyDay(d.first)+' à '+journeyDay(d.last)) : 'Aucun mouvement enregistré';
  };
  const figures = result.status === 'balanced' ? `<div class="journeyBalanceGrid">${Object.entries(labels).filter(([key])=>!['written_off','pending'].includes(key) || result.totals[key]>0).map(([key,label])=>
    `<div data-journey-metric="${key}" data-quantity="${result.totals[key]}"><small>${label}</small><strong>${lotTraceQtyText(result.totals[key])} ${e(lot.uom)}</strong><small>${['remaining','pending'].includes(key)?'Au dernier événement : '+journeyDay(result.last_day):dates(key)}</small></div>`).join('')}</div>
    <p data-journey-balance-status="balanced">Bilan rapproché sur ${result.event_count} événements : entrée = consommation + expédition + service client + pertes + réservation en attente + solde au site.</p>`
    : `<p role="status" data-journey-balance-status="${result.status}">Bilan ${result.status==='invalid'?'incohérent — quantités récapitulatives non affichées':'indisponible'} : ${e(result.reason)}</p>`;
  return `<article class="journeyLotSummary" data-journey-summary-lot="${e(id)}"><h3>Fiche du lot · ${e(lot.business_lot_id || id)}</h3>
    <p>${e(lot.node_id)} · ${e(lot.item_id)} · Occurrence ${e(id)}. Origine fabricant : ${identity}.</p>
    <p>Cette fiche porte sur l’occurrence entière à ce site, ${journeyExplorer.day===null?'sur tout l’historique enregistré':'en fin de journée J'+e(journeyExplorer.day)}, même si le diagramme ne montre qu’une branche. Le solde n’est pas le stock total du lot sur le réseau. Une réception mélangée inclut tous ses lots d’origine.</p>
    ${figures}</article>`;
}

function journeyDetailHtml(ids, scope) {
  const e = escapeTableHtml, focus = lotTraceLotInfo(scope.root), model = lotTraceViewModelForLot(scope.root);
  return ids.map(id => {
    const lot = lotTraceLotInfo(id), events = journeyIndex().events.get(id) || [];
    const receipts = (LOT_TRACE.material_traceability?.receipt_ids_by_lot[id] || []).map(key => LOT_TRACE.material_traceability.receipts[key]);
    const origins = receipts.flatMap(r => r.origins.map(p => LOT_TRACE.material_traceability.origins[p.origin_id]));
    const identity = origins.length ? origins.map(o => `${e(o.batch_number)} (${o.status === 'observed' ? 'documenté' : 'simulé'})`).join(', ') : 'Origine fabricant non documentée';
    // Include only scoped links: an ancestor stock's unrelated uses are not
    // silently appended to the selected PF's journey.
    const relevant = scope.links.filter(l => l.parent_lot_id === id || l.child_lot_id === id);
    const rows = relevant.map(link => {
      const parent = lotTraceLotInfo(link.parent_lot_id), child = lotTraceLotInfo(link.child_lot_id), dates = journeyLinkDates(link);
      let contribution = '';
      if (model && focus.created_event_type === 'production_output' && link.link_type === 'transport' && child.item_id === focus.item_id) {
        const known = model.links.filter(l => l.parent_lot_id === link.parent_lot_id && l.child_lot_id === link.child_lot_id && l.link_type === 'transport' && String(l.shipment_id || '') === String(link.shipment_id || ''));
        if (known.length === 1 && Number(known[0].contribution_qty) > 0) contribution = `<br><strong>Part du PF suivi : ${lotTraceQtyText(known[0].contribution_qty)} ${e(child.uom)}</strong>`;
      }
      const physical = link.link_type === 'production'
        ? `Consommé : ${lotTraceQtyText(link.parent_qty)} ${e(parent.uom)} de ${e(parent.item_id)}<br>Fabrication totale : ${lotTraceQtyText(link.child_qty)} ${e(child.uom)} de ${e(child.item_id)}`
        : `Quantité de ce lien : ${lotTraceQtyText(link.parent_qty)} ${e(parent.uom)}<br>Réception totale : ${lotTraceQtyText(child.qty)} ${e(child.uom)}${contribution}`;
      const schedule = link.link_type === 'production' ? `Fin de fabrication : ${journeyDay(link.day)}` : `Départ : ${journeyDay(dates.departure)}<br>Arrivée : ${journeyDay(dates.arrival)}`;
      return `<tr data-journey-link="${link.journey_id}" data-journey-shipment="${e(link.shipment_id || '')}"><td>${link.link_type === 'production' ? 'Fabrication' : e(link.shipment_id || 'Expédition non identifiée')}<br>${e(parent.node_id)} → ${e(child.node_id)}</td><td>${schedule}</td><td>${physical}</td><td><button data-journey-focus="${e(link.parent_lot_id)}">Origine</button> <button data-journey-focus="${e(link.child_lot_id)}">Destination</button></td></tr>`;
    }).join('');
    const services = events.filter(row => row.event_type === 'demand_service');
    const last = events.filter(row => row.qty_after !== '' && row.qty_after != null).at(-1);
    return `<article class="journeyDetailCard"><strong>${e(lot.business_lot_id || lot.lot_id)} · ${e(lot.node_id)} · ${e(lot.item_id)}</strong>
      <p>${e(identity)}. Occurrence : ${e(id)}. ${journeyDay(lot.created_day)} · Quantité initiale : ${lotTraceQtyText(lot.qty)} ${e(lot.uom)}.</p>
      ${lot.created_event_type === 'opening_stock' ? '<p>Stock présent à J0 : histoire antérieure non documentée.</p>' : ''}
      ${last ? `<p>Solde de l’occurrence après son dernier événement (${journeyDay(last.day)}) : ${lotTraceQtyText(last.qty_after)} ${e(lot.uom)}.</p>` : ''}
      ${services.length ? `<p>Service client enregistré : ${services.map(s => `${journeyDay(s.day)} : ${lotTraceQtyText(s.qty)} ${e(lot.uom)}`).join(' ; ')}. Quantités de l’occurrence entière, éventuellement mélangée.</p>` : ''}
      <button data-journey-focus="${e(id)}">Recentrer sur cette occurrence</button>
      <table><thead><tr><th>Mouvement / trajet</th><th>Dates simulées</th><th>Quantités</th><th>Suivre</th></tr></thead><tbody>${rows || '<tr><td colspan="4">Aucun lien physique documenté dans cette direction.</td></tr>'}</tbody></table></article>`;
  }).join('');
}

function lotJourneyHtml(snapshot) {
  if (!snapshot) return '';
  if (lotJourneyState.anchor !== snapshot.lotId) lotJourneyState = {anchor: snapshot.lotId, focus: snapshot.lotId, direction: 'downstream', detail: '', limit: 60};
  const root = lotTraceLotInfo(lotJourneyState.focus), e = escapeTableHtml;
  let scope, layout;
  try { scope = journeyScope(root.lot_id, lotJourneyState.direction); layout = journeyGroups(scope); }
  catch (error) { return `<section id="lotJourney"><p>${e(error.message)}</p></section>`; }
  const model = lotTraceViewModelForLot(root.lot_id), selection=journeyVisibleGroups(scope,layout), visible=selection.groups;
  // Always retain the selected occurrence when the graph is large.
  const rootGroup = layout.groups.find(g => g.lots.includes(root.lot_id));
  if (rootGroup && !visible.includes(rootGroup)) visible.push(rootGroup);
  const columns = new Map();
  visible.forEach(group => {
    if (!columns.has(group.level)) columns.set(group.level, []);
    const lot = group.lot, isRoot = group.lots.includes(root.lot_id);
    const contribution = model?.contribution_by_lot?.[lot.lot_id];
    const portion = root.created_event_type === 'production_output' && lot.item_id === root.item_id && !isRoot && contribution > 0
      ? `<strong>Part du PF suivi : ${lotTraceQtyText(contribution)} ${e(lot.uom)}</strong><br>` : '';
    const ships = [...new Set(scope.links.filter(l => group.lots.includes(l.child_lot_id) && l.link_type === 'transport').map(l => l.shipment_id).filter(Boolean))];
    const schedules = [...new Set(scope.links.filter(l => group.lots.includes(l.child_lot_id) && l.link_type === 'transport').map(l => { const d=journeyLinkDates(l); return `${journeyDay(d.departure)} → ${journeyDay(d.arrival)}`; }))];
    const inspected=lotJourneyState.detail===lot.lot_id || (!lotJourneyState.detail && isRoot);
    const future=journeyExplorer.day!==null && Number(lot.created_day)>journeyExplorer.day;
    const card = `<button class="journeyNode ${isRoot ? 'journeyRoot' : ''} ${inspected?'journeyInspected':''} ${future?'journeyFuture':''} ${journeyOpsState.impact?.ids.includes(lot.lot_id)?'journeyImpacted':''}" aria-pressed="${inspected}" data-journey-card="${e(group.id)}" data-journey-lots="${e(JSON.stringify(group.lots))}" data-journey-lot="${e(group.lots.length === 1 ? group.lots[0] : '')}">
      <small>${e(group.role)}${isRoot ? ' · point de départ' : ''}${inspected?' · fiche ouverte':''}</small><strong>${e(group.lots.length === 1 ? lot.business_lot_id || lot.lot_id : lot.item_id.replace('item:','') + ' · ' + group.lots.length + ' occurrences')}</strong>
      <span>${e(lot.node_id)} · ${e(lot.item_id.replace('item:',''))}</span>
      <span>${group.lots.length === 1 ? journeyDay(lot.created_day) + ' · Total ' + lotTraceQtyText(lot.qty) + ' ' + e(lot.uom) : 'Dates et quantités séparées dans le détail'}</span>
      <span>${portion}${ships.length === 1 ? e(ships[0]) : ships.length ? ships.length + ' expéditions — voir détail' : ''}</span>
      ${schedules.length === 1 ? `<small>Départ → arrivée : ${schedules[0]}</small>` : ''}${future?'<small>À venir à la date de lecture</small>':''}</button>`;
    columns.get(group.level).push(card);
  });
  const selectedGroup = layout.groups.find(g => g.lots.includes(lotJourneyState.detail));
  const inspectedId=selectedGroup?.lots[0] || root.lot_id;
  return `<section id="lotJourney" data-journey-root="${e(root.lot_id)}" data-journey-direction="${e(scope.direction)}" data-journey-scope="${e(JSON.stringify(scope.lot_ids))}">
    <p class="journeyHeading">Point de départ : <strong>${e(root.business_lot_id || root.lot_id)}</strong> · ${e(root.node_id)} · ${e(root.item_id)} · ${e(root.lot_id)}. Cliquez sur une étape pour ouvrir sa fiche.</p>
    <div class="journeyToolbar"><button data-journey-direction="upstream" ${scope.direction === 'upstream' ? 'aria-pressed="true"' : ''}>← Origines</button><button data-journey-direction="downstream" ${scope.direction === 'downstream' ? 'aria-pressed="true"' : ''}>Destinations →</button><button data-journey-direction="both" ${scope.direction === 'both' ? 'aria-pressed="true"' : ''}>Les deux sens</button><button data-journey-focus="${e(snapshot.lotId)}">Revenir au lot principal</button>
      <button data-journey-back ${journeyExplorer.history.length?'':'disabled'}>← Précédent</button></div>
    ${journeySearchHtml()}${journeyDateHtml()}${journeyCaseControls()}
    <div class="journeyWorkspace"><main class="journeyMain"><div class="journeyGraphTools"><strong>${visible.length}/${layout.groups.length} étapes</strong><button data-journey-zoom="-0.15" aria-label="Réduire le graphe">−</button><button data-journey-zoom="0.15" aria-label="Agrandir le graphe">+</button><button data-journey-fit>Ajuster</button>${journeyNeighbourControls(inspectedId)}</div>
    <div class="journeyScroll"><div class="journeyCanvas" style="zoom:${journeyExplorer.zoom}"><svg class="journeyEdges" aria-hidden="true"></svg>${[...columns.entries()].sort((a,b)=>a[0]-b[0]).map(([level,cards])=>`<div class="journeyColumn"><small>Étape ${level+1}</small>${cards.join('')}</div>`).join('')}</div></div>
    ${layout.groups.length > visible.length ? `<p>${visible.length} étapes affichées sur ${layout.groups.length}.${selection.eligible>visible.length?' <button data-journey-more>Afficher 60 étapes supplémentaires</button>':''} ${journeyCaseState.depth===null?'Recherchez une réception précise pour recentrer le parcours.':'Étendez le voisinage depuis une fiche ou choisissez « Tout le parcours ».'}</p>` : ''}
    ${!scope.links.length ? '<p>Aucun mouvement documenté dans cette direction. Cela peut correspondre à un stock initial sans origine connue ou à un lot encore en stock ; ce n’est pas une preuve de livraison.</p>' : ''}
    <p class="journeyNote">Bleu : point de départ · vert : fiche ouverte · grisé : à venir. ${journeyOpsState.impact?'Orange : périmètre potentiel analysé sur tout l’historique. ':''}Flèches = liens physiques enregistrés ; les branches restent distinctes. Un SHIP identifie une expédition simulée, pas un camion réel. Matière consommée et PF produit utilisent leurs propres unités. Une présence de matière dans un PF ne donne pas à elle seule une quantité de PF attribuable.</p>
    ${journeyNetworkHtml(root.lot_id)}</main><aside class="journeySidebar" aria-label="Fiche de l’étape inspectée"><p><strong>Fiche ouverte : ${e(inspectedId)}</strong> · ${e(lotTraceLotInfo(inspectedId).node_id)}</p>
    <nav class="journeyTabs" aria-label="Détails du lot">${[['summary','Bilan'],['identity','Identités / états'],['operations','Transports / impacts'],['links','Mouvements']].map(([key,label])=>`<button data-journey-tab="${key}" aria-pressed="${journeyExplorer.tab===key}">${label}</button>`).join('')}</nav>
    <div ${journeyExplorer.tab==='summary'?'':'hidden'}>${journeyLotSummaryHtml(inspectedId)}</div>
    <div ${journeyExplorer.tab==='identity'?'':'hidden'}>${journeyIdentitiesHtml(inspectedId)}</div>
    <div ${journeyExplorer.tab==='operations'?'':'hidden'}><p>Transports et impacts : historique complet, indépendants du curseur de date.</p>${journeyOperationsHtml(inspectedId)}</div>
    <div ${journeyExplorer.tab==='links'?'':'hidden'}><p>Mouvements et liens sur tout l’historique.</p><details class="journeyDetails" ${selectedGroup ? 'open' : ''}><summary>Détail de l’étape ${selectedGroup ? 'sélectionnée' : 'principale'}</summary>${journeyDetailHtml(selectedGroup?.lots || [root.lot_id],scope)}</details></div>
    </aside></div></section>`;
}

function drawJourneyEdges() {
  const container = document.querySelector('#lotJourney .journeyCanvas');
  if (!container) return;
  const scope = journeyScope(lotJourneyState.focus, lotJourneyState.direction), layout = journeyGroups(scope), positions = new Map();
  const bounds = container.getBoundingClientRect();
  container.querySelectorAll('[data-journey-card]').forEach(card => {
    const rect = card.getBoundingClientRect();
    const zoom=journeyExplorer.zoom;
    positions.set(card.dataset.journeyCard,{x:(rect.left-bounds.left)/zoom,y:(rect.top-bounds.top)/zoom,width:rect.width/zoom,height:rect.height/zoom});
  });
  const svg = container.querySelector('svg');
  svg.setAttribute('width',container.scrollWidth); svg.setAttribute('height',container.scrollHeight);
  svg.innerHTML = '<defs><marker id="journeyArrow" markerWidth="8" markerHeight="8" refX="7" refY="3" orient="auto"><path d="M0,0 L0,6 L7,3 z" fill="#64748b"/></marker></defs>' + layout.edges.map(edge => {
    const a=positions.get(edge.source), b=positions.get(edge.target);
    if (!a || !b) return '';
    const x=a.x+a.width, y=a.y+a.height/2, tx=b.x, ty=b.y+b.height/2, mid=(x+tx)/2;
    const source=layout.groups.find(g=>g.id===edge.source).lots[0],target=layout.groups.find(g=>g.id===edge.target).lots[0];
    const links=scope.links.filter(l=>l.parent_lot_id===source && l.child_lot_id===target),ships=[...new Set(links.map(l=>l.shipment_id).filter(Boolean))];
    const title=links.map(l=>{const d=journeyLinkDates(l);return `${l.shipment_id || 'Consommation en fabrication'} · ${lotTraceQtyText(l.parent_qty)} ${lotTraceLotInfo(source).uom} · ${l.link_type==='transport'?journeyDay(d.departure)+' → '+journeyDay(d.arrival):journeyDay(l.day)}`;}).join(' ; ');
    return `<path d="M${x},${y} C${mid},${y} ${mid},${ty} ${tx},${ty}" stroke="${edge.type==='production'?'#2563eb':'#64748b'}" fill="none" stroke-width="2" marker-end="url(#journeyArrow)" ${ships.length===1?`data-journey-shipment-open="${escapeTableHtml(ships[0])}" role="button" tabindex="0" aria-label="Ouvrir ${escapeTableHtml(ships[0])}"`:''}><title>${escapeTableHtml(title)}</title></path>`;
  }).join('');
}

function refreshLotJourney() {
  const section = document.getElementById('lotJourney');
  if (!section) return;
  section.outerHTML = lotJourneyHtml({lotId: lotJourneyState.anchor});
  drawJourneyEdges();
  journeyRenderSearch();
}

document.addEventListener('click', event => {
  const focus=event.target.closest('[data-journey-focus]'), direction=event.target.closest('button[data-journey-direction]'), card=event.target.closest('[data-journey-card]');
  if (focus) { journeyRemember(); journeyCaseState.expanded=[]; lotJourneyState.focus=focus.dataset.journeyFocus; if (journeyRole(lotTraceLotInfo(lotJourneyState.focus))==='Réception client') lotJourneyState.direction='upstream'; lotJourneyState.detail=''; lotJourneyState.limit=60; journeyExplorer.query=''; journeyExplorer.tab='summary'; refreshLotJourney(); }
  else if (direction) { journeyCaseState.expanded=[]; lotJourneyState.direction=direction.dataset.journeyDirection; lotJourneyState.detail=''; refreshLotJourney(); }
  else if (card) { lotJourneyState.detail=card.dataset.journeyLot; journeyExplorer.tab='summary'; refreshLotJourney(); document.querySelector('.journeySidebar')?.scrollTo(0,0); }
  else if (event.target.closest('[data-journey-more]')) { lotJourneyState.limit+=60; refreshLotJourney(); }
});
window.addEventListener('resize',drawJourneyEdges);

// Separate entry point and dialog. Never render into, or change the state of,
// the existing detailed lot tracking window.
function installLotJourneyOption() {
  const legacyButton = document.getElementById('lotTraceOpenBtn');
  if (!legacyButton || document.getElementById('lotJourneyOpenBtn')) return;
  legacyButton.insertAdjacentHTML('afterend', '<button id="lotJourneyOpenBtn" class="tableBtn" type="button">Parcours simplifié des lots</button>');
  document.body.insertAdjacentHTML('beforeend', `<div id="lotJourneyModal" class="tableModal" role="dialog" aria-modal="true" aria-labelledby="lotJourneyTitle">
    <div class="tableModalCard"><div class="tableModalHeader"><div>
      <div class="tableModalTitle" id="lotJourneyTitle">Parcours simplifié des lots</div>
      <div class="tableModalMeta">Vue indépendante · rechercher un lot ou une expédition, puis suivre ses origines ou destinations</div>
    </div><button id="lotJourneyCloseBtn" class="tableBtn" type="button">Fermer</button></div>
    <div id="lotJourneyBody" class="tableModalBody"></div></div></div>`);
  const modal = document.getElementById('lotJourneyModal'), button = document.getElementById('lotJourneyOpenBtn');
  function close() { modal.classList.remove('visible'); button.focus(); }
  button.addEventListener('click', () => {
    const root = selectedLotTraceSnapshot()?.lotId || Object.keys(LOT_TRACE.lots || {})[0];
    journeyOpsState = {shipment:'', impact:null, limit:50};
    journeyCaseState.depth=null;journeyCaseState.expanded=[];journeyCaseState.message='';
    journeyExplorer={day:null,tab:'summary',query:'',site:'',item:'',role:'',identity:'',from:'',to:'',offset:0,history:[],zoom:1};
    lotJourneyState = {anchor: root, focus: root, direction: 'downstream', detail: '', limit: 60};
    document.getElementById('lotJourneyBody').innerHTML = root ? lotJourneyHtml({lotId: root}) : '<p>Aucun lot disponible.</p>';
    modal.classList.add('visible');
    drawJourneyEdges();
    document.getElementById('lotJourneyCloseBtn').focus();
  });
  document.getElementById('lotJourneyCloseBtn').addEventListener('click', close);
  modal.addEventListener('click', event => { if (event.target === modal) close(); });
  modal.addEventListener('keydown', event => { if (event.key === 'Escape') { event.stopPropagation(); close(); } });
}
installLotJourneyOption();
