// Supplier lots are independent of receipts, stock occurrences and vehicles.
// This exploration never mutates simulation data or reports a causal delay.
let materialIncidentPreview = null;
let materialOutgoingIndex = null;

function materialScope(seedLots) {
  if (!materialOutgoingIndex) {
    materialOutgoingIndex = new Map();
    (LOT_TRACE.genealogy || []).forEach(link => {
      if (!['transport', 'production'].includes(link.link_type) || !(Number(link.parent_qty) > 0)) return;
      if (!materialOutgoingIndex.has(link.parent_lot_id)) materialOutgoingIndex.set(link.parent_lot_id, []);
      materialOutgoingIndex.get(link.parent_lot_id).push(link.child_lot_id);
    });
  }
  const reached = new Set(seedLots), queue = [...reached];
  for (let i = 0; i < queue.length; i++) {
    (materialOutgoingIndex.get(queue[i]) || []).forEach(child => {
      if (!reached.has(child)) { reached.add(child); queue.push(child); }
    });
  }
  const outputs = Object.values(LOT_TRACE.lots || {}).filter(lot =>
    reached.has(lot.lot_id) && lot.created_event_type === 'production_output').map(lot => lot.lot_id).sort();
  return {potential_lot_ids: [...reached].sort(), potential_production_lot_ids: outputs};
}

function materialPreview(targetType, targetId) {
  const context = LOT_TRACE.material_traceability || {}, receipts = Object.values(context.receipts || {});
  let selected = [];
  if (targetType === 'receipt') selected = receipts.filter(r => r.id === targetId);
  else if (targetType === 'supplier_lot') selected = receipts.filter(r => r.origins.some(p => p.origin_id === targetId) || (r.possible_origin_ids || []).includes(targetId));
  else if (targetType === 'handling_unit') selected = receipts.filter(r => r.handling_units.some(p => p.id === targetId));
  if (!selected.length) throw new Error('La cible ne correspond à aucune réception connue.');
  return {id: 'PREVIEW-' + targetId, target_type: targetType, target_id: targetId,
    label: 'Rappel hypothétique — ' + targetId, status: 'scenario_preview', kind: 'quality_recall',
    receipt_ids: selected.map(r => r.id), ...materialScope(selected.map(r => r.lot_id))};
}

function materialIncidentHtml(snapshot) {
  const context = LOT_TRACE.material_traceability || {};
  const rootId = snapshot && snapshot.lotId;
  const native = (context.incidents || []).filter(i => i.potential_lot_ids.includes(rootId));
  const incidents = materialIncidentPreview ? [materialIncidentPreview, ...native] : native;
  const e = escapeTableHtml;
  const rows = incidents.map(incident => {
    const exposed = incident.potential_lot_ids.includes(rootId);
    const state = incident.status === 'engine_recorded' ? 'Incident enregistré par le moteur' : 'Exploration hypothétique';
    const targets = incident.potential_production_lot_ids || [];
    const choices = targets.map(id => {
      const lot = LOT_TRACE.lots[id] || {};
      return `<option value="${e(id)}" ${id === rootId ? 'selected' : ''}>${e(lot.business_lot_id || id)} · ${e(lot.item_id || '')} · J${e(lot.created_day)}</option>`;
    }).join('');
    return `<div class="materialIncidentCard" data-material-incident="${e(incident.id)}">
      <strong>${e(state)} : ${e(incident.label || incident.id)}</strong>
      ${incident.day != null ? `<p>Jour de décision / détection : J${e(incident.day)}.</p>` : ''}
      ${(incident.shipment_ids || []).length ? `<p>Expéditions directement ciblées : ${incident.shipment_ids.map(e).join(', ')}.</p>` : ''}
      <p>${exposed ? 'Le lot sélectionné appartient au périmètre à examiner.' : 'Le lot sélectionné est hors de ce périmètre.'}
      ${targets.length} fabrication(s) potentiellement concernée(s) sur l’ensemble de l’horizon.</p>
      ${choices ? `<label>Examiner une fabrication <select data-material-affected-select><option value="">Choisir…</option>${choices}</select></label>` : ''}
      <p>Propagation par les liens physiques du registre. Une réception mélangeant plusieurs origines est considérée dans son ensemble faute d’affectation plus fine. Cela ne prouve ni une quantité défectueuse, ni un retard, ni une perte de service.</p>
    </div>`;
  }).join('');
  return `<strong>Incidents et exposition des lots</strong>${rows || '<p>Aucun incident enregistré ne cible le lot sélectionné. Les boutons des réceptions permettent d’explorer le périmètre d’un rappel hypothétique.</p>'}
    ${materialIncidentPreview ? '<button type="button" data-material-clear>Fermer l’exploration</button><p>Exploration seule : les stocks, dates, coûts et résultats de la simulation restent inchangés.</p>' : ''}`;
}

