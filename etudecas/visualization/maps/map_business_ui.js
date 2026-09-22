/* Shared reading contracts for the standalone map. No network or data mutation. */
function installBusinessDialogs() {
  const dialogs = Array.from(document.querySelectorAll('.tableModal'));
  const openers = new WeakMap();
  const states = new WeakMap();
  const focusable = dialog => Array.from(dialog.querySelectorAll(
    'button:not([disabled]), a[href], input:not([disabled]), select:not([disabled]), textarea:not([disabled]), [tabindex]:not([tabindex="-1"])'
  )).filter(el => el.getClientRects().length && !el.closest('[inert]'));
  dialogs.forEach((dialog, index) => {
    dialog.setAttribute('role', 'dialog');
    dialog.setAttribute('aria-modal', 'true');
    dialog.setAttribute('tabindex', '-1');
    const heading = dialog.querySelector('.tableModalTitle');
    if (heading) {
      if (!heading.id) heading.id = `businessDialogTitle-${index}`;
      dialog.setAttribute('aria-labelledby', heading.id);
    }
    states.set(dialog, false);
    const sync = () => {
      const visible = dialog.classList.contains('visible');
      if (states.get(dialog) === visible) return;
      states.set(dialog, visible);
      dialog.setAttribute('aria-hidden', String(!visible));
      if (visible) {
        openers.set(dialog, document.activeElement);
        const close = Array.from(dialog.querySelectorAll('button')).find(el => /fermer/i.test(el.textContent));
        (close || focusable(dialog)[0] || dialog).focus();
      } else {
        const opener = openers.get(dialog);
        if (opener && opener.isConnected && opener.getClientRects().length) opener.focus();
      }
    };
    new MutationObserver(sync).observe(dialog, {attributes: true, attributeFilter: ['class']});
    sync();
    dialog.addEventListener('keydown', event => {
      if (event.key === 'Escape') {
        event.preventDefault();
        event.stopPropagation();
        const close = Array.from(dialog.querySelectorAll('button')).find(el => /fermer/i.test(el.textContent));
        if (close) close.click(); else dialog.classList.remove('visible');
      } else if (event.key === 'Tab') {
        const controls = focusable(dialog);
        if (!controls.length) {event.preventDefault(); dialog.focus(); return;}
        const first = controls[0], last = controls[controls.length - 1];
        if (event.shiftKey && (document.activeElement === first || document.activeElement === dialog)) {
          event.preventDefault(); last.focus();
        } else if (!event.shiftKey && document.activeElement === last) {
          event.preventDefault(); first.focus();
        }
      }
    });
  });
}

function businessPlotPresentation(plot, source, container) {
  if (!plot || !source) return plot;
  // Long explanations belong in the document flow, not on the graph's title.
  const note = source.note;
  if (note) {
    const explanation = document.createElement('p');
    explanation.className = 'businessFigureNote';
    explanation.textContent = String(note).replace(/<br\s*\/?\s*>/gi, ' ').replace(/<[^>]*>/g, '');
    container.appendChild(explanation);
  }
  const layout = {...(plot.layout || {})};
  layout.annotations = (layout.annotations || []).filter(annotation => !note || annotation.text !== note);
  // Trace/lot annotations remain plotted. Only the explanatory note is moved.
  return {...plot, layout};
}

function businessBundleNavigation(asset, bundleKey, selections) {
  const levels = [];
  let current = asset, key = bundleKey || 'bundle';
  while (current && Array.isArray(current.bundle) && current.bundle.length) {
    const entries = current.bundle.filter(entry => entry && entry.asset);
    if (!entries.length) return {levels, leaf: null, key};
    let index = selections[key] ?? 0;
    if (!Object.prototype.hasOwnProperty.call(selections, key)) {
      const labelIndex = label => entries.findIndex(entry => (entry.label || '').toLowerCase() === label);
      if (key.includes(':supplier_dc:')) {
        const physical = entries.findIndex(entry => /execution|envois physiques/i.test(entry.label || ''));
        const graph = labelIndex('graph stock fournisseur');
        const preferred = key.endsWith(':incoming') ? (physical >= 0 ? physical : graph)
          : key.endsWith(':fourth') ? labelIndex('carnet') : labelIndex('nominal fournisseur');
        if (preferred >= 0) index = preferred;
      } else if (key.includes(':factory:')) {
        const capacity = labelIndex('nominal capacite');
        if (capacity >= 0) index = capacity;
      }
    }
    if (!Number.isInteger(index) || index < 0 || index >= entries.length) index = 0;
    levels.push({key, entries, index});
    const selected = entries[index];
    key = `${key}:${selected.label || index}`;
    current = selected.asset;
  }
  return {levels, leaf: current, key};
}

