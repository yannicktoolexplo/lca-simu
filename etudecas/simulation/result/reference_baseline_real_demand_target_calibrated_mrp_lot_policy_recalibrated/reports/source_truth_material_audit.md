# Source-Truth Material Audit

## Scope

This note treats the workbooks in [donnees](C:/dev/lca-simu/etudecas/donnees) as the business source of truth:

- [demand_PF.xlsx](C:/dev/lca-simu/etudecas/donnees/demand_PF.xlsx)
- [268967.xlsx](C:/dev/lca-simu/etudecas/donnees/268967.xlsx)
- [268191.xlsx](C:/dev/lca-simu/etudecas/donnees/268191.xlsx)
- [021081.xlsx](C:/dev/lca-simu/etudecas/donnees/021081.xlsx)
- [Stocks_MRP.xlsx](C:/dev/lca-simu/etudecas/donnees/Stocks_MRP.xlsx)
- [Fournisseur.xlsx](C:/dev/lca-simu/etudecas/donnees/Fournisseur.xlsx)

The simulation graph and CSV outputs are treated as secondary artifacts used only to detect modeling gaps.

## Demand Truth

From [demand_PF.xlsx](C:/dev/lca-simu/etudecas/donnees/demand_PF.xlsx), sheet `Demande`:

- `268967`: `1,575,986 UN/an`
- `268091`: `3,576,442 UN/an`

Important note:

- these totals do **not** exactly match the current simulation CSV exports,
- so the current baseline run is not fully aligned to the demand workbook,
- and any material analysis should prioritize the XLSX totals above the run CSV totals.

## Product `268967` at `M-1430`

Source BOM: [268967.xlsx](C:/dev/lca-simu/etudecas/donnees/268967.xlsx), sheet `BOM`

Annual material requirements derived from the workbook demand:

| Component | Type | BOM ratio | Annual requirement from source demand | Initial stock at site `1430` | Coverage vs source demand | FIA suppliers |
|---|---|---|---:|---:|---:|---:|
| `038005` | MP | `17499.176 G / 1000 UN` | `27,578,456.388 G` | `37,598,532.500 G` | `1.36x` | `1` |
| `042342` | MP | `60342 UN / 1000 UN` | `95,098,147.212 UN` | `78,749,996 UN` | `0.83x` | `1` |
| `773474` | MP | `9654.718 G / 1000 UN` | `15,215,700.402 G` | `14,593,000 G` | `0.96x` | `1` |
| `333362` | Pack | `1000 UN / 1000 UN` | `1,575,986 UN` | `142,250 UN` | `0.09x` | `1` |
| `344135` | Pack | `1000 UN / 1000 UN` | `1,575,986 UN` | `0 UN` | `0.00x` | `1` |
| `708073` | Pack | `7930 G / 1000 UN` | `12,497,568.980 G` | `10,326,880 G` | `0.83x` | `1` |
| `730384` | Pack | `212 M / 1000 UN` | `334,109.032 M` | `68,387 M` | `0.20x` | `1` |
| `734545` | Pack | `8 UN / 1000 UN` | `12,607.888 UN` | `1,641 UN` | `0.13x` | `1` |

Readout:

- `268967` is structurally tight on several packaging components.
- `344135` is the clearest case: zero initial stock in the source snapshot.
- `773474` is also structurally important because its source-truth coverage is below `1x`.

## Product `268091` at `M-1810`

Source BOM: [268191.xlsx](C:/dev/lca-simu/etudecas/donnees/268191.xlsx), sheet `BOM`

Annual material requirements derived from the workbook demand:

