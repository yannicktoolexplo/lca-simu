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
