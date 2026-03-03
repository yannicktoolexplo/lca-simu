// 1) Top risky supply links
MATCH (a:Actor)-[:SUPPLIES_LINK]->(l:SupplyLink)-[:DELIVERS_TO]->(b:Actor)
MATCH (l)-[:FOR_PRODUCT]->(p:Product)
RETURN l.link_id, a.actor_code AS supplier, b.actor_code AS customer, p.product_code AS product,
       l.zone AS zone, l.material_family AS material_family, l.risk_score AS risk_score, l.risk_display AS risk_display
ORDER BY l.risk_score DESC
LIMIT 25;

// 2) Issues and impacted links
MATCH (i:Issue)-[r:IMPACTS_LINK]->(l:SupplyLink)
MATCH (a:Actor)-[:SUPPLIES_LINK]->(l)-[:DELIVERS_TO]->(b:Actor)
MATCH (l)-[:FOR_PRODUCT]->(p:Product)
RETURN i.issue_id, i.severity, i.area, r.rank, r.impact_score,
       a.actor_code AS supplier, b.actor_code AS customer, p.product_code AS product, l.zone
ORDER BY i.issue_id, r.rank
LIMIT 100;

// 3) Issue drill-down by product
MATCH (i:Issue)-[r:IMPACTS_PRODUCT]->(p:Product)
RETURN i.issue_id, i.severity, i.area, p.product_code, r.impact_score, r.rank
ORDER BY i.issue_id, r.rank;

// 4) Single-source products (supply concentration)
MATCH (a:Actor)-[:SUPPLIES_LINK]->(l:SupplyLink)-[:FOR_PRODUCT]->(p:Product)
WITH p, collect(DISTINCT a.actor_code) AS suppliers, count(DISTINCT a) AS n_suppliers, max(l.risk_score) AS max_risk
WHERE n_suppliers = 1
RETURN p.product_code, suppliers[0] AS sole_supplier, max_risk
ORDER BY max_risk DESC, p.product_code;

// 5) Highest-risk inbound links by actor
MATCH (a:Actor)<-[:DELIVERS_TO]-(l:SupplyLink)
RETURN a.actor_code, a.role, count(l) AS inbound_links, max(l.risk_score) AS max_inbound_risk, avg(l.risk_score) AS avg_inbound_risk
ORDER BY max_inbound_risk DESC, avg_inbound_risk DESC
LIMIT 20;

// 6) BOM critical components linked to high-risk supply links
MATCH (input:Product)-[b:BOM_COMPONENT_OF]->(output:Product)
OPTIONAL MATCH (l:SupplyLink)-[:FOR_PRODUCT]->(input)
WITH input, output, b, max(l.risk_score) AS supply_risk
RETURN output.product_code AS output_product, input.product_code AS input_component,
       b.quantity AS bom_quantity, b.quantity_unit AS bom_unit, supply_risk
ORDER BY supply_risk DESC, b.quantity DESC
LIMIT 40;

// 7) SD reception metric and highlighted actors
MATCH (s:SummaryMetric {summary_id:'SD_RECEPTION'})-[r:HIGHLIGHTS_ACTOR]->(a:Actor)
RETURN s.metric, s.value, s.details, a.actor_code, a.role, r.score;

// 8) Zone-level view
MATCH (z:RiskZone)<-[:IN_ZONE]-(l:SupplyLink)
RETURN z.zone, z.zone_score, count(l) AS link_count, max(l.risk_score) AS max_risk, avg(l.risk_score) AS avg_risk
ORDER BY z.zone_score DESC, max_risk DESC;
