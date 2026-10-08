"""Translate the mass-transport comparison into monthly cohort accounting."""
from __future__ import annotations

import math
import hashlib
import json


def aircraft_use_signature(model):
    seat = model.get('lightweight_seat') or {}
    physical = {'mission': seat.get('mission'), 'indicators': seat.get('indicator_results'),
                'combustion_inventory': [r for r in model.get('exchanges', [])
                    if r.get('activity_name') == 'kerosene, production et combustion, 1tkm eq'],
                'legacy': model.get('usage_calibration') if not seat.get('mission') else None}
    return hashlib.sha256(json.dumps(physical, sort_keys=True).encode('utf-8')).hexdigest()


def refresh_production_use_rows(monthly, cumulative, profile):
    """Only recalculate lifecycle totals; production and SDD deltas stay intact."""
    lifetime = profile['full_lifetime_use_kgco2e_per_seat']
    other = profile['other_lifecycle_kgco2e_per_seat']
    running = 0.0
    running_by_month = {}
    for row in sorted(monthly, key=lambda r: float(r['month_index'])):
        volume = float(row['seat_equivalent_volume'])
        total = float(row['production_dynamic_kgco2e']) + volume * (lifetime + other)
        row.update(use_full_lifetime_kgco2e=volume*lifetime,
                   other_lifecycle_net_kgco2e=volume*other,
                   lifecycle_attributed_kgco2e=total,
                   cycle_dynamic_with_stelia_usage_kgco2e=total,
                   use_accounting_method=profile['accounting_method'],
                   legacy_cycle_field_status='name_only_alias_to_current_use_method')
        running += total
        running_by_month[int(float(row['month_index']))] = running
    for row in cumulative:
        total = running_by_month[int(float(row['month_index']))]
        row.update(lifecycle_attributed_cumulative=total,
                   cycle_dynamic_with_stelia_usage_cumulative=total,
                   use_accounting_method=profile['accounting_method'])


def build_article_use_profile(model):
    seat = model.get('lightweight_seat') or {}
    mission = seat.get('mission')
    if not mission:
        return None
    climate = next(r for r in seat['indicator_results'] if r['indicator_id'] == 'Climate Change - total')
    total = climate.get('baseline_use_raw')
    if total is None or not math.isfinite(float(total)):
        raise ValueError('Article use profile requires a finite climate LCIA factor; no STELIA fallback')
    total = float(total)
    fuel = float(mission['baseline_fuel_kg'])
    years = float(mission['lifetime_years'])
    months = round(years * 12)
    if months < 1 or not math.isclose(months, years * 12):
        raise ValueError('Cohort lifetime must be a positive whole number of months')
    norm = float(climate['normalization_factor_per_person_year'])
    production = float(climate['baseline_production_raw'])
    # Use the imported combustion inventory for decomposition, not an ICAO
    # scalar subtracted from LCIA and mislabeled as upstream emissions.
    exchanges = [r for r in model.get('exchanges', [])
                 if r.get('activity_name') == 'kerosene, production et combustion, 1tkm eq']
    kerosene = sum(float(r['amount']) for r in exchanges
                   if r.get('type') == 'technosphere' and r.get('name') == 'market for kerosene')
    carbon = sum(float(r['amount']) for r in exchanges
                 if r.get('type') == 'biosphere' and r.get('name') == 'Carbon dioxide, fossil')
    if kerosene <= 0 or carbon <= 0:
        raise ValueError('Combustion inventory unavailable; refuse fabricated decomposition')
    combustion = fuel * carbon / kerosene
    remainder = total - combustion
    components = [
        {'mechanism': 'fuel_upstream', 'label': 'Autres contributions ACV du carburant', 'full_lifetime_kgco2e': remainder},
        {'mechanism': 'inflight_mass_burden', 'label': 'CO2 de combustion - inventaire OPERA', 'full_lifetime_kgco2e': combustion},
    ]
    for row in components:
        row.update(monthly_per_active_seat_kgco2e=row['full_lifetime_kgco2e']/months,
                   full_lifetime_person_equivalent=row['full_lifetime_kgco2e']/norm,
                   calculation_status='steinegger_mass_transport_with_historical_lcia',
                   physical_amount=fuel, physical_unit='kg kerosene', confidence='modele exploratoire')
    return {
        'accounting_method': 'cohortes_mensuelles_steinegger_a322_v1',
        'functional_unit': 'Transport de la masse dun siege pendant sa duree de vie',
        'calculation_status': 'steinegger_mass_transport_with_historical_lcia',
        'mission_status': mission['status'], 'mission_warning': mission.get('warning', ''),
        'scope': 'Transport de masse; IFE, nettoyage, fin de vie et effets non-CO2 en altitude exclus',
        'lifetime_years': years, 'lifetime_months': months,
        'seat_mass_kg': mission['baseline_mass_kg'],
        'average_flight_distance_km': mission['average_flight_distance_km'],
        'annual_flight_cycles': mission['annual_flight_cycles'],
        'fuel_kg_per_seat': fuel,
        'direct_co2_icao_kg_per_seat': fuel * 3.16,
        'target_fuel_kg_per_seat': mission['target_fuel_kg'],
        'target_direct_co2_icao_kg_per_seat': mission['target_fuel_kg'] * 3.16,
        'direct_co2_opera_kg_per_seat': combustion,
        'production_kgco2e_per_seat': production,
        'other_lifecycle_kgco2e_per_seat': 0.0,
        'other_lifecycle_status': 'excluded_not_zero_impact',
        'non_use_lifecycle_kgco2e_per_seat': production,
        'full_lifetime_use_kgco2e_per_seat': total,
        'monthly_use_kgco2e_per_active_seat': total/months,
        'aligned_lifecycle_kgco2e_per_seat': total+production,
        'full_lifetime_use_person_equivalent_per_seat': total/norm,
        'normalization_factor_kgco2e_per_person_equivalent': norm,
        'fuel_upstream_kgco2e_per_seat': remainder,
        'inflight_mass_burden_kgco2e_per_seat': combustion,
        'cleaning_kgco2e_per_seat': 0.0, 'cleaning_status': 'excluded_not_zero_impact',
        'components': components,
    }