function businessPhysicalQuantity(value, unit, formatter) {
  if (value === null || value === undefined || value === '' || !Number.isFinite(Number(value))) return 'Non disponible';
  const number = Number(value);
  // Do not hide a physical fraction if a future regression introduces one.
  const integer = Math.abs(number - Math.round(number)) < 1e-8;
  return formatter(number, unit === 'UN' && integer ? 0 : 3);
}

function businessAggregateMaterialRow(row, years) {
  const yearly = row.yearly || {};
  const hasYearly = Object.keys(yearly).length > 0;
  const buckets = hasYearly ? years.map(year => yearly[String(year)]).filter(Boolean) : [row];
  const missingYears = hasYearly ? years.filter(year => !yearly[String(year)]) : years;
  const consecutive = years.every((year, index) => index === 0 || year === years[index - 1] + 1);
  const completeWindow = hasYearly && years.length > 0 && !missingYears.length && consecutive;
  const finite = value => value !== null && value !== undefined && value !== '' && Number.isFinite(Number(value));
  const sum = key => completeWindow && buckets.length && buckets.every(bucket => finite(bucket[key]))
    ? buckets.reduce((total, bucket) => total + Number(bucket[key]), 0) : null;
  const days = sum('days') || 0;
  const planned = sum('planned_qty');
  const delivered = sum('delivered_qty');
  const consumed = sum('consumed_qty');
  const initial = completeWindow && buckets.length && finite(buckets[0].initial_qty) ? Number(buckets[0].initial_qty) : null;
  const finalBucket = buckets[buckets.length - 1];
  const finalStock = completeWindow && finalBucket && finite(finalBucket.final_stock_qty) ? Number(finalBucket.final_stock_qty) : null;
  const sourceAvailable = completeWindow && buckets.length > 0 && buckets.every(bucket => bucket.physical_source_available === true);
  const expectedFinal = initial !== null && delivered !== null && consumed !== null
    && sum('stock_outflow_qty') !== null && sum('stock_adjustment_qty') !== null
    ? initial + delivered - consumed - sum('stock_outflow_qty') + sum('stock_adjustment_qty') : null;
  const balanceGap = expectedFinal !== null && finalStock !== null ? expectedFinal - finalStock : null;
  const tolerance = buckets.reduce((total, bucket) => total + (finite(bucket.balance_tolerance_qty) ? Math.max(0, Number(bucket.balance_tolerance_qty)) : 1e-5), 0);
  const balanceStatus = row.scope !== 'material' ? 'not_applicable'
    : !sourceAvailable || buckets.some(bucket => !['reconciled', 'mismatch'].includes(bucket.balance_status)) ? 'unavailable'
    : buckets.some(bucket => bucket.balance_status === 'mismatch') || balanceGap === null || Math.abs(balanceGap) > tolerance ? 'mismatch' : 'reconciled';
  let diagnostic = row.diagnostic || '';
  if (row.scope === 'material') {
    diagnostic = balanceStatus === 'mismatch' ? 'Écart de bilan physique à examiner'
      : balanceStatus === 'reconciled' ? 'Bilan physique rapproché'
      : 'Bilan physique non disponible / non qualifié';
    if (balanceStatus !== 'reconciled' && row.diagnostic) diagnostic += ` — ${row.diagnostic}`;
  } else {
    diagnostic = `${row.scope === 'pf' ? 'Service client' : 'Production et expéditions'} ; bilan des intrants non applicable`;
  }
  if (!buckets.length) diagnostic = 'Aucune donnée sur la période sélectionnée';
  const sourceNotes = Array.from(new Set(buckets.flatMap(bucket => Array.isArray(bucket.source_notes) ? bucket.source_notes : (bucket.source_notes ? [bucket.source_notes] : []))));
  if (!hasYearly) sourceNotes.push('Données agrégées sur l’horizon complet ; absence de ventilation annuelle.');
  if (missingYears.length) sourceNotes.push(`Années sans données : ${missingYears.join(', ')}. Aucun bilan de période complète n’est qualifié.`);
  if (!consecutive) sourceNotes.push('Les périodes disjointes ne forment pas un bilan de stock continu.');
  if (!completeWindow) diagnostic = 'Période incomplète ou disjointe : bilan non qualifié';
  const average = days > 0 && planned !== null ? planned / days : null;
  // Source safety days may be working days. Do not multiply them by a daily
  // calendar average and present that shortcut as an operational MRP target.
  const coverage = row.safety_time_calendar_days;
  const stockEquivalent = average !== null && finite(coverage) ? average * Number(coverage) : null;
  return {...row, planned_qty: planned, delivered_qty: delivered, consumed_qty: consumed,
    initial_qty: initial, final_stock_qty: finalStock, selected_days: days,
    theoretical_consumed_qty: sum('theoretical_consumed_qty'), stock_outflow_qty: sum('stock_outflow_qty'),
    stock_adjustment_qty: sum('stock_adjustment_qty'), balance_gap_qty: balanceGap,
    balance_expected_final_qty: expectedFinal, balance_tolerance_qty: tolerance, window_complete: completeWindow, missing_years: missingYears,
    balance_status: balanceStatus, physical_source_available: sourceAvailable, source_notes: sourceNotes,
    avg_daily_need_qty: average, stock_equiv_safety_time_qty: stockEquivalent,
    gap_vs_need_qty: planned !== null && (row.scope === 'pf' ? delivered : consumed) !== null
      ? (row.scope === 'pf' ? delivered : consumed) - planned : null, diagnostic};
}

