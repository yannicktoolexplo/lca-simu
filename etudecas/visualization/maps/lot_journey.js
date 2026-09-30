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
  const entries = new Set(['opening_stock', 'production_output', 'opening_production_order', 'opening_purchase_order_receipt', 'lane_receipt', 'external_procurement_receipt', 'stock_reconciliation', 'estimated_source_receipt', 'estimated_capacity_receipt']);
  const totals = {entered: 0, consumed: 0, shipped: 0, served: 0, written_off: 0, pending: 0, remaining: 0};
  const dates = {}, seen = new Set(), reserved = new Map();
  const numeric = value => value !== '' && value != null && Number.isFinite(Number(value));
  const close = (a,b) => Math.abs(a-b) <= 0.00002;
  let balance = 0, creation = null, held = 0, availabilityEvents = 0, released = 0;
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
        else if (type === 'stock_availability_hold') {
          held += qty; availabilityEvents += 1;
        } else if (type === 'stock_availability_release') {
          if (qty > held + 0.00002) throw new Error('Libération supérieure au stock détenu non utilisable.');
          held = Math.max(0, held - qty); released += qty; availabilityEvents += 1;
        } else if (type === 'shipment_reserve') {
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
      if (held > balance + 0.00002) throw new Error('Stock détenu non utilisable supérieur au solde physique.');
    }
    totals.pending = [...reserved.values()].reduce((sum,qty)=>sum+qty,0);
    totals.remaining = Number(events.at(-1).qty_after);
    if (!numeric(lot.qty) || !close(totals.entered, Number(lot.qty))) throw new Error('Quantité initiale différente de la fiche du registre.');
    return {status:'balanced', totals, dates, entry_type:creation.event_type, last_day:Number(events.at(-1).day), event_count:events.length,
      availability:availabilityEvents?{held,available:Math.max(0,balance-held),physical_onsite:balance+totals.pending,released,event_count:availabilityEvents}:null};
  } catch (error) { return {status:'invalid', reason:error.message}; }
}

