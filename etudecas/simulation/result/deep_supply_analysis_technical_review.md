# Relecture technique du rapport supply

Date: 2026-03-05 (UTC)

## Perimetre
Cette note relit techniquement les resultats consolides de:
- `etudecas/simulation/result/deep_supply_analysis.md`
- `etudecas/simulation/result/full_system_exploration_summary.json`
- `etudecas/simulation/sensibility/result/sensitivity_summary.json`
- `etudecas/simulation/sensibility/shock_campaign_result/shock_campaign_summary.json`
- `etudecas/simulation/result/first_simulation_summary.json`

## 1) Vocabulaire et definitions (validation)
- `fill_rate` (ici): service cumule sur 30 jours = `total_served / total_demand`.
  - Baseline: `0.945418 = 1418.1264 / 1500.0`.
- `ending_backlog`: demande non servie a la fin de l'horizon.
  - Baseline: `81.8736`.
- `total_cost`: somme `holding + transport + purchase`.
  - Baseline: `28723.7188 = 21768.5663 + 3950.9269 + 3004.2256`.
- `p95` delai: 95% des expeditions ont un delai <= p95.
  - Courant: `p95 = 16j` (max `26j`).

## 2) Coherence interne des chiffres

### 2.1 Ce qui est coherent
- Fill rate eleve avec backlog non nul: coherent (`0.945` avec backlog `81.9`).
- Distribution de delai a queue longue: moyenne `7.927j`, mediane `7j`, p95 `16j`, max `26j`.

### 2.2 Points a surveiller
- Appro externe encore tres importante: ordered `53342.6`, arrived `49150.0`, rejected `19998.7`.
- Dans l'exploration large, certaines zones donnent backlog et cout tres eleves (voir pire cas plus bas).

## 3) Ce que les resultats disent du systeme

### 3.1 Baseline
- Baseline performante, avec cout plus credibles apres recalibrage:
  - holding `0.758`, transport `0.138`, purchase `0.105`.

### 3.2 Sensibilite OAT
- Fill: `supplier_stock_scale` (+0.260), `lead_time_scale` (-0.209), `demand_item_scale::item:268091` (-0.183), `demand_item_scale::item:268967` (-0.174), `capacity_node_scale::M-1810` (+0.142)
- Backlog: `supplier_stock_scale` (-4.512), `demand_item_scale::item:268091` (+3.970), `demand_item_scale::item:268967` (+3.835), `lead_time_scale` (+3.622), `capacity_node_scale::M-1810` (-2.455)
- Cout: `capacity_node_scale::M-1430` (+0.921), `lead_time_scale` (+0.509), `demand_item_scale::item:268967` (-0.149), `transport_cost_scale` (+0.138), `supplier_stock_scale` (+0.073)

### 3.3 Exploration globale elargie
- Runs: `757` (baseline `1`, corners `256`, random `500`).
- Risques:
  - `P(fill < 0.90) = 0.9168`
  - `P(backlog > 100) = 0.9313`
  - `P(fill >= baseline) = 0.0555`

### 3.4 Pire cas parametre (service)
- Run: `full_run_0703`
- Fill: `0.349634` | backlog: `1195.9955` | cout: `33622.0080`
- Parametres marquants:
  - `demand_scale=1.13931`
  - `lead_time_scale=1.138736`
  - `review_period_scale=6.0`
  - `supplier_reliability_scale=0.853576`
  - `external_procurement_cost_multiplier_scale=1.631393`

## 4) Pieges d'interpretation
- Un bon fill cumule ne veut pas dire zero tension quotidienne.
- Les probabilites globales dependent du domaine teste (ici tres large).
- Pearson reste indicatif; les interactions non-lineaires restent importantes.

## 5) Recommandations prioritaires
1. Finaliser un domaine "plausible metier" pour distinguer risque realiste vs stress extrême.
2. Rejouer le `fill_rate_whatif_analysis.csv` dans le moteur actuel (fichier legacy).
3. Produire une frontiere Pareto cout/service sur les runs non-domines.
4. Ajouter une analyse d'interactions (au moins 2-way) sur les facteurs dominants.

## 6) Reponse courte a "est-ce realiste ?"
- Oui sur la dynamique (delais, revue, fiabilite, arbitrage stock/service).
- Encore a cadrer metier sur: envelope de variation plausible et role cible de l'appro externe.