function businessComparableCostSelection(scenarios, reference) {
  // A partial subtotal cannot rank complete economic exposures. Coverage must
  // be explicit for every compared scenario, including the reference.
  const eligible = scenario => {
    const kpis = scenario && scenario.kpis || {};
    return kpis.valuation_complete === true && kpis.monetary_comparison_eligible === true
      && typeof kpis.economic_exposure === 'number' && Number.isFinite(kpis.economic_exposure);
  };
  if (!scenarios.length || !eligible(reference) || !scenarios.every(eligible)) return null;
  return scenarios.reduce((best, item) => Number(item.kpis.economic_exposure) < Number(best.kpis.economic_exposure) ? item : best);
}

function businessMaterialProof(row, escape, format) {
  const notes = Array.isArray(row.source_notes) ? row.source_notes.join(' ; ') : (row.source_notes || '');
  const physical = value => businessPhysicalQuantity(value, row.unit, format);
  const lines = [
    ['Périmètre', `${row.node_label || row.node_id || ''} / ${row.item_id || ''} / ${row.selected_days ?? row.days ?? '?'} jours couverts`],
    ['Source physique', row.physical_source_available ? 'Registre des événements de la simulation' : 'Source physique non disponible : bilan non qualifié'],
    ['Stock à l’ouverture', physical(row.initial_qty)],
    ['Réceptions / service client', physical(row.delivered_qty)],
    ['Consommation physique', physical(row.consumed_qty)],
    ['Autres sorties', physical(row.stock_outflow_qty)],
    ['Ajustements de stock', physical(row.stock_adjustment_qty)],
    ['Stock à la clôture', physical(row.final_stock_qty)],
    ['Écart de bilan', physical(row.balance_gap_qty)],
    ['Consommation théorique BOM', row.theoretical_consumed_qty == null ? 'Non disponible' : format(row.theoretical_consumed_qty, 3)],
    ['Convention', 'UN : mouvements physiques entiers ; prévisions potentiellement fractionnaires.'],
    ['Provenance et limites', notes || 'Lire le manifeste et le registre du calcul.'],
  ];
  if (row.scope !== 'material') {
    lines.splice(1, 8, ['Lecture', row.scope === 'pf' ? 'Demande client et quantités servies ; cette ligne n’est pas un bilan matière.' : 'Production et expéditions ; cette ligne n’est pas un bilan des intrants.']);
  }
  return `<details class="businessMaterialProof"><summary>Pourquoi ces chiffres ?</summary><dl>${lines.map(([key, value]) => `<dt>${escape(key)}</dt><dd>${escape(String(value))}</dd>`).join('')}</dl></details>`;
}
