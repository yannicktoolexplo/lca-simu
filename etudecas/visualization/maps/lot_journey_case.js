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
