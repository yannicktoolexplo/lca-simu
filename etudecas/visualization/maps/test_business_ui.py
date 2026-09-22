"""Browser checks for quantities, evidence scope and modal keyboard behavior."""
from pathlib import Path

import pytest
from playwright.sync_api import sync_playwright


@pytest.fixture(scope="module")
def browser():
    with sync_playwright() as playwright:
        instance = playwright.chromium.launch()
        yield instance
        instance.close()


@pytest.fixture
def page(browser):
    page = browser.new_page(offline=True)
    page.add_script_tag(path=str(Path(__file__).with_name("map_business_ui.js")))
    yield page
    page.close()


def _bucket(initial=100, delivered=20, consumed=12, final=108, gap=0, status="reconciled"):
    return dict(days=365, planned_qty=12.5, initial_qty=initial, delivered_qty=delivered,
                consumed_qty=consumed, final_stock_qty=final, balance_gap_qty=gap,
                balance_status=status, physical_source_available=True, stock_outflow_qty=0,
                stock_adjustment_qty=0, theoretical_consumed_qty=12.5)


def test_selected_year_uses_its_opening_closing_and_movements(page):
    row = dict(scope="material", unit="UN", yearly={"1": _bucket(), "2": _bucket(108, 30, 18, 120)})
    actual = page.evaluate("row => businessAggregateMaterialRow(row, [2])", row)
    assert (actual["initial_qty"], actual["delivered_qty"], actual["consumed_qty"], actual["final_stock_qty"]) == (108, 30, 18, 120)
    assert actual["balance_expected_final_qty"] == 120
    assert actual["balance_status"] == "reconciled"
    assert actual["theoretical_consumed_qty"] == 12.5


def test_activity_or_cancelling_yearly_gaps_do_not_hide_mismatch(page):
    row = dict(scope="material", diagnostic="Écart enregistré", yearly={
        "1": _bucket(gap=2, status="mismatch"), "2": _bucket(gap=-2, status="mismatch")})
    actual = page.evaluate("row => businessAggregateMaterialRow(row, [1, 2])", row)
    assert actual["balance_status"] == "mismatch"
    assert "examiner" in actual["diagnostic"]
    assert "Écart enregistré" in actual["diagnostic"]


def test_missing_physical_source_and_empty_window_are_not_zero_or_qualified(page):
    bucket = _bucket()
    bucket.update(delivered_qty=None, physical_source_available=False, balance_status="unavailable")
    row = dict(scope="material", yearly={"1": bucket})
    actual = page.evaluate("row => businessAggregateMaterialRow(row, [1])", row)
    assert actual["delivered_qty"] is None
    assert actual["balance_status"] == "unavailable"
    empty = page.evaluate("row => businessAggregateMaterialRow(row, [2])", row)
    assert empty["consumed_qty"] is None
    assert empty["selected_days"] == 0


def test_working_days_are_not_multiplied_by_calendar_daily_average(page):
    row = dict(scope="material", safety_time_days=5, yearly={"1": _bucket()})
    actual = page.evaluate("row => businessAggregateMaterialRow(row, [1])", row)
    assert actual["stock_equiv_safety_time_qty"] is None


def test_missing_middle_year_cannot_form_reconciled_continuous_balance(page):
    row = dict(scope="material", days=1095, yearly={"1": _bucket(), "3": _bucket(200, 30, 18, 212)})
    actual = page.evaluate("row => businessAggregateMaterialRow(row, [1, 2, 3])", row)
    assert actual["balance_status"] == "unavailable"
    assert actual["missing_years"] == [2]
    assert actual["balance_expected_final_qty"] is None
    assert actual["delivered_qty"] is None
    assert "non qualifié" in actual["diagnostic"]


def test_inconsistent_year_boundaries_are_not_hidden_by_individual_year_balances(page):
    row = dict(scope="material", yearly={"1": _bucket(), "2": _bucket(200, 30, 18, 212)})
    actual = page.evaluate("row => businessAggregateMaterialRow(row, [1, 2])", row)
    assert actual["balance_status"] == "mismatch"
    assert actual["balance_gap_qty"] == -92


