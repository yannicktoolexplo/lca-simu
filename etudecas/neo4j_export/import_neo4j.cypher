// Neo4j 5+ import script for the supply risk KG.
// Prereq: copy this whole neo4j_export/ folder into Neo4j's import directory.
// Then run this file in Neo4j Browser.

CREATE CONSTRAINT actor_id_unique IF NOT EXISTS FOR (n:Actor) REQUIRE n.actor_id IS UNIQUE;
CREATE CONSTRAINT product_id_unique IF NOT EXISTS FOR (n:Product) REQUIRE n.product_id IS UNIQUE;
CREATE CONSTRAINT org_id_unique IF NOT EXISTS FOR (n:Organization) REQUIRE n.org_id IS UNIQUE;
CREATE CONSTRAINT issue_id_unique IF NOT EXISTS FOR (n:Issue) REQUIRE n.issue_id IS UNIQUE;
CREATE CONSTRAINT zone_id_unique IF NOT EXISTS FOR (n:RiskZone) REQUIRE n.zone_id IS UNIQUE;
CREATE CONSTRAINT summary_id_unique IF NOT EXISTS FOR (n:SummaryMetric) REQUIRE n.summary_id IS UNIQUE;
CREATE CONSTRAINT link_id_unique IF NOT EXISTS FOR (n:SupplyLink) REQUIRE n.link_id IS UNIQUE;

LOAD CSV WITH HEADERS FROM 'file:///neo4j_export/nodes_actor.csv' AS row
MERGE (a:Actor {actor_id: row.actor_id})
SET a.actor_code = row.actor_code,
    a.name = row.name,
    a.role = row.role,
    a.description = row.description,
    a.layer = row.layer,
    a.location_id = row.location_id,
    a.lat = CASE row.lat WHEN '' THEN null ELSE toFloat(row.lat) END,
    a.lon = CASE row.lon WHEN '' THEN null ELSE toFloat(row.lon) END,
    a.degree_centrality = CASE row.degree_centrality WHEN '' THEN null ELSE toFloat(row.degree_centrality) END,
    a.is_placeholder = CASE row.is_placeholder WHEN 'true' THEN true ELSE false END;

LOAD CSV WITH HEADERS FROM 'file:///neo4j_export/nodes_product.csv' AS row
MERGE (p:Product {product_id: row.product_id})
SET p.product_code = row.product_code,
    p.name = row.name,
    p.degree_centrality = CASE row.degree_centrality WHEN '' THEN null ELSE toFloat(row.degree_centrality) END,
    p.bom_criticality = CASE row.bom_criticality WHEN '' THEN null ELSE toFloat(row.bom_criticality) END;

LOAD CSV WITH HEADERS FROM 'file:///neo4j_export/nodes_org.csv' AS row
MERGE (o:Organization {org_id: row.org_id})
SET o.name = row.name,
    o.layer = row.layer;

LOAD CSV WITH HEADERS FROM 'file:///neo4j_export/nodes_issue.csv' AS row
MERGE (i:Issue {issue_id: row.issue_id})
SET i.severity = row.severity,
    i.area = row.area,
    i.description = row.description;

LOAD CSV WITH HEADERS FROM 'file:///neo4j_export/nodes_zone.csv' AS row
MERGE (z:RiskZone {zone_id: row.zone_id})
SET z.zone = row.zone,
    z.zone_score = CASE row.zone_score WHEN '' THEN null ELSE toFloat(row.zone_score) END;

LOAD CSV WITH HEADERS FROM 'file:///neo4j_export/nodes_summary.csv' AS row
MERGE (s:SummaryMetric {summary_id: row.summary_id})
SET s.metric = row.metric,
    s.value = CASE row.value WHEN '' THEN null ELSE toFloat(row.value) END,
    s.details = row.details;

LOAD CSV WITH HEADERS FROM 'file:///neo4j_export/nodes_supply_link.csv' AS row
MERGE (l:SupplyLink {link_id: row.link_id})
SET l.source_actor_id = row.source_actor_id,
    l.target_actor_id = row.target_actor_id,
    l.product_id = row.product_id,
    l.zone = row.zone,
    l.material_family = row.material_family,
    l.risk_score = CASE row.risk_score WHEN '' THEN null ELSE toFloat(row.risk_score) END,
    l.risk_display = CASE row.risk_display WHEN '' THEN null ELSE toFloat(row.risk_display) END,
    l.distance_km = CASE row.distance_km WHEN '' THEN null ELSE toFloat(row.distance_km) END,
    l.sell_price = CASE row.sell_price WHEN '' THEN null ELSE toFloat(row.sell_price) END,
    l.price_base = CASE row.price_base WHEN '' THEN null ELSE toFloat(row.price_base) END,
    l.unit_price = CASE row.unit_price WHEN '' THEN null ELSE toFloat(row.unit_price) END,
    l.quantity_unit = row.quantity_unit,
    l.source_dataset = row.source_dataset;

