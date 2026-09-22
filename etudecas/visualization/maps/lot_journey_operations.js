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