function updateMaterialIncidentView(snapshot) {
  const panel = document.querySelector('.lotTraceMaterialIncidents');
  if (panel) panel.innerHTML = materialIncidentHtml(snapshot);
  const context = LOT_TRACE.material_traceability || {};
  const active = materialIncidentPreview ? [materialIncidentPreview] : (context.incidents || []);
  const affected = new Set(active.flatMap(i => i.potential_lot_ids));
  if (panel) {
    panel.dataset.potentialLots = JSON.stringify([...affected].sort());
    panel.dataset.productionLots = JSON.stringify([...new Set(active.flatMap(i => i.potential_production_lot_ids))].sort());
    panel.dataset.receiptIds = JSON.stringify(materialIncidentPreview?.receipt_ids || []);
    panel.dataset.previewActive = materialIncidentPreview ? 'true' : 'false';
  }
  document.querySelectorAll('[data-material-stock-lot]').forEach(node => {
    node.classList.toggle('materialExposed', affected.has(node.dataset.materialStockLot));
  });
}

function lotTraceMaterialsHtml(snapshot, selected) {
  const context = LOT_TRACE.material_traceability;
  if (!context || !snapshot) return '';
  const e = escapeTableHtml, groups = new Map(), uses = new Map();
  // Parent quantities are physical component units. Never sum output contribution
  // quantities as if they were input units, or add factory aggregate stock.
  (selected.links || []).filter(link => link.link_type === 'production').forEach(link => {
    if (!uses.has(link.parent_lot_id)) uses.set(link.parent_lot_id, []);
    uses.get(link.parent_lot_id).push(link);
  });
  const visible = new Set((selected.lots || []).map(lot => typeof lot === 'string' ? lot : lot.lot_id));
  Object.values(context.receipts).forEach(receipt => {
    const links = uses.get(receipt.lot_id) || [];
    if (!links.length && !visible.has(receipt.lot_id)) return;
    // A supplier's replenishment is not a second factory receipt to add to the
    // material consumed. Show direct input stock and the selected source only.
    if (!links.length && receipt.lot_id !== snapshot.lotId) return;
    const key = receipt.item_id + '|' + receipt.uom;
    if (!groups.has(key)) groups.set(key, {item: receipt.item_id, uom: receipt.uom, rows: [], used: 0});
    const group = groups.get(key), used = links.reduce((sum, link) => sum + Number(link.parent_qty), 0);
    group.used += used;
    const origins = receipt.origins.map(part => {
      const origin = context.origins[part.origin_id];
      return `${e(origin.batch_number)} — fabricant ${e(origin.manufacturer_id)} (${origin.status === 'observed' ? 'documenté' : 'simulé'}) : ${lotTraceQtyText(part.quantity)} ${e(receipt.uom)}<br>
      <small>Source : ${e(origin.source_reference)}${part.basis === 'transport_genealogy' ? '<br>Lien conservé par le transport simulé' : ''}</small><br><button type="button" data-material-preview="supplier_lot" data-material-target="${e(origin.id)}">Explorer ce lot fournisseur</button>`;
    });
    if (receipt.unknown_origin_qty > 0 || !origins.length) origins.push(`<strong>Lot fournisseur inconnu</strong> : ${lotTraceQtyText(receipt.unknown_origin_qty)} ${e(receipt.uom)}`);
    if ((receipt.possible_origin_ids || []).length) origins.push('Origines possibles après mélange, quantités non attribuables : ' + receipt.possible_origin_ids.map(id => e(context.origins[id].batch_number)).join(', '));
    const containers = receipt.handling_units.map(unit => `${e(unit.kind)} ${e(unit.id)} (${unit.status === 'observed' ? 'documenté' : 'simulé'}) : ${lotTraceQtyText(unit.quantity)} ${e(receipt.uom)}<br><button type="button" data-material-preview="handling_unit" data-material-target="${e(unit.id)}">Explorer ce contenant</button>`);
    const mapped = receipt.handling_units.reduce((sum, part) => sum + Number(part.quantity), 0);
    if (!containers.length || mapped < receipt.quantity) containers.push('Contenants non renseignés' + (mapped ? ' pour le reste' : ''));
    const productions = [...new Set(links.map(link => link.child_lot_id))].map(id => {
      const lot = LOT_TRACE.lots[id] || {};
      return e(lot.business_lot_id || id);
    });
    const transportGroups = ((LOT_TRACE.truck_consolidation || {}).groups || []).filter(g => g.shipment_ids.includes(receipt.shipment_id));
    const transportText = transportGroups.map(g => `${e(g.id)} : ${g.truck_count != null ? g.truck_count + ' chargement(s) proposé(s)' : g.estimated_truck_count != null ? g.estimated_truck_count + ' camion(s) estimé(s)' : 'capacité inconnue'}`).join('<br>');
    const sourceLabel = receipt.event_type === 'opening_stock' ? 'Stock initial' : 'Réception simulée';
    group.rows.push(`<tr data-material-receipt="${e(receipt.id)}" data-material-stock-lot="${e(receipt.lot_id)}">
      <td>${e(sourceLabel)} ${e(receipt.id)}<br>J${receipt.day} · ${e(receipt.node_id)}<br>${e(receipt.supplier_ids.join(', ') || 'Origine avant réception non renseignée')}<br><small>Occurrence ${e(receipt.lot_id)}${receipt.simulated_batch_id ? '<br>Identité simulée : ' + e(receipt.simulated_batch_id) : ''}</small></td>
      <td>${origins.join('<br>')}<br><small>Statut qualité : non renseigné</small></td>
      <td>${lotTraceQtyText(receipt.quantity)} ${e(receipt.uom)}</td>
      <td><strong data-material-consumed="${used}">${lotTraceQtyText(used)} ${e(receipt.uom)}</strong><br><small>${productions.join('<br>') || 'Aucune consommation dans cette vue'}</small></td>
      <td>${containers.join('<br>')}</td>
      <td>${e(receipt.shipment_id || 'Expédition non renseignée')}<br><small>${transportText}</small></td>
      <td><button type="button" data-material-preview="receipt" data-material-target="${e(receipt.id)}">Explorer un rappel de cette réception</button></td>
    </tr>`);
  });
  const articles = [...groups.values()].sort((a, b) => a.item.localeCompare(b.item)).map(group =>
    `<details class="materialArticle" data-material-article="${e(group.item)}"><summary><strong>${e(group.item.replace('item:', ''))}</strong> · ${group.rows.length} réception(s) / stock(s) d’origine · ${lotTraceQtyText(group.used)} ${e(group.uom)} prélevées dans les fabrications affichées</summary>
    <div class="materialTableScroll"><table><thead><tr><th>Réception / stock</th><th>Lot du fabricant</th><th>Reçu / initial</th><th>Prélevé</th><th>Contenants à réception</th><th>Transport</th><th>Exploration</th></tr></thead><tbody>${group.rows.join('')}</tbody></table></div></details>`).join('');
  return `<section class="lotTraceMaterials"><details open><summary><strong>Matières, emballages et réceptions — ${groups.size} article(s)</strong></summary>
    <p>Une référence article peut avoir plusieurs réceptions et plusieurs lots fournisseurs. Les BATCH sont des identités de simulation. Les contenants documentés et les estimations camion sont distincts.</p>
    <p>« Prélevé » indique la consommation des fabrications nommées dans chaque ligne ; ce n’est pas le stock total de l’usine. Les lots fournisseurs inconnus restent séparés tant que leur origine n’est pas documentée.</p>
    ${articles || '<p>Aucune réception directement consommée dans cette direction du graphe.</p>'}</details>
    <div class="lotTraceMaterialIncidents">${materialIncidentHtml(snapshot)}</div></section>`;
}

document.addEventListener('click', event => {
  const button = event.target.closest('[data-material-preview]');
  if (button) {
    materialIncidentPreview = materialPreview(button.dataset.materialPreview, button.dataset.materialTarget);
    updateMaterialIncidentView(selectedLotTraceSnapshot());
    document.querySelector('.lotTraceMaterialIncidents')?.scrollIntoView({block: 'nearest'});
  }
  if (event.target.closest('[data-material-clear]')) {
    materialIncidentPreview = null;
    updateMaterialIncidentView(selectedLotTraceSnapshot());
  }
});
document.addEventListener('change', event => {
  if (event.target.matches('[data-material-affected-select]') && event.target.value) {
    setSelectedLot(event.target.value);
  }
});