LOAD CSV WITH HEADERS FROM 'file:///neo4j_export/rel_actor_supplies_link.csv' AS row
MATCH (a:Actor {actor_id: row.actor_id})
MATCH (l:SupplyLink {link_id: row.link_id})
MERGE (a)-[:SUPPLIES_LINK]->(l);

LOAD CSV WITH HEADERS FROM 'file:///neo4j_export/rel_link_delivers_to_actor.csv' AS row
MATCH (l:SupplyLink {link_id: row.link_id})
MATCH (a:Actor {actor_id: row.actor_id})
MERGE (l)-[:DELIVERS_TO]->(a);

LOAD CSV WITH HEADERS FROM 'file:///neo4j_export/rel_link_for_product.csv' AS row
MATCH (l:SupplyLink {link_id: row.link_id})
MATCH (p:Product {product_id: row.product_id})
MERGE (l)-[:FOR_PRODUCT]->(p);

LOAD CSV WITH HEADERS FROM 'file:///neo4j_export/rel_link_in_zone.csv' AS row
MATCH (l:SupplyLink {link_id: row.link_id})
MATCH (z:RiskZone {zone_id: row.zone_id})
MERGE (l)-[:IN_ZONE]->(z);

LOAD CSV WITH HEADERS FROM 'file:///neo4j_export/rel_actor_supplies_product.csv' AS row
MATCH (a:Actor {actor_id: row.actor_id})
MATCH (p:Product {product_id: row.product_id})
MERGE (a)-[:SUPPLIES_PRODUCT]->(p);

LOAD CSV WITH HEADERS FROM 'file:///neo4j_export/rel_product_used_by_actor.csv' AS row
MATCH (p:Product {product_id: row.product_id})
MATCH (a:Actor {actor_id: row.actor_id})
MERGE (p)-[:USED_BY]->(a);

LOAD CSV WITH HEADERS FROM 'file:///neo4j_export/rel_bom_component_of.csv' AS row
MATCH (p1:Product {product_id: row.input_product_id})
MATCH (p2:Product {product_id: row.output_product_id})
MERGE (p1)-[r:BOM_COMPONENT_OF]->(p2)
SET r.quantity = CASE row.quantity WHEN '' THEN null ELSE toFloat(row.quantity) END,
    r.quantity_unit = row.quantity_unit;

LOAD CSV WITH HEADERS FROM 'file:///neo4j_export/rel_org_operates_actor.csv' AS row
MATCH (o:Organization {org_id: row.org_id})
MATCH (a:Actor {actor_id: row.actor_id})
MERGE (o)-[:OWNS_OR_OPERATES]->(a);

LOAD CSV WITH HEADERS FROM 'file:///neo4j_export/rel_issue_impacts_link.csv' AS row
MATCH (i:Issue {issue_id: row.issue_id})
MATCH (l:SupplyLink {link_id: row.link_id})
MERGE (i)-[r:IMPACTS_LINK]->(l)
SET r.impact_score = CASE row.impact_score WHEN '' THEN null ELSE toFloat(row.impact_score) END,
    r.rank = CASE row.rank WHEN '' THEN null ELSE toInteger(row.rank) END,
    r.zone_hint = row.zone_hint;

LOAD CSV WITH HEADERS FROM 'file:///neo4j_export/rel_issue_impacts_actor.csv' AS row
MATCH (i:Issue {issue_id: row.issue_id})
MATCH (a:Actor {actor_id: row.actor_id})
MERGE (i)-[r:IMPACTS_ACTOR]->(a)
SET r.impact_score = CASE row.impact_score WHEN '' THEN null ELSE toFloat(row.impact_score) END,
    r.rank = CASE row.rank WHEN '' THEN null ELSE toInteger(row.rank) END;

LOAD CSV WITH HEADERS FROM 'file:///neo4j_export/rel_issue_impacts_product.csv' AS row
MATCH (i:Issue {issue_id: row.issue_id})
MATCH (p:Product {product_id: row.product_id})
MERGE (i)-[r:IMPACTS_PRODUCT]->(p)
SET r.impact_score = CASE row.impact_score WHEN '' THEN null ELSE toFloat(row.impact_score) END,
    r.rank = CASE row.rank WHEN '' THEN null ELSE toInteger(row.rank) END;

LOAD CSV WITH HEADERS FROM 'file:///neo4j_export/rel_summary_highlights_actor.csv' AS row
MATCH (s:SummaryMetric {summary_id: row.summary_id})
MATCH (a:Actor {actor_id: row.actor_id})
MERGE (s)-[r:HIGHLIGHTS_ACTOR]->(a)
SET r.score = CASE row.score WHEN '' THEN null ELSE toFloat(row.score) END;

// Optional direct relationship to simplify exploration in Bloom
MATCH (a:Actor)-[:SUPPLIES_LINK]->(l:SupplyLink)-[:DELIVERS_TO]->(b:Actor)
WITH a, b, max(l.risk_score) AS max_risk, max(l.risk_display) AS max_risk_display, count(l) AS links
MERGE (a)-[r:SUPPLIES]->(b)
SET r.max_risk = max_risk,
    r.max_risk_display = max_risk_display,
    r.links = links;
