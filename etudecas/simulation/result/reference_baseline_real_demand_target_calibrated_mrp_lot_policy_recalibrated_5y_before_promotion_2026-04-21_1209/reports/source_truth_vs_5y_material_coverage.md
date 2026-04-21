# Source Truth vs 5Y Material Coverage

This report links workbook-derived demand and BOM requirements to the 5-year simulation outputs.

Reference data:
- `demand_PF.xlsx` for annual finished-goods demand
- `268967.xlsx`, `268191.xlsx`, `021081.xlsx` for BOM/FIA
- `Stocks_MRP.xlsx` for initial stock snapshot

Simulation data:
- `production_supplier_shipments_daily.csv`
- `mrp_trace_daily.csv`

Formula:
- `coverage_5y_source = initial_stock_xlsx / (annual_requirement_xlsx * 5)`

- Total families audited: `24`
- Active on 5y: `22`
- Suspect under source-truth 5y test: `3`

## Suspect Rows
- `001848` @ `M-1810`: coverage 5y `0.471184363341564`, bb `2.314200`, bn `0.000000`, shipped `0.000000` -> inactive despite 5y source gap
- `007923` @ `M-1810`: coverage 5y `0.947273358997849`, bb `6.171200`, bn `0.000000`, shipped `0.000000` -> inactive despite 5y source gap
- `039668` @ `M-1810`: coverage 5y `0.6331732465622654`, bb `0.077140`, bn `0.000000`, shipped `0.000000` -> inactive despite 5y source gap