def test_physical_formatter_distinguishes_unknown_integer_and_bad_fraction(page):
    result = page.evaluate("""() => {
      const format = (number, digits) => number.toFixed(digits);
      return [null, 100, 100.25].map(value => businessPhysicalQuantity(value, 'UN', format));
    }""")
    assert result == ["Non disponible", "100", "100.250"]


def test_modal_traps_tab_closes_escape_and_returns_focus(page):
    page.set_content('''<style>.tableModal{display:none}.tableModal.visible{display:block}</style>
      <button id="open">Ouvrir</button><a href="#" id="behind">Page</a>
      <div id="modal" class="tableModal"><div class="tableModalTitle">Bilan</div>
      <button id="close">Fermer</button><input id="last"></div>''')
    page.evaluate("""() => {
      document.querySelector('#open').onclick = () => document.querySelector('#modal').classList.add('visible');
      document.querySelector('#close').onclick = () => document.querySelector('#modal').classList.remove('visible');
      installBusinessDialogs();
    }""")
    page.click("#open")
    page.wait_for_function("document.activeElement.id === 'close'")
    assert page.locator("#modal").get_attribute("role") == "dialog"
    page.keyboard.press("Shift+Tab")
    assert page.evaluate("document.activeElement.id") == "last"
    page.keyboard.press("Tab")
    assert page.evaluate("document.activeElement.id") == "close"
    page.keyboard.press("Escape")
    page.wait_for_function("document.activeElement.id === 'open'")
    assert not page.locator("#modal").is_visible()


def test_explanatory_note_moves_outside_plot_but_lot_annotations_remain(page):
    result = page.evaluate("""() => {
      const host = document.createElement('div');
      const plot = businessPlotPresentation({layout:{annotations:[{text:'Explication'}, {text:'LOT-1'}]}, data:[]}, {note:'Explication'}, host);
      return {annotations:plot.layout.annotations, explanation:host.textContent};
    }""")
    assert result == {"annotations": [{"text": "LOT-1"}], "explanation": "Explication"}


def test_nested_navigation_reaches_every_unit_beyond_two_levels(page):
    result = page.evaluate("""() => {
      const unit = {bundle:[{label:'UN',asset:{figure:{quantity_unit:'UN'}}}, {label:'KG',asset:{figure:{quantity_unit:'KG'}}}]};
      const asset = {bundle:[{label:'MRP',asset:{bundle:[{label:'Stocks',asset:unit}, {label:'Ordres',asset:unit}]}}]};
      const navigation = businessBundleNavigation(asset, 'factory:incoming', {'factory:incoming:MRP':1, 'factory:incoming:MRP:Ordres':1});
      return {depth:navigation.levels.length, unit:navigation.leaf.figure.quantity_unit};
    }""")
    assert result == {"depth": 3, "unit": "KG"}


def test_incomplete_valuation_cannot_rank_costs_and_ranking_includes_external_cost(page):
    result = page.evaluate("""() => {
      const first = {id:'first', kpis:{valuation_complete:true, monetary_comparison_eligible:true, total_cost:10, economic_exposure:110}};
      const second = {id:'second', kpis:{valuation_complete:true, monetary_comparison_eligible:true, total_cost:20, economic_exposure:20}};
      const complete = businessComparableCostSelection([first, second], first).id;
      second.kpis.valuation_complete = false;
      const partial = businessComparableCostSelection([first, second], first);
      const missing = businessComparableCostSelection([first], {kpis:{total_cost:1}});
      const invalid = ['', '  ', false, null, Infinity].map(value => {
        first.kpis.economic_exposure = value;
        return businessComparableCostSelection([first], first);
      });
      first.kpis.economic_exposure = 0;
      return {complete, partial, missing, invalid, zero:businessComparableCostSelection([first], first).id};
    }""")
    assert result == dict(complete="second", partial=None, missing=None, invalid=[None]*5, zero="first")
