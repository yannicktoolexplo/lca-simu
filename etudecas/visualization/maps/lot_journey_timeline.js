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
  try {
    for (const id of ids) {
      const check=journeyLotBalance(id,atDay);
      if (!['balanced','not_created'].includes(check.status)) throw new Error(id+' : '+check.reason);
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
    return {status:'balanced',exact,entered,totals,received,locations,lot_ids:[...ids],day:atDay,uom:reference.uom};
  } catch(error){return {status:'unavailable',reason:error.message};}
}

function journeyNetworkHtml(id) {
  const r=journeyNetworkBalance(id,journeyExplorer.day),e=escapeTableHtml;
  if(r.status!=='balanced')return `<details class="journeyNetwork"><summary>Où est la quantité suivie ?</summary><p data-journey-network-status="unavailable">Bilan réseau indisponible : ${e(r.reason)}</p></details>`;
  const labels={factory:'Stock usine',supplier:'Stock fournisseur',depot:'Stock dépôt',customer:'Stock client',other:'Autre site',reserved:'Réservé au site',transit:'En transport',consumed:'Consommé en fabrication',served:'Service client cumulé',written_off:'Perte / rebut'};
  const text=c=>Math.abs(c.lo-c.hi)<0.00002?lotTraceQtyText(c.lo):lotTraceQtyText(c.lo)+' à '+lotTraceQtyText(c.hi);
  return `<details class="journeyNetwork" open data-journey-network-status="${r.exact?'exact':'bounds'}"><summary>Où est la quantité du point de départ ? · ${journeyExplorer.day===null?'fin de l’historique':'fin de J'+e(journeyExplorer.day)}</summary>
    <p>${e(id)} · ${lotTraceQtyText(r.entered)} ${e(r.uom)} entrées. Suivi de cette quantité par transports, jusqu’à sa consommation, son service ou sa perte. Les PF fabriqués avec une matière utilisent une autre quantité : voir le graphe.</p>
    <div class="journeyNetworkGrid">${Object.entries(r.totals).filter(([k,c])=>c.hi>0 || ['factory','depot','customer','transit'].includes(k)).map(([k,c])=>`<span data-network-category="${k}" data-low="${c.lo}" data-high="${c.hi}"><small>${labels[k]}</small><strong>${text(c)} ${e(r.uom)}</strong></span>`).join('')}</div>
    <p>Reçu chez les clients (cumul des passages enregistrés, distinct du stock) : <span data-network-received data-low="${r.received.lo}" data-high="${r.received.hi}">${text(r.received)} ${e(r.uom)}</span>.</p>
    ${!r.exact?'<p role="status">Attribution incertaine après mélange : bornes compatibles avec les mouvements. Les intervalles sont liés entre eux et ne doivent pas être additionnés comme des quantités exactes.</p>':''}
    <details><summary>Localiser les stocks et transports (${r.locations.length})</summary>${r.locations.map(c=>`<p><button data-journey-focus="${e(c.lot_id)}">${e(c.lot_id)}</button> · ${e(c.node_id || c.shipment_id)} · ${labels[c.category]} : ${text(c)} ${e(r.uom)} ${c.shipment_id?`<button data-journey-shipment-open="${e(c.shipment_id)}">Transport</button>`:''}</p>`).join('') || '<p>Aucune quantité restante dans les stocks ou transports suivis.</p>'}</details></details>`;
}
