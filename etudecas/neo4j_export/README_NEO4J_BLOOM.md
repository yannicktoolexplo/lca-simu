# Neo4j + Bloom Package

This folder contains a Neo4j-ready export of the supply knowledge graph enriched with:
- SD/DES diagnostics,
- link-level risk scoring,
- issue localization,
- `Data_poc.xlsx` relation and BOM enrichment.

## 1) Regenerate the export

From project root:

```bash
python export_neo4j_bloom.py \
  --graph knowledge_graph.json \
  --coords actor_coords.json \
  --report advanced_complex_full_report.json \
  --data-poc Data_poc.xlsx \
  --out-dir neo4j_export
```

## 2) Import in Neo4j

1. Copy the full `neo4j_export/` folder into Neo4j database `import/` directory.
2. Open Neo4j Browser on your database.
3. Run [import_neo4j.cypher](/workspaces/lca-simu/neo4j_export/import_neo4j.cypher).

## 3) Explore in Bloom

Recommended Perspective setup:
- Node captions:
  - `Actor`: `actor_code`
  - `Product`: `product_code`
  - `Issue`: `issue_id`
  - `SupplyLink`: `link_id`
- Node style:
  - color `Actor` by `role`
  - color `Issue` by `severity`
  - color `SupplyLink` by `risk_display` (continuous)
  - size `SupplyLink` by `risk_score`
- Relationship style:
  - emphasize `IMPACTS_LINK`, `IMPACTS_ACTOR`, `IMPACTS_PRODUCT`

## 4) Useful labels and relationships

- Labels:
  - `Actor`, `Product`, `SupplyLink`, `Issue`, `RiskZone`, `SummaryMetric`, `Organization`
- Key relationships:
  - `(:Actor)-[:SUPPLIES_LINK]->(:SupplyLink)-[:DELIVERS_TO]->(:Actor)`
  - `(:SupplyLink)-[:FOR_PRODUCT]->(:Product)`
  - `(:Issue)-[:IMPACTS_LINK|IMPACTS_ACTOR|IMPACTS_PRODUCT]->(...)`
  - `(:Product)-[:BOM_COMPONENT_OF]->(:Product)`

## 5) Ready-to-run analysis queries

Run [analysis_queries.cypher](/workspaces/lca-simu/neo4j_export/analysis_queries.cypher) in Browser.

## 6) Alternative interactive view: NeoVis.js

File:
- [neovis_demo.html](/workspaces/lca-simu/neo4j_export/neovis_demo.html)

Usage:
1. Start Neo4j DB.
2. Serve this folder locally (recommended):

```bash
cd /workspaces/lca-simu/neo4j_export
python -m http.server 8000
```

3. Open:
   - `http://localhost:8000/neovis_demo.html`
4. Fill connection:
   - URI: `bolt://localhost:7687`
   - User: `neo4j`
   - Password: your DB password
   - Database: `neo4j`
5. Click `Render`.

The page includes preset Cypher queries for:
- issue-centric risk exploration,
- supply flow exploration,
- BOM + risk exploration.
- generic graph test (`MATCH (n) OPTIONAL MATCH (n)-[r]->(m) RETURN n,r,m LIMIT 260`).

### Easiest way (one script)

Use:

```bash
cd /workspaces/lca-simu/neo4j_export
./run_neovis_easy.sh all
```

This does:
1. start Neo4j Docker container,
2. run the import script,
3. serve `neovis_demo.html` on `http://localhost:8000/neovis_demo.html`.

Neo4j default credentials used by the script:
- user: `neo4j`
- password: `test12345`
- bolt: `bolt://localhost:7687`

Useful commands:

```bash
./run_neovis_easy.sh status
./run_neovis_easy.sh up
./run_neovis_easy.sh import
./run_neovis_easy.sh serve
./run_neovis_easy.sh down
```

If script says Docker is not accessible, run with proper permissions
(e.g. add your user to Docker group, restart session, or use sudo).

If `neo4j_export` permissions become broken after Docker use:

```bash
sudo chown -R $(whoami):$(whoami) /workspaces/lca-simu/neo4j_export
chmod -R u+rwX,go+rX /workspaces/lca-simu/neo4j_export
docker rm -f neo4j-supply-local
./run_neovis_easy.sh all
```

Troubleshooting:
- If nothing appears, first switch preset to `Test générique`.
- Open browser devtools (F12) and check JS errors.
- If message says `NeoVis non charge`, your network blocks CDN JS files.
- If page is served from a remote workspace (Codespaces/remote VS Code), `bolt://localhost:7687` often points to your local machine, not the Neo4j server.
  - In that case, either:
    - run the HTML on the same machine as Neo4j, or
    - expose Neo4j endpoint publicly and use the correct URI (`neo4j+s://...`) with TLS.

## Notes

- `SupplyLink` nodes are intentional: they make Bloom exploration of link-level risk much clearer than relationship-only modeling.
- `data_poc` enrichment is partial by design because some fields are missing in source spreadsheets.