function journeyLotSummaryHtml(id) {
  const lot = lotTraceLotInfo(id), result = journeyLotBalance(id, journeyExplorer.day), e = escapeTableHtml;
  const receipts = (LOT_TRACE.material_traceability?.receipt_ids_by_lot[id] || []).map(key=>LOT_TRACE.material_traceability.receipts[key]);
  const origins = [...new Set(receipts.flatMap(r=>r.origins.map(p=>p.origin_id)))].map(key=>LOT_TRACE.material_traceability.origins[key]);
  const identity = lot.created_event_type==='production_output' ? 'Fabrication simulée identifiée par son lot métier ; matières à consulter en amont'
    : origins.length ? origins.map(o=>`${e(o.batch_number)} (${o.status==='observed'?'documenté':'simulé'})`).join(', ') + ' ; allocations détaillées dans le registre matières' : 'Non documentée';
  const entryNames = {opening_stock:'Stock initial', production_output:'Quantité produite', opening_production_order:'Production issue du carnet initial', opening_purchase_order_receipt:'Achat initial reçu sur site', lane_receipt:'Quantité reçue', external_procurement_receipt:'Approvisionnement reçu', stock_reconciliation:'Entrée de régularisation', estimated_source_receipt:'Entrée estimée', estimated_capacity_receipt:'Entrée estimée'};
  const labels = {entered:entryNames[result.entry_type], consumed:'Consommée en fabrication', shipped:'Expédiée', served:'Affectée au service client', written_off:'Sortie en perte / rebut', pending:'Réservée, en attente de départ', remaining:'Solde au site'};
  const dates = key => {
    const d=result.dates[key];
    return d ? (d.first===d.last ? journeyDay(d.first) : journeyDay(d.first)+' à '+journeyDay(d.last)) : 'Aucun mouvement enregistré';
  };
  const figures = result.status === 'balanced' ? `<div class="journeyBalanceGrid">${Object.entries(labels).filter(([key])=>!['written_off','pending'].includes(key) || result.totals[key]>0).map(([key,label])=>
    `<div data-journey-metric="${key}" data-quantity="${result.totals[key]}"><small>${label}</small><strong>${lotTraceQtyText(result.totals[key])} ${e(lot.uom)}</strong><small>${['remaining','pending'].includes(key)?'Au dernier événement : '+journeyDay(result.last_day):dates(key)}</small></div>`).join('')}</div>
    <p data-journey-balance-status="balanced">Bilan rapproché sur ${result.event_count} événements : entrée = consommation + expédition + service client + pertes + réservation en attente + solde au site.</p>
    ${result.availability?`<p data-journey-availability data-held="${result.availability.held}" data-available="${result.availability.available}" data-physical="${result.availability.physical_onsite}">Dans le solde au site : ${lotTraceQtyText(result.availability.available)} ${e(lot.uom)} disponibles et ${lotTraceQtyText(result.availability.held)} ${e(lot.uom)} détenues non utilisables. Physique sur site, réservation comprise : ${lotTraceQtyText(result.availability.physical_onsite)} ${e(lot.uom)}. Mise en attente et libération changent la disponibilité, sans entrée ni sortie physique ; le détenu est déjà inclus dans le solde.</p>`:''}`
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

    // Read-only shipment inspection and conservative descendant scope.
let journeyOpsState = {shipment:'', impact:null, limit:50};
let journeyShipmentIndex = null;

function journeyShipments() {
  if (journeyShipmentIndex) return journeyShipmentIndex;
  const result = new Map();
  (LOT_TRACE.events || []).forEach(row => {
    if (!row.shipment_id || !['lane_ship','lane_receipt','shipment_reserve'].includes(row.event_type)) return;
    if (!result.has(row.shipment_id)) result.set(row.shipment_id, []);
    result.get(row.shipment_id).push(row);
  });
  journeyShipmentIndex = result;
  return result;
}

function journeyShipmentDetail(id) {
  const events = journeyShipments().get(id) || [];
  const departures = events.filter(r=>r.event_type==='lane_ship');
  const receipts = events.filter(r=>r.event_type==='lane_receipt');
  const reservations = events.filter(r=>r.event_type==='shipment_reserve');
  const totals = new Map();
  // Reservations and receipts are not a second physical departure.
  departures.forEach(row => {
    const key=JSON.stringify([row.item_id,row.uom]);
    if (!totals.has(key)) totals.set(key,{item_id:row.item_id,uom:row.uom,quantity:0});
    totals.get(key).quantity+=Number(row.qty);
  });
  return {id,departures,receipts,reservations,totals:[...totals.values()],
    groups:(LOT_TRACE.truck_consolidation?.groups || []).filter(g=>g.shipment_ids.includes(id))};
}

function journeyShipmentHtml(id) {
  const data=journeyShipmentDetail(id), e=escapeTableHtml;
  const rows=(list,kind)=>list.map(row=>{
    const lot=lotTraceLotInfo(row.lot_id);
    const day=kind==='Départ' ? row.departure_day ?? row.day : kind==='Réception' ? row.arrival_day ?? row.day : row.day;
    return `<tr data-shipment-event="${e(row.event_id)}"><td>${kind} · ${journeyDay(day===''?row.day:day)}</td><td>${e(lot.node_id)}<br><button data-journey-focus="${e(row.lot_id)}">${e(lot.business_lot_id || row.lot_id)}</button><br>${e(row.lot_id)}</td><td>${e(row.item_id)}</td><td>${lotTraceQtyText(row.qty)} ${e(row.uom)}</td></tr>`;
  }).join('');
  const groups=data.groups.map(g=>`<article class="journeyTruckGroup" data-journey-truck-group="${e(g.id)}">
    <strong>${e(g.origin)} → ${e(g.destination)} · ${journeyDay(g.start_day)} à ${journeyDay(g.end_day)}</strong>
    <p>${e(g.id)} · ${g.truck_count!=null ? e(g.truck_count)+' chargement(s) proposé(s)' : g.estimated_truck_count!=null ? e(g.estimated_truck_count)+' camion(s) estimé(s)' : 'Nombre de camions indéterminé'}${g.estimated_pallets!=null?' · '+lotTraceQtyText(g.estimated_pallets)+' palettes estimées':g.pallets!=null?' · '+lotTraceQtyText(g.pallets)+' palettes proposées':''}.</p>
    <p>Groupe de planification complet, pouvant comprendre d’autres lots. Aucun camion réel identifié ; aucune affectation d’un lot à un camion précis n’est déduite.</p>
    ${(g.missing_dimensions || []).length?'<p>Données physiques manquantes : '+g.missing_dimensions.map(key=>e(({gross_weight_kg:'poids brut chargé',weight:'poids brut chargé',pallets:'nombre de palettes documenté',volume_m3:'volume chargé'})[key] || key)).join(', ')+'. Les estimations affichées reposent sur les hypothèses ci-dessous.</p>':''}
    ${(g.estimate_basis || []).length?'<details><summary>Sources et hypothèses de l’estimation</summary>'+g.estimate_basis.map(e).join('<br>')+'</details>':''}
    <details><summary>Expéditions du groupe (${g.shipment_ids.length})</summary>${g.shipment_ids.map(ship=>`<button data-journey-shipment-open="${e(ship)}">${e(ship)}</button>`).join(' ')}</details></article>`).join('');
  const capacity=LOT_TRACE.truck_consolidation?.capacity;
  return `<section data-journey-shipment-detail="${e(id)}"><h3>Expédition ${e(id)}</h3>
    <p>Contenu complet de l’expédition simulée, y compris les autres lots chargés. Les lignes de départ et de réception décrivent deux étapes du même flux et ne s’additionnent pas.</p>
    <p>Départs enregistrés : ${data.totals.map(t=>`${e(t.item_id)} : <strong data-journey-shipped-item="${e(t.item_id)}" data-uom="${e(t.uom)}" data-quantity="${t.quantity}">${lotTraceQtyText(t.quantity)} ${e(t.uom)}</strong>`).join(' ; ') || 'aucun départ enregistré'}.</p>
    <table><thead><tr><th>Étape / jour</th><th>Site / lot</th><th>Article</th><th>Quantité</th></tr></thead><tbody>${rows(data.departures,'Départ')}${rows(data.receipts,'Réception')}</tbody></table>
    ${!data.receipts.length?'<p>Réception non enregistrée dans l’horizon ; une date prévue ne prouve pas une arrivée.</p>':''}
    ${data.reservations.length?`<details><summary>Réservations enregistrées (${data.reservations.length}) — distinctes des départs</summary><table><tbody>${rows(data.reservations,'Réservation')}</tbody></table></details>`:''}
    <h4>Regroupement camion</h4>${capacity?`<p>Capacité de référence : ${e(capacity.max_pallets)} palettes et ${lotTraceQtyText(capacity.max_weight_kg)} kg. Les dates de simulation restent celles des mouvements.</p>`:''}
    ${LOT_TRACE.truck_consolidation?.error?`<p role="status">Regroupements camion indisponibles : incohérence détectée dans le registre de ce scénario. ${e(LOT_TRACE.truck_consolidation.error)}</p>`:groups || '<p>Aucun regroupement documenté pour cette expédition ; capacité inconnue.</p>'}</section>`;
}

function journeyImpact(targetType,targetId) {
  const context=LOT_TRACE.material_traceability || {}, lots=LOT_TRACE.lots || {};
  let seeds=[], label='';
  if (targetType==='occurrence' && lots[targetId]) {
    seeds=[targetId];label=(lots[targetId].business_lot_id || targetId)+' · '+targetId;
  } else if (targetType==='supplier_lot' && context.origins?.[targetId]) {
    const origin=context.origins[targetId];
    label=origin.manufacturer_id+' · '+origin.batch_number+' ('+(origin.status==='observed'?'documenté':'simulé')+')';
    seeds=Object.values(context.receipts || {}).filter(r=>r.origins.some(p=>p.origin_id===targetId && Number(p.quantity)>0) || (r.possible_origin_ids || []).includes(targetId)).map(r=>r.lot_id);
  }
  seeds=[...new Set(seeds)];
  if (!seeds.length) throw new Error('Aucune occurrence documentée pour cette cible.');
  const ids=[...new Set(seeds.flatMap(id=>journeyScope(id,'downstream').lot_ids))].sort();
  const productions=[], customers=[], stocks=[], unknown=[], shipments=new Set();
  ids.forEach(id=>{
    const lot=lotTraceLotInfo(id), balance=journeyLotBalance(id);
    if (lot.created_event_type==='production_output') productions.push(id);
    if (nodeById[lot.node_id]?.type==='customer') customers.push(id);
    if (balance.status!=='balanced') unknown.push(id);
    else if (balance.totals.remaining>0 || balance.totals.pending>0) stocks.push({id,remaining:balance.totals.remaining,pending:balance.totals.pending,day:balance.last_day});
    (journeyIndex().events.get(id) || []).filter(r=>['lane_ship','lane_receipt','shipment_reserve'].includes(r.event_type) && r.shipment_id).forEach(r=>shipments.add(r.shipment_id));
  });
  return {targetType,targetId,label,seeds,ids,productions,customers,stocks,unknown,shipments:[...shipments].sort()};
}

function journeyImpactHtml() {
  const impact=journeyOpsState.impact,e=escapeTableHtml;
  if (!impact) return '<p>Choisissez une occurrence ou un lot fournisseur documenté pour retrouver les fabrications, stocks et livraisons client potentiellement concernés.</p>';
  const limit=journeyOpsState.limit;
  const lotButton=id=>{const lot=lotTraceLotInfo(id);return `<button data-journey-focus="${e(id)}">${e(lot.business_lot_id || id)} · ${e(id)}</button>`;};
  const lotRows=ids=>ids.slice(0,limit).map(id=>{const lot=lotTraceLotInfo(id);return `<tr><td>${lotButton(id)}</td><td>${e(lot.node_id)} · ${e(lot.item_id)}</td><td>${journeyDay(lot.created_day)}</td><td>${lotTraceQtyText(lot.qty)} ${e(lot.uom)} au total</td></tr>`;}).join('');
  const max=Math.max(impact.seeds.length,impact.productions.length,impact.customers.length,impact.stocks.length,impact.shipments.length,impact.unknown.length);
  return `<div data-journey-impact-scope="${e(JSON.stringify(impact.ids))}" data-journey-impact-seeds="${e(JSON.stringify(impact.seeds))}">
    <h3>Impacts potentiels · ${e(impact.label)}</h3>
    <p>${impact.seeds.length} occurrence(s) de départ · ${impact.ids.length} occurrence(s) dans le périmètre · ${impact.productions.length} fabrication(s) · ${impact.customers.length} réception(s) client · ${impact.stocks.length} stock(s) ou réservation(s) restant(s).</p>
    <p>Analyse rétrospective sur tout l’horizon, par les liens physiques. Les mélanges sont inclus en entier faute d’affectation plus fine. Les quantités totales ci-dessous ne sont pas des quantités défectueuses. Aucun retard, rebut ou effet sur le service n’est recalculé.</p>
    <button data-journey-impact-clear>Effacer l’analyse</button>
    <details><summary>Occurrences de départ (${impact.seeds.length})</summary>${impact.seeds.slice(0,limit).map(lotButton).join(' ')}<p>Le diagramme suit l’occurrence sur laquelle vous naviguez ; ces listes couvrent le périmètre complet de l’analyse.</p></details>
    <details open><summary>Fabrications potentiellement concernées (${impact.productions.length})</summary><table><tbody>${lotRows(impact.productions)}</tbody></table></details>
    <details><summary>Réceptions client potentiellement concernées (${impact.customers.length})</summary><table><tbody>${lotRows(impact.customers)}</tbody></table><p>Une réception ne signifie pas que la quantité est encore chez le client ; consultez sa fiche pour le service enregistré.</p></details>
    <details><summary>Stocks et réservations restants (${impact.stocks.length})</summary><table><tbody>${impact.stocks.slice(0,limit).map(s=>{const lot=lotTraceLotInfo(s.id);return `<tr><td>${lotButton(s.id)}</td><td>${e(lot.node_id)} · ${e(lot.item_id)}</td><td>Solde : ${lotTraceQtyText(s.remaining)} ${e(lot.uom)}<br>Réservé en attente : ${lotTraceQtyText(s.pending)} ${e(lot.uom)}</td><td>Dernier événement : ${journeyDay(s.day)}</td></tr>`;}).join('')}</tbody></table><p>Soldes locaux à leur dernier événement, sans addition des unités ou des étapes successives.</p></details>
    <details><summary>Expéditions liées au périmètre (${impact.shipments.length})</summary>${impact.shipments.slice(0,limit).map(id=>`<button data-journey-shipment-open="${e(id)}">${e(id)}</button>`).join(' ')}<p>Les autres lots du même transport ou groupe camion ne deviennent pas concernés par simple cochargement.</p></details>
    ${impact.unknown.length?`<details><summary>Soldes indisponibles ou incohérents (${impact.unknown.length})</summary>${impact.unknown.slice(0,limit).map(lotButton).join(' ')}</details>`:''}
    ${max>limit?`<p>Listes limitées à ${limit} lignes chacune. <button data-journey-impact-more>Afficher 50 lignes supplémentaires</button></p>`:''}
    </div>`;
}

function journeyOperationsHtml(id) {
  const e=escapeTableHtml, ships=[...new Set((journeyIndex().events.get(id) || []).filter(r=>['lane_ship','lane_receipt','shipment_reserve'].includes(r.event_type)).map(r=>r.shipment_id).filter(Boolean))];
  const origins=Object.values(LOT_TRACE.material_traceability?.origins || {});
  return `<section class="journeyOperations" data-journey-operations-lot="${e(id)}">
    <details id="journeyTransports" ${journeyOpsState.shipment?'open':''}><summary>Transports de l’occurrence (${ships.length})</summary>
      <p>${ships.map(ship=>`<button data-journey-shipment-open="${e(ship)}">${e(ship)}</button>`).join(' ') || 'Aucune expédition identifiée pour cette occurrence.'}</p>
      ${journeyOpsState.shipment?journeyShipmentHtml(journeyOpsState.shipment)+'<button data-journey-shipment-close>Fermer le détail transport</button>':''}</details>
    <details id="journeyImpacts" ${journeyOpsState.impact?'open':''}><summary>Rechercher les impacts potentiels</summary>
      <button data-journey-impact-occurrence="${e(id)}">Analyser cette occurrence · ${e(id)}</button>
      ${origins.length?`<label>Lot fournisseur <select id="journeyOriginSelect"><option value="">Choisir une origine documentée…</option>${origins.map(o=>`<option value="${e(o.id)}">${e(o.manufacturer_id)} · ${e(o.batch_number)} · ${e(o.item_id)} (${o.status==='observed'?'documenté':'simulé'})</option>`).join('')}</select></label>`:'<p>Aucun lot fabricant renseigné : analyse possible par occurrence ; les réceptions ne sont pas regroupées sur une identité inventée.</p>'}
      ${journeyImpactHtml()}</details></section>`;
}

document.addEventListener('click',event=>{
  const ship=event.target.closest('[data-journey-shipment-open]'), impact=event.target.closest('[data-journey-impact-occurrence]');
  let target='';
  if (ship) {journeyOpsState.shipment=ship.dataset.journeyShipmentOpen;target='journeyTransports';}
  else if (impact) {journeyCaseState.expanded=[];journeyOpsState.impact=journeyImpact('occurrence',impact.dataset.journeyImpactOccurrence);journeyOpsState.limit=50;lotJourneyState.focus=impact.dataset.journeyImpactOccurrence;lotJourneyState.direction='downstream';lotJourneyState.detail='';lotJourneyState.limit=60;target='journeyImpacts';}
  else if (event.target.closest('[data-journey-impact-clear]')) {journeyOpsState.impact=null;target='journeyImpacts';}
  else if (event.target.closest('[data-journey-impact-more]')) {journeyOpsState.limit+=50;target='journeyImpacts';}
  else if (event.target.closest('[data-journey-shipment-close]')) {journeyOpsState.shipment='';target='journeyTransports';}
  if (target) {journeyExplorer.tab='operations';refreshLotJourney();document.getElementById(target)?.scrollIntoView({block:'start'});}
});
document.addEventListener('change',event=>{
  if (event.target.id!=='journeyOriginSelect' || !event.target.value) return;
  try {journeyOpsState.impact=journeyImpact('supplier_lot',event.target.value);journeyOpsState.limit=50;}
  catch (error) {
    const panel=document.getElementById('journeyImpacts');
    let message=panel.querySelector('[data-journey-impact-error]');
    if (!message) {message=document.createElement('p');message.dataset.journeyImpactError='';message.setAttribute('role','status');panel.appendChild(message);}
    message.textContent=error.message;return;
  }
  refreshLotJourney();document.getElementById('journeyImpacts')?.scrollIntoView({block:'start'});
});

// Search, inspection and date state belong only to the simplified dialog.
let journeyExplorer={day:null,tab:'summary',query:'',site:'',item:'',role:'',identity:'',from:'',to:'',offset:0,history:[],zoom:1};
let journeySearchIndex=null;

function journeySearchRows() {
  if(journeySearchIndex)return journeySearchIndex;
  const ctx=LOT_TRACE.material_traceability || {};
  journeySearchIndex=Object.values(LOT_TRACE.lots || {}).map(lot=>{
    const events=journeyIndex().events.get(lot.lot_id) || [];
    const receipts=(ctx.receipt_ids_by_lot?.[lot.lot_id] || []).map(id=>ctx.receipts[id]);
    const originIds=[...new Set(receipts.flatMap(r=>[...(r.origins || []).map(o=>o.origin_id),...(r.possible_origin_ids || [])]))];
    const origins=originIds.map(id=>ctx.origins?.[id]).filter(Boolean);
    const unitIds=receipts.flatMap(r=>(r.handling_units || []).map(u=>typeof u==='string'?u:u.id || u.handling_unit_id));
    const aliases=[lot.lot_id,lot.stock_occurrence_id,lot.stock_lot_id,lot.business_lot_id,...(lot.business_lot_ids || []),lot.item_id,lot.node_id,
      ...Object.values(lot.identity || {}).flat(),...events.flatMap(r=>[r.lot_occurrence_id,r.stock_lot_id,r.event_id,r.production_order_id,r.planned_order_id,r.handling_unit_id]),
      ...events.filter(r=>r.event_type==='lane_receipt' || (r.shipment_id && !(journeyShipments().get(r.shipment_id)||[]).some(other=>other.event_type==='lane_receipt'))).map(r=>r.shipment_id),...originIds,...origins.flatMap(o=>[o.manufacturer_id,o.batch_number]),...unitIds];
    return {lot,text:aliases.filter(v=>typeof v==='string').join('\n').toLowerCase(),role:journeyRole(lot),identity:lot.business_identity_status || ((lot.business_lot_ids || []).length>1?'mixed':lot.business_lot_id?'identified':'untraced')};
  }).sort((a,b)=>Number(a.lot.created_day)-Number(b.lot.created_day) || a.lot.lot_id.localeCompare(b.lot.lot_id));
  return journeySearchIndex;
}

function journeyFindLots() {
  const s=journeyExplorer,q=s.query.trim().toLowerCase();
  return journeySearchRows().filter(r=>(!q || r.text.includes(q)) && (!s.site || r.lot.node_id===s.site) &&
    (!s.item || r.lot.item_id===s.item) && (!s.role || r.role===s.role) && (!s.identity || r.identity===s.identity) &&
    (s.from==='' || Number(r.lot.created_day)>=Number(s.from)) && (s.to==='' || Number(r.lot.created_day)<=Number(s.to)));
}

function journeySearchHtml() {
  const e=escapeTableHtml,s=journeyExplorer,rows=journeySearchRows();
  const select=(key,label,values)=>`<label>${label}<select data-journey-filter="${key}"><option value="">Tous</option>${[...new Set(values)].filter(Boolean).sort().map(v=>`<option ${s[key]===v?'selected':''} value="${e(v)}">${e(v)}</option>`).join('')}</select></label>`;
  return `<div class="journeySearchBar"><label>Rechercher <input id="journeySearch" type="search" value="${e(s.query)}" placeholder="LOT, LOCC, STOCKLOT, PBATCH, SHIP, fabricant…" aria-label="Rechercher un lot ou une expédition"></label><details id="journeyFilters"><summary>Filtrer les occurrences</summary><div class="journeyFilters">
    ${select('site','Site',rows.map(r=>r.lot.node_id))}${select('item','Article',rows.map(r=>r.lot.item_id))}${select('role','Type',rows.map(r=>r.role))}${select('identity','Identité',rows.map(r=>r.identity))}
    <label>Création de J<input type="number" data-journey-filter="from" value="${e(s.from)}"></label><label>à J<input type="number" data-journey-filter="to" value="${e(s.to)}"></label><button data-journey-search-clear>Effacer les filtres et la recherche</button></div></details></div><div id="journeySearchResults" aria-live="polite"></div>`;
}

function journeyRenderSearch() {
  const target=document.getElementById('journeySearchResults'),s=journeyExplorer,e=escapeTableHtml;
  if(!target)return;
  if(![s.query,s.site,s.item,s.role,s.identity,s.from,s.to].some(v=>v!=='')){target.innerHTML='';return;}
  const rows=journeyFindLots(),start=Math.min(s.offset,Math.max(0,Math.floor((rows.length-1)/30)*30));s.offset=start;
  target.innerHTML=`<p>${rows.length} occurrence(s) · ${rows.length?start+1:0}–${Math.min(start+30,rows.length)} · tri par date de création. Identités partagées conservées ; stocks distincts.</p><div class="journeySearchList">${rows.slice(start,start+30).map(({lot,identity})=>`<button data-journey-focus="${e(lot.lot_id)}">${e(lot.business_lot_id || lot.lot_id)} · ${e(lot.lot_id)} · ${e(lot.item_id)} · ${e(lot.node_id)} · ${journeyDay(lot.created_day)}${identity==='mixed'?' · mélange, contient plusieurs lots métier':''}</button>`).join('')}</div>
    ${start>0?'<button data-journey-search-page="-1">Précédents</button>':''}${start+30<rows.length?'<button data-journey-search-page="1">Suivants</button>':''}`;
}

function journeyDays() {
  const scope=journeyScope(lotJourneyState.focus,lotJourneyState.direction);
  return [...new Set(scope.lot_ids.flatMap(id=>(journeyIndex().events.get(id)||[]).map(e=>Number(e.day))).filter(Number.isFinite))].sort((a,b)=>a-b);
}

function journeyDateHtml() {
  const days=journeyDays(),s=journeyExplorer,max=Math.max(days.at(-1) ?? 0,s.day ?? 0);
  return `<div class="journeyDate"><label>Date : <input id="journeyDay" type="number" min="0" max="${max}" value="${s.day===null?max:s.day}" aria-label="Jour de lecture"></label><input id="journeyDaySlider" type="range" min="0" max="${max}" value="${s.day===null?max:s.day}" aria-label="Date de lecture du parcours"><strong>${s.day===null?'Tout l’historique':'Fin de J'+s.day}</strong><button data-journey-day-step="-1">Événement précédent</button><button data-journey-day-step="1">Suivant</button><button data-journey-all-days>Tout l’historique</button></div>`;
}

function journeyPhysicalState(id) {
  const b=journeyLotBalance(id,journeyExplorer.day);
  if(b.status==='not_created')return 'À venir dans la simulation';
  if(b.status!=='balanced')return 'État non vérifiable';
  if(b.totals.remaining>0)return b.totals.pending>0?'Stock présent et réservation':'Stock présent';
  if(b.totals.pending>0)return 'Réservé, en attente de départ';
  return 'Occurrence épuisée au site';
}

function journeyIdentitiesHtml(id) {
  const lot=lotTraceLotInfo(id),e=escapeTableHtml,ctx=LOT_TRACE.material_traceability || {};
  const rows=(ctx.receipt_ids_by_lot?.[id] || []).map(key=>ctx.receipts[key]);
  const origins=[...new Set(rows.flatMap(r=>[...(r.origins||[]).map(o=>o.origin_id),...(r.possible_origin_ids||[])]))].map(key=>ctx.origins?.[key]).filter(Boolean);
  const units=[...new Set(rows.flatMap(r=>(r.handling_units||[]).map(u=>typeof u==='string'?u:u.id || u.handling_unit_id)))].filter(Boolean);
  const events=journeyIndex().events.get(id)||[], scenarios=[...new Set(events.map(r=>r.scenario_id).filter(Boolean))];
  const risks=[...new Set(rows.flatMap(r=>r.risk_event_ids||[]))];
  const replacements=events.filter(r=>r.event_type==='production_consume_reference_transition');
  const businessIds=lot.business_lot_ids?.length?lot.business_lot_ids:[lot.business_lot_id].filter(Boolean);
  const starts=journeySearchRows().filter(r=>r.lot.created_event_type!=='lane_receipt' && businessIds.includes(r.lot.business_lot_id));
  return `<section class="journeyIdentities"><h3>Identités et état métier</h3><dl>
    <dt>État physique</dt><dd>${journeyPhysicalState(id)} · ${journeyExplorer.day===null?'fin de l’historique':'fin de J'+e(journeyExplorer.day)}</dd>
    <dt>Lot métier simulé</dt><dd>${e((lot.business_lot_ids?.length?lot.business_lot_ids:[lot.business_lot_id]).filter(Boolean).join(', ') || 'Non identifié')}${lot.business_identity_status==='mixed'?' · réception mélangée':''}</dd>
    <dt>Occurrence / stock</dt><dd>${e(id)} · ${e(lot.stock_occurrence_id || 'Identifiant LOCC absent')} · ${e(lot.stock_lot_id || events.find(r=>r.stock_lot_id)?.stock_lot_id || 'Identifiant STOCKLOT absent')}</dd>
    <dt>Origine fabricant externe</dt><dd>${lot.created_event_type==='production_output'?'Cette occurrence est une fabrication simulée identifiée par son lot métier. Les origines matières se consultent en amont.':origins.length?origins.map(o=>`${e(o.manufacturer_id)} · ${e(o.batch_number)} · ${o.status==='observed'?'documenté':'simulé'} · source : ${e(o.source_reference || 'non renseignée')}`).join('<br>'):'Non documentée : aucun numéro fabricant déduit du numéro simulé.'}</dd>
    <dt>Palettes / contenants identifiés</dt><dd>${units.map(e).join(', ') || 'Non documentés. Une occurrence ou une expédition ne constitue pas une identité de palette.'}</dd>
    <dt>Qualité / péremption</dt><dd>Non documentées. Un stock présent ne prouve ni libération qualité ni absence d’incident.</dd>
    <dt>Scénario des événements</dt><dd>${e(scenarios.join(', ') || 'Non renseigné')}</dd>
    <dt>Incidents associés aux réceptions</dt><dd>${risks.map(e).join(', ') || 'Aucun identifiant associé aux réceptions de cette occurrence.'} Exposition et événements enregistrés ; aucun incident physique ajouté ici.</dd></dl>
    ${lot.created_event_type==='opening_stock'?'<p>Stock initial : historique antérieur à J0 non documenté.</p>':''}
    ${replacements.length?`<p>Remplacement de référence enregistré : ${replacements.map(r=>`${journeyDay(r.day)} · ${e(r.event_id)} · ${lotTraceQtyText(r.qty)} ${e(r.uom)}`).join(' ; ')}. Il s’agit d’une consommation, pas d’une nouvelle entrée.</p>`:''}
    ${starts.length?`<p>Repartir de l’origine du lot métier pour son bilan réseau : ${starts.map(r=>`<button data-journey-focus="${e(r.lot.lot_id)}">${e(r.lot.business_lot_id)} · ${e(r.lot.node_id)}</button>`).join(' ')}</p>`:''}
    <p>Provenance : événements et généalogie embarqués dans cette carte ; identités externes issues du registre matières quand il est renseigné. Quantités et dates sont des résultats simulés.</p></section>`;
}

function journeyRemember() {
  journeyExplorer.history.push({...lotJourneyState,day:journeyExplorer.day,depth:journeyCaseState.depth,expanded:[...journeyCaseState.expanded]});
  if(journeyExplorer.history.length>50)journeyExplorer.history.shift();
}

function journeyApplyZoom() {
  const canvas=document.querySelector('#lotJourney .journeyCanvas');
  if(canvas)canvas.style.zoom=String(journeyExplorer.zoom);
  drawJourneyEdges();
}

document.addEventListener('input',event=>{
  if(event.target.id==='journeySearch'){journeyExplorer.query=event.target.value;journeyExplorer.offset=0;journeyRenderSearch();}
});
document.addEventListener('keydown',event=>{
  if(['Enter',' '].includes(event.key) && event.target.matches('path[data-journey-shipment-open]')){event.preventDefault();event.target.dispatchEvent(new MouseEvent('click',{bubbles:true}));}
});
document.addEventListener('change',event=>{
  if(event.target.matches('[data-journey-filter]')){journeyExplorer[event.target.dataset.journeyFilter]=event.target.value;journeyExplorer.offset=0;journeyRenderSearch();}
  if(['journeyDay','journeyDaySlider'].includes(event.target.id)) {
    const n=Number(event.target.value);if(!Number.isInteger(n)||n<0){event.target.reportValidity();return;}
    if(n===journeyExplorer.day)return; // A blur during replacement can repeat change.
    journeyExplorer.day=n;refreshLotJourney();
  }
});
document.addEventListener('click',event=>{
  const tab=event.target.closest('[data-journey-tab]'),page=event.target.closest('[data-journey-search-page]'),step=event.target.closest('[data-journey-day-step]'),zoom=event.target.closest('[data-journey-zoom]');
  if(tab){journeyExplorer.tab=tab.dataset.journeyTab;refreshLotJourney();}
  else if(page){journeyExplorer.offset+=Number(page.dataset.journeySearchPage)*30;journeyRenderSearch();}
  else if(event.target.closest('[data-journey-search-clear]')){for(const k of ['query','site','item','role','identity','from','to'])journeyExplorer[k]='';journeyExplorer.offset=0;refreshLotJourney();}
  else if(step){const days=journeyDays(),now=journeyExplorer.day ?? days.at(-1),n=Number(step.dataset.journeyDayStep);journeyExplorer.day=(n<0?days.filter(d=>d<now).at(-1):days.find(d=>d>now)) ?? now;refreshLotJourney();}
  else if(event.target.closest('[data-journey-all-days]')){journeyExplorer.day=null;refreshLotJourney();}
  else if(event.target.closest('[data-journey-back]')){const state=journeyExplorer.history.pop();if(state){journeyExplorer.day=state.day;journeyCaseState.depth=state.depth;journeyCaseState.expanded=state.expanded;delete state.day;delete state.depth;delete state.expanded;lotJourneyState=state;refreshLotJourney();}}
  else if(zoom){journeyExplorer.zoom=Math.max(0.25,Math.min(2,journeyExplorer.zoom+Number(zoom.dataset.journeyZoom)));journeyApplyZoom();}
  else if(event.target.closest('[data-journey-fit]')){const c=document.querySelector('#lotJourney .journeyCanvas'),v=c?.parentElement;if(c&&v){journeyExplorer.zoom=Math.max(0.25,Math.min(1,(v.clientWidth-12)/c.scrollWidth,(v.clientHeight-12)/c.scrollHeight));journeyApplyZoom();}}
});

// Independent read-only replay of a selected occurrence, in its own unit.
// Mixed stocks retain bounds; no proportional physical allocation is invented.
function journeyNetworkBalance(root, atDay) {
  const index=journeyIndex(), reference=lotTraceLotInfo(root), ids=new Set([root]), queue=[root];
  const same=lot=>lot && lot.item_id===reference.item_id && lot.uom===reference.uom;
  for (let i=0;i<queue.length;i++) for (const link of index.children.get(queue[i]) || []) {
    if (link.link_type==='transport' && same(lotTraceLotInfo(link.child_lot_id)) && !ids.has(link.child_lot_id)) {
      ids.add(link.child_lot_id); queue.push(link.child_lot_id);
    }
  }
  const stocks=new Map(), reserved=new Map(), transit=new Map();
  const removed={consumed:{lo:0,hi:0},served:{lo:0,hi:0},written_off:{lo:0,hi:0}};
  const received={lo:0,hi:0}; // Recorded customer arrivals; repeated passages are cumulative.
  const zero=()=>({qty:0,lo:0,hi:0}), plus=(to,from)=>{to.lo+=from.lo;to.hi+=from.hi;};
  const key=(id,ship)=>id+'|'+ship, eps=0.00002;
  const take=(container,qty)=>{
    if (!container || qty<0 || qty>container.qty+eps) throw new Error('Mouvement sans stock ou départ enregistré suffisant.');
    qty=Math.min(qty,container.qty);
    const part={qty,lo:Math.max(0,container.lo-(container.qty-qty)),hi:Math.min(container.hi,qty)};
    container.lo=Math.max(0,container.lo-qty);container.hi=Math.min(container.hi,container.qty-qty);container.qty-=qty;
    return part;
  };
  const put=(map,id,part)=>{if(!map.has(id))map.set(id,zero());const c=map.get(id);c.qty+=part.qty;plus(c,part);};
  let hasAvailability = false;
  try {
    for (const id of ids) {
      const check=journeyLotBalance(id,atDay);
      if (!['balanced','not_created'].includes(check.status)) throw new Error(id+' : '+check.reason);
      hasAvailability ||= Boolean(check.availability);
    }
    const rows=(LOT_TRACE.events || []).filter(r=>ids.has(r.lot_id) && (atDay===null || Number(r.day)<=atDay))
      .map((row,order)=>({row,order})).sort((a,b)=>Number(a.row.day)-Number(b.row.day)||a.order-b.order);
    let entered=0;
    for (const {row} of rows) {
      const id=row.lot_id, type=row.event_type, qty=Number(row.qty), ship=row.shipment_id, lot=lotTraceLotInfo(id);
      if (!stocks.has(id)) {
        const balance=journeyLotBalance(id,atDay);
        if (type!==balance.entry_type) throw new Error('Entrée initiale absente.');
        const c={qty,lo:0,hi:0};
        if (id===root) {
          c.lo=c.hi=qty;entered=qty;
          if(type==='lane_receipt' && nodeById[lot.node_id]?.type==='customer')plus(received,c);
        }
        else if (type==='lane_receipt') {
          let linked=0;
          for (const link of index.parents.get(id) || []) {
            if (link.link_type!=='transport' || !ids.has(link.parent_lot_id)) continue;
            if (!link.shipment_id || link.shipment_id!==ship) throw new Error('Réception sans expédition concordante.');
            const part=take(transit.get(key(link.parent_lot_id,ship)),Number(link.parent_qty));
            plus(c,part);linked+=part.qty;
            if (nodeById[lot.node_id]?.type==='customer') plus(received,part);
          }
          if (linked>qty+eps) throw new Error('Liens entrants supérieurs à la réception.');
        }
        stocks.set(id,c);
      } else if (type==='stock_availability_hold' || type==='stock_availability_release') {
        // Usability changes only: stock quantity and its origin bounds stay put.
      } else if (type==='shipment_reserve') {
        if (!ship) throw new Error('Réservation sans expédition.');
        put(reserved,key(id,ship),take(stocks.get(id),qty));
      } else if (type==='lane_ship') {
        if (!ship) throw new Error('Départ sans expédition.');
        const reservation=reserved.get(key(id,ship));
        put(transit,key(id,ship),take(reservation || stocks.get(id),qty));
      } else if (['production_consume','production_consume_reference_transition','demand_service','writeoff','stock_writeoff'].includes(type)) {
        const category=type.startsWith('production_consume')?'consumed':type==='demand_service'?'served':'written_off';
        plus(removed[category],take(stocks.get(id),qty));
      } else throw new Error('Mouvement non pris en charge : '+type);
      if (Math.abs(stocks.get(id).qty-Number(row.qty_after))>eps) throw new Error('Solde local différent du registre.');
    }
    const totals={factory:zero(),supplier:zero(),depot:zero(),customer:zero(),other:zero(),reserved:zero(),transit:zero(),...removed};
    const locations=[];
    for (const [id,c] of stocks) {
      const lot=lotTraceLotInfo(id),type=nodeById[lot.node_id]?.type;
      const category=({factory:'factory',manufacturing:'factory',manufacturing_site:'factory',supplier_dc:'supplier',distribution_center:'depot',customer:'customer'})[type] || 'other';
      plus(totals[category],c);
      if(c.hi>eps)locations.push({lot_id:id,node_id:lot.node_id,category,lo:c.lo,hi:c.hi});
    }
    for(const [k,c] of reserved){plus(totals.reserved,c);if(c.hi>eps)locations.push({lot_id:k.split('|')[0],shipment_id:k.split('|')[1],category:'reserved',lo:c.lo,hi:c.hi});}
    for(const [k,c] of transit){plus(totals.transit,c);if(c.hi>eps)locations.push({lot_id:k.split('|')[0],shipment_id:k.split('|')[1],category:'transit',lo:c.lo,hi:c.hi});}
    Object.values(totals).forEach(c=>{c.hi=Math.min(entered,c.hi);c.lo=Math.min(entered,c.lo);});
    // Every unit is in exactly one current or terminal category. This also
    // recovers an exact cumulative service once an entire mixed stock is used.
    const categories=Object.values(totals);
    for(let pass=0;pass<categories.length;pass++) for(const c of categories) {
      const others=categories.filter(other=>other!==c);
      c.lo=Math.max(c.lo,entered-others.reduce((n,other)=>n+other.hi,0),0);
      c.hi=Math.max(0,Math.min(c.hi,entered-others.reduce((n,other)=>n+other.lo,0)));
      if(c.lo>c.hi+eps)throw new Error('Bornes incompatibles avec la conservation.');
      // Do not amplify a sub-tolerance floating residual at every pass.
      if(c.lo>c.hi)c.lo=c.hi;
    }
    const exact=Object.values(totals).every(c=>Math.abs(c.lo-c.hi)<eps);
    if(exact && Math.abs(Object.values(totals).reduce((n,c)=>n+c.lo,0)-entered)>eps) throw new Error('Bilan réseau non conservé.');
    return {status:'balanced',exact,entered,totals,received,locations,lot_ids:[...ids],day:atDay,uom:reference.uom,has_availability:hasAvailability};
  } catch(error){return {status:'unavailable',reason:error.message};}
}

function journeyNetworkHtml(id) {
  const r=journeyNetworkBalance(id,journeyExplorer.day),e=escapeTableHtml;
  if(r.status!=='balanced')return `<details class="journeyNetwork"><summary>Où est la quantité suivie ?</summary><p data-journey-network-status="unavailable">Bilan réseau indisponible : ${e(r.reason)}</p></details>`;
  const labels={factory:'Stock usine',supplier:'Stock fournisseur',depot:'Stock dépôt',customer:'Stock client',other:'Autre site',reserved:'Réservé au site',transit:'En transport',consumed:'Consommé en fabrication',served:'Service client cumulé',written_off:'Perte / rebut'};
  const text=c=>Math.abs(c.lo-c.hi)<0.00002?lotTraceQtyText(c.lo):lotTraceQtyText(c.lo)+' à '+lotTraceQtyText(c.hi);
  return `<details class="journeyNetwork" open data-journey-network-status="${r.exact?'exact':'bounds'}"><summary>Où est la quantité du point de départ ? · ${journeyExplorer.day===null?'fin de l’historique':'fin de J'+e(journeyExplorer.day)}</summary>
    <p>${e(id)} · ${lotTraceQtyText(r.entered)} ${e(r.uom)} entrées. Suivi de cette quantité par transports, jusqu’à sa consommation, son service ou sa perte. Les PF fabriqués avec une matière utilisent une autre quantité : voir le graphe.</p>
    ${r.has_availability?'<p>Les stocks par site incluent les quantités détenues non utilisables. Leur mise en attente ou libération reste au même site et ne crée aucun flux physique supplémentaire ; le détail de disponibilité figure dans la fiche du lot.</p>':''}
    <div class="journeyNetworkGrid">${Object.entries(r.totals).filter(([k,c])=>c.hi>0 || ['factory','depot','customer','transit'].includes(k)).map(([k,c])=>`<span data-network-category="${k}" data-low="${c.lo}" data-high="${c.hi}"><small>${labels[k]}</small><strong>${text(c)} ${e(r.uom)}</strong></span>`).join('')}</div>
    <p>Reçu chez les clients (cumul des passages enregistrés, distinct du stock) : <span data-network-received data-low="${r.received.lo}" data-high="${r.received.hi}">${text(r.received)} ${e(r.uom)}</span>.</p>
    ${!r.exact?'<p role="status">Attribution incertaine après mélange : bornes compatibles avec les mouvements. Les intervalles sont liés entre eux et ne doivent pas être additionnés comme des quantités exactes.</p>':''}
    <details><summary>Localiser les stocks et transports (${r.locations.length})</summary>${r.locations.map(c=>`<p><button data-journey-focus="${e(c.lot_id)}">${e(c.lot_id)}</button> · ${e(c.node_id || c.shipment_id)} · ${labels[c.category]} : ${text(c)} ${e(r.uom)} ${c.shipment_id?`<button data-journey-shipment-open="${e(c.shipment_id)}">Transport</button>`:''}</p>`).join('') || '<p>Aucune quantité restante dans les stocks ou transports suivis.</p>'}</details></details>`;
}

// Investigation files contain navigation only. Imports never write to the ledger.
let journeyCaseState={depth:null,expanded:[],message:'',busy:false};
let journeyDatasetPromise=null;

function journeyVisibleGroups(scope,layout,settings=journeyCaseState,limit=lotJourneyState.limit) {
  const adjacency=new Map(scope.lot_ids.map(id=>[id,[]]));
  scope.links.forEach(l=>{adjacency.get(l.parent_lot_id).push(l.child_lot_id);adjacency.get(l.child_lot_id).push(l.parent_lot_id);});
  const distances=new Map([[scope.root,0]]),queue=[scope.root];
  for(let i=0;i<queue.length;i++)for(const next of adjacency.get(queue[i]))if(!distances.has(next)){distances.set(next,distances.get(queue[i])+1);queue.push(next);}
  const eligible=new Set(queue.filter(id=>settings.depth===null || distances.get(id)<=settings.depth));
  // Expansion seeds are replayed in click order; a seed must already be visible.
  for(const id of settings.expanded)if(eligible.has(id))for(const next of adjacency.get(id)||[])eligible.add(next);
  const ranked=layout.groups.filter(g=>eligible.has(g.lots[0])).sort((a,b)=>distances.get(a.lots[0])-distances.get(b.lots[0]) || Number(a.lot.created_day)-Number(b.lot.created_day) || a.key.localeCompare(b.key));
  const visible=new Set(ranked.slice(0,limit).map(g=>g.id));
  return {groups:layout.groups.filter(g=>visible.has(g.id)),eligible:ranked.length};
}

function journeyCaseControls() {
  const e=escapeTableHtml;
  return `<details class="journeyCaseTools"><summary>Conserver ou partager cette enquête</summary><p>Le fichier d’enquête mémorise le lot, la date et la vue. Pour le rouvrir, utilisez une carte contenant les mêmes données.</p>
    <button data-journey-case-save>Enregistrer l’enquête</button> <label class="journeyFileLabel">Ouvrir une enquête<input id="journeyCaseFile" type="file" accept=".json,application/json"></label>
    <button data-journey-case-report>Exporter la fiche HTML</button><p>La fiche exportée est un instantané lisible et imprimable ; elle précise les limites et le périmètre du suivi.</p></details><p id="journeyCaseMessage" role="status" aria-live="polite">${e(journeyCaseState.message)}</p>`;
}

function journeyNeighbourControls(inspected) {
  return `<label>Voisinage <select id="journeyDepth">${[[null,'Tout le parcours'],[1,'1 liaison'],[2,'2 liaisons'],[3,'3 liaisons']].map(([value,label])=>`<option value="${value===null?'all':value}" ${journeyCaseState.depth===value?'selected':''}>${label}</option>`).join('')}</select></label>${journeyCaseState.depth===null?'':`<button data-journey-expand="${escapeTableHtml(inspected)}">Étendre depuis la fiche</button><small>Vue partielle ; bilan réseau et impacts sur leur périmètre complet.</small>`}`;
}

async function journeyDatasetIdentity() {
  if(!journeyDatasetPromise)journeyDatasetPromise=(async()=>{
    if(!globalThis.crypto?.subtle)throw new Error('Le navigateur ne permet pas de vérifier les données. Utilisez un navigateur récent.');
    const encoder=new TextEncoder(),hash=async value=>Array.from(new Uint8Array(await crypto.subtle.digest('SHA-256',encoder.encode(JSON.stringify(value))))).map(n=>n.toString(16).padStart(2,'0')).join('');
    const chunks=[];
    // Bound allocations while hashing; event order is part of the ledger contract.
    for(const [name,rows] of [['events',LOT_TRACE.events||[]],['genealogy',LOT_TRACE.genealogy||[]],['lots',Object.values(LOT_TRACE.lots||{})]]){
      chunks.push([name,rows.length]);
      for(let i=0;i<rows.length;i+=500)chunks.push(await hash(rows.slice(i,i+500)));
    }
    for(const [name,value] of [['materials',LOT_TRACE.material_traceability||null],['trucks',LOT_TRACE.truck_consolidation||null],['nodes',nodeById]])chunks.push([name,await hash(value)]);
    return {method:'sha256-chunks-500-v1',sha256:await hash(chunks),scenarios:[...new Set((LOT_TRACE.events||[]).map(r=>r.scenario_id||'non renseigné'))].sort()};
  })().catch(error=>{journeyDatasetPromise=null;throw error;});
  return journeyDatasetPromise;
}

function journeyCaseSnapshot() {
  const e=journeyExplorer,s=lotJourneyState;
  return {anchor:s.anchor,focus:s.focus,direction:s.direction,detail:s.detail,limit:s.limit,day:e.day,tab:e.tab,zoom:e.zoom,
    depth:journeyCaseState.depth,expanded:[...journeyCaseState.expanded],filters:Object.fromEntries(['query','site','item','role','identity','from','to','offset'].map(key=>[key,e[key]])),
    shipment:journeyOpsState.shipment,impact:journeyOpsState.impact?{type:journeyOpsState.impact.targetType,id:journeyOpsState.impact.targetId}:null};
}

async function journeyCaseDocument() {
  // Capture before awaiting the hash: continuing navigation cannot alter the saved view.
  const view=journeyCaseSnapshot(),dataset=await journeyDatasetIdentity();
  return {format:'etudecas.lot-investigation.v1',saved_at:new Date().toISOString(),dataset,view};
}

function journeyValidateCase(doc,dataset) {
  const fail=message=>{throw new Error(message);},plain=x=>x && typeof x==='object' && !Array.isArray(x);
  if(!plain(doc)||doc.format!=='etudecas.lot-investigation.v1'||!plain(doc.dataset)||!plain(doc.view))fail('Format d’enquête non reconnu.');
  if(doc.dataset.method!==dataset.method||doc.dataset.sha256!==dataset.sha256)fail('Cette enquête provient de données différentes. Ouvrez la carte d’origine ; le suivi actuel est conservé.');
  const v=doc.view,exists=id=>typeof id==='string' && Object.hasOwn(LOT_TRACE.lots,id),integer=(n,min,max)=>Number.isSafeInteger(n)&&n>=min&&n<=max;
  if(!exists(v.anchor)||!exists(v.focus)||!['upstream','downstream','both'].includes(v.direction))fail('Lot ou direction invalide.');
  const scope=journeyScope(v.focus,v.direction);
  if(typeof v.detail!=='string'||(v.detail && !scope.lot_ids.includes(v.detail)))fail('La fiche ne fait pas partie du parcours.');
  if(v.day!==null && !integer(v.day,0,10000000))fail('Jour de lecture invalide.');
  if(!integer(v.limit,1,Math.max(60,Object.keys(LOT_TRACE.lots).length+60))||!Number.isFinite(v.zoom)||v.zoom<0.25||v.zoom>2)fail('Cadrage invalide.');
  if(!['summary','identity','operations','links'].includes(v.tab)||![null,1,2,3].includes(v.depth))fail('Vue invalide.');
  if(!Array.isArray(v.expanded)||v.expanded.length>Object.keys(LOT_TRACE.lots).length||v.expanded.some(id=>!scope.lot_ids.includes(id)))fail('Voisinage invalide.');
  if(v.detail&&!journeyVisibleGroups(scope,journeyGroups(scope),v,v.limit).groups.some(g=>g.lots.includes(v.detail)))fail('La fiche inspectée est masquée par ce voisinage.');
  if(!plain(v.filters))fail('Filtres absents.');
  for(const key of ['query','site','item','role','identity','from','to'])if(typeof v.filters[key]!=='string'||v.filters[key].length>1000)fail('Filtre invalide.');
  if(!integer(v.filters.offset,0,Object.keys(LOT_TRACE.lots).length+30))fail('Page invalide.');
  for(const key of ['from','to'])if(v.filters[key]!==''&&!integer(Number(v.filters[key]),0,10000000))fail('Période de recherche invalide.');
  if(typeof v.shipment!=='string'||(v.shipment&&!journeyShipments().has(v.shipment)))fail('Expédition absente des données.');
  let impact=null;
  if(v.impact!==null){if(!plain(v.impact)||!['occurrence','supplier_lot'].includes(v.impact.type)||typeof v.impact.id!=='string')fail('Cible d’impact invalide.');impact=journeyImpact(v.impact.type,v.impact.id);}
  return {view:JSON.parse(JSON.stringify(v)),impact};
}

async function journeyRestoreCase(doc) {
  const validated=journeyValidateCase(doc,await journeyDatasetIdentity()),v=validated.view;
  // Commit only after all validation, including recomputation of an optional impact.
  lotJourneyState={anchor:v.anchor,focus:v.focus,direction:v.direction,detail:v.detail,limit:v.limit};
  Object.assign(journeyExplorer,Object.fromEntries(['query','site','item','role','identity','from','to','offset'].map(key=>[key,v.filters[key]])),{day:v.day,tab:v.tab,zoom:v.zoom,history:[]});
  Object.assign(journeyCaseState,{depth:v.depth,expanded:v.expanded});
  journeyOpsState={shipment:v.shipment,impact:validated.impact,limit:50};
  refreshLotJourney();
}

function journeyDownload(text,type,name) {
  const url=URL.createObjectURL(new Blob([text],{type})),a=document.createElement('a');
  a.href=url;a.download=name;document.body.appendChild(a);a.click();a.remove();setTimeout(()=>URL.revokeObjectURL(url),1000);
}

function journeyReportHtml(doc) {
  const v=doc.view,e=escapeTableHtml,root=lotTraceLotInfo(v.focus),inspected=lotTraceLotInfo(v.detail||v.focus);
  const scope=journeyScope(v.focus,v.direction),network=journeyNetworkBalance(v.focus,v.day),local=journeyLotBalance(inspected.lot_id,v.day);
  const range=c=>c.lo===c.hi?lotTraceQtyText(c.lo):lotTraceQtyText(c.lo)+' à '+lotTraceQtyText(c.hi);
  const categories={factory:'Stock usine',supplier:'Stock fournisseur',depot:'Stock dépôt',customer:'Stock client',other:'Autre site',reserved:'Réservation au site',transit:'Transport',consumed:'Consommation',served:'Service client cumulé',written_off:'Perte / rebut'};
  const localLabels={entered:'Entrée initiale',consumed:'Consommation',shipped:'Expédié',served:'Service client',written_off:'Perte / rebut',pending:'Réservation au site',remaining:'Solde au site'};
  const links=scope.links.map(l=>{const a=lotTraceLotInfo(l.parent_lot_id),b=lotTraceLotInfo(l.child_lot_id),d=journeyLinkDates(l);return `<tr><td>${e(l.parent_lot_id)} · ${e(a.node_id)}</td><td>${e(l.child_lot_id)} · ${e(b.node_id)}</td><td>${e(l.link_type==='production'?'Fabrication':l.shipment_id||'Transport sans numéro')}</td><td>${l.link_type==='production'?journeyDay(l.day):journeyDay(d.departure)+' → '+journeyDay(d.arrival)}</td><td>${lotTraceQtyText(l.parent_qty)} ${e(a.uom)} de ${e(a.item_id)}</td></tr>`;}).join('');
  const identities=id=>{const lot=lotTraceLotInfo(id);return `${e(id)} · ${e(lot.business_lot_ids?.join(', ')||lot.business_lot_id||'Identité métier inconnue')} · ${e(lot.node_id)} · ${e(lot.item_id)}`;};
  const title='Enquête de lot · '+(root.business_lot_id||v.focus);
  return `<!doctype html><html lang="fr"><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>${e(title)}</title><style>body{font:15px system-ui;color:#183247;max-width:1100px;margin:32px auto;padding:0 20px}p{line-height:1.5}table{border-collapse:collapse;width:100%;font-size:13px}th,td{border:1px solid #ccd8e2;padding:8px;text-align:left;overflow-wrap:anywhere}h2{margin-top:30px}code{overflow-wrap:anywhere}@media print{body{margin:0;max-width:none}thead{display:table-header-group}tr{break-inside:avoid}}</style>
    <h1>${e(title)}</h1><p>Scénario : ${e(doc.dataset.scenarios.join(', '))} · ${v.day===null?'Tout l’historique':'Fin de J'+e(v.day)} · Export ${e(doc.saved_at)}</p>
    <p>Point de départ : ${identities(v.focus)}.<br>Fiche inspectée : ${identities(inspected.lot_id)}.</p>
    <p>Instantané en lecture seule. Les quantités sont simulées ; une identité fabricant ou un état qualité absent n’est pas déduit de ces résultats. Cette fiche ne simule aucun nouvel incident.</p>
    <h2>Bilan de l’occurrence inspectée</h2>${local.status==='balanced'?`<table><tr><th>Mesure</th><th>Quantité · ${e(inspected.uom)}</th></tr>${Object.entries(local.totals).map(([k,n])=>`<tr><td>${localLabels[k]}</td><td>${lotTraceQtyText(n)}</td></tr>`).join('')}</table>`:`<p>${e(local.reason)}</p>`}
    <h2>Quantité du point de départ sur le réseau</h2>${network.status==='balanced'?`<table><tr><th>Situation</th><th>Quantité · ${e(root.uom)}</th></tr>${Object.entries(network.totals).map(([k,c])=>`<tr><td>${categories[k]}</td><td>${range(c)}</td></tr>`).join('')}</table><p>Cumul des réceptions client : ${range(network.received)} ${e(root.uom)}, distinct du stock restant.</p>${network.exact?'':'<p>Bornes d’attribution après mélange : intervalles liés entre eux, non additionnables comme des quantités exactes.</p>'}`:`<p>Bilan indisponible : ${e(network.reason)}</p>`}
    <h2>Liens du parcours complet (${scope.links.length})</h2><p>Sens : ${e(({upstream:'origines',downstream:'destinations',both:'les deux sens'})[v.direction])}. Historique complet, y compris après la date de lecture. Le voisinage et la limite graphique ne tronquent pas cette table. Les quantités sont celles des liens entiers, pas une allocation au seul PF suivi. La matière consommée n’est pas convertie en quantité de PF.</p>
    <table><thead><tr><th>Origine</th><th>Destination</th><th>Opération</th><th>Jour(s)</th><th>Quantité du lien</th></tr></thead><tbody>${links||'<tr><td colspan="5">Aucun lien documenté dans cette direction.</td></tr>'}</tbody></table>
    <h2>Contexte de l’enquête</h2><p>Expédition inspectée : ${e(v.shipment||'aucune')}. Cible d’impact potentielle : ${e(v.impact?v.impact.type+' · '+v.impact.id:'aucune')}. Ces sélections ne prouvent aucun défaut ni effet physique. Le détail complet des transports et impacts se consulte en rouvrant le fichier d’enquête dans la carte.</p>
    <p>Empreinte des registres, identités et contexte : <code>${e(doc.dataset.method)} · ${e(doc.dataset.sha256)}</code>. Cette empreinte identifie les données ; elle ne certifie pas leur vérité industrielle. Conservez aussi le fichier JSON d’enquête pour retrouver la vue interactive.</p></html>`;
}

function journeyCaseMessage(message) {
  journeyCaseState.message=message;
  const target=document.getElementById('journeyCaseMessage');if(target)target.textContent=message;
}

document.addEventListener('click',async event=>{
  const expand=event.target.closest('[data-journey-expand]');
  if(expand){const id=expand.dataset.journeyExpand;if(!journeyCaseState.expanded.includes(id)){journeyCaseState.expanded.push(id);lotJourneyState.limit=Math.min(Object.keys(LOT_TRACE.lots).length+60,lotJourneyState.limit+60);}refreshLotJourney();return;}
  const save=event.target.closest('[data-journey-case-save]'),report=event.target.closest('[data-journey-case-report]');
  if((!save&&!report)||journeyCaseState.busy)return;
  journeyCaseState.busy=true;journeyCaseMessage('Préparation et vérification des données…');
  try{const doc=await journeyCaseDocument(),name=doc.view.focus.replace(/[^a-zA-Z0-9_-]/g,'_');
    journeyDownload(save?JSON.stringify(doc,null,2):journeyReportHtml(doc),save?'application/json':'text/html','enquete-'+name+(save?'.json':'.html'));
    journeyCaseMessage(save?'Enquête téléchargée. Conservez-la avec la carte contenant ces données.':'Fiche HTML téléchargée : ouvrez-la pour la lire ou l’imprimer.');
  }catch(error){journeyCaseMessage(error.message);}finally{journeyCaseState.busy=false;}
});
document.addEventListener('change',async event=>{
  if(event.target.id==='journeyDepth'){journeyCaseState.depth=event.target.value==='all'?null:Number(event.target.value);journeyCaseState.expanded=[];lotJourneyState.detail='';lotJourneyState.limit=60;refreshLotJourney();return;}
  if(event.target.id!=='journeyCaseFile'||!event.target.files?.length||journeyCaseState.busy)return;
  const file=event.target.files[0];journeyCaseState.busy=true;journeyCaseMessage('Vérification de l’enquête…');
  try{if(file.size>1024*1024)throw new Error('Fichier d’enquête trop volumineux (maximum 1 Mo).');const doc=JSON.parse(await file.text());await journeyRestoreCase(doc);journeyCaseMessage('Enquête restaurée ; les données de simulation sont conservées.');}
  catch(error){journeyCaseMessage(error instanceof SyntaxError?'Fichier JSON illisible. Le suivi actuel est conservé.':error.message);}
  finally{journeyCaseState.busy=false;event.target.value='';}
});