| Component | Type | BOM ratio | Annual requirement from source demand | Initial stock at site `1810` | Coverage vs source demand | FIA suppliers |
|---|---|---|---:|---:|---:|---:|
| `001757` | MP | `1624 G / 1000 UN` | `5,808,141.808 G` | `8,499,654 G` | `1.46x` | `1` |
| `001848` | MP | `1218 G / 1000 UN` | `4,356,106.356 G` | `10,262,646 G` | `2.36x` | `2` |
| `001893` | MP | `7.714 KG / 1000 UN` | `27,588.674 KG` | `9,783.500 KG` | `0.35x` | `3` |
| `002612` | MP | `2.03 KG / 1000 UN` | `7,260.177 KG` | `153,521.637 KG` | `21.15x` | `4` |
| `016332` | MP | `487.2 G / 1000 UN` | `1,742,442.542 G` | `883,020 G` | `0.51x` | `1` |
| `029313` | MP | `40.6 G / 1000 UN` | `145,203.545 G` | `226,830 G` | `1.56x` | `1` |
| `039668` | MP | `40.6 G / 1000 UN` | `145,203.545 G` | `459,695 G` | `3.17x` | `1` |
| `049371` | MP | `1502.2 G / 1000 UN` | `5,372,531.172 G` | `4,138,930 G` | `0.77x` | `1` |
| `055703` | MP | `81.2 G / 1000 UN` | `290,407.090 G` | `569,805 G` | `1.96x` | `2` |
| `099439` | MP | `2030 G / 1000 UN` | `7,260,177.260 G` | `4,972,616 G` | `0.68x` | `1` |
| `693055` | MP | `406 G / 1000 UN` | `1,452,035.452 G` | `1,010,000 G` | `0.70x` | `1` |
| `007923` | MP | `3248 G / 1000 UN` | `11,616,283.616 G` | `55,018,980 G` | `4.74x` | `0` |
| `338928` | Pack | `1000 UN / 1000 UN` | `3,576,442 UN` | `404,065 UN` | `0.11x` | `1` |
| `338929` | Pack | `1000 UN / 1000 UN` | `3,576,442 UN` | `354,000 UN` | `0.10x` | `1` |
| `426331` | Pack | `11 UN / 1000 UN` | `39,340.862 UN` | `24,159 UN` | `0.61x` | `1` |

Readout:

- `002612` is massively over-covered in the source snapshot.
- `001893`, `016332`, `049371`, `099439`, `693055`, `338928`, `338929`, `426331` are structurally tighter from a source-truth perspective.
- `007923` is special:
  - the source BOM requires it,
  - source stock is high,
  - but there is no supplier lane in FIA, already documented in [case_data_update_report.md](C:/dev/lca-simu/etudecas/donnees/case_data_update_report.md).

## Upstream branch `268967 -> 773474 -> 021081`

Source chain:

- [268967.xlsx](C:/dev/lca-simu/etudecas/donnees/268967.xlsx): `9654.718 G of 773474 / 1000 UN of 268967`
- [021081.xlsx](C:/dev/lca-simu/etudecas/donnees/021081.xlsx): `8.94 KG of 021081 / 1000 G of 773474`

Derived from source-truth demand of `268967`:

- theoretical annual `773474` need: `15,215,700.402 G`
- theoretical annual `021081` need: `136,028.361 KG`

Source-truth stocks:

- `773474` at `1430`: `14,593,000 G`
- `021081` at `1450`: `1,142,100 KG`

Readout:

- `773474` is near-balanced structurally (`0.96x` coverage at `1430`),
- `021081` is not structurally tight at all from the source snapshot,
- so a dormant upstream supplier such as `VD0975221A` is entirely plausible in the current baseline.

## Major Modeling Gaps Detected

### 1. Demand workbook and run exports are not fully aligned

Source-truth annual demand:

- `268967`: `1,575,986`
- `268091`: `3,576,442`

Current run exports differ from that.

Implication:

- before using the run as reference for decision-making, demand ingestion should be rechecked and aligned to [demand_PF.xlsx](C:/dev/lca-simu/etudecas/donnees/demand_PF.xlsx).

### 2. `021081` MRP trace is not source-realistic

The current MRP trace for `SDC-1450 / item:021081` uses a static nominal requirement, not the actual downstream-demand-based consumption.

Implication:

- the current `bb_qty` for `021081` is not business-realistic,
- and should not be interpreted as source-truth demand propagation.

### 3. `007923` remains unresolved

The source case explicitly documents:

- `007923` is kept in the BOM,
- but no supplier lane exists in FIA.

Implication:

- this branch is still structurally under-modeled,
- even if source stock is high enough to mask the issue in baseline conditions.

## Priority Conclusions Before Further Simulations

1. The source workbooks support continuing the simulation study, but only if they remain the primary reference.
2. `268967` is especially sensitive on packaging and on `773474`.
3. `268091` is especially sensitive on `001893`, `016332`, `049371`, `099439`, `693055`, `338928`, `338929`, and `426331`.
4. `002612`, `055703`, `039668`, and `021081` are strongly buffered by source-truth starting stock in the current snapshot.
5. The current MRP trace for some transformed-input branches is not realistic enough and should be corrected before deeper resilience experiments.
