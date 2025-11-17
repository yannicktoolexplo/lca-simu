
import random, math, csv
import simpy
from collections import defaultdict
from config_supply import (DEFAULT_RANDOM_SEED, PROCESSING_TIME_DAYS, ROLE_CAPACITY,
                           SPEEDS_KMPH, INTERCONTINENTAL_MODE, PROCESSING_JITTER,
                           TRANSIT_JITTER, TRANSPORT_OVERRIDE, DEFAULT_UNITS_PER_COMPONENT,
                           SIM_HORIZON_DAYS, EVENTS_CSV, ARRIVALS_CSV)

def same_continent(lat1, lon1, lat2, lon2):
    def haversine_km(a1, o1, a2, o2):
        R = 6371.0
        import math
        phi1 = math.radians(a1); phi2 = math.radians(a2)
        dphi = math.radians(a2-a1); dlambda = math.radians(o2-o1)
        A = (math.sin(dphi/2)**2 + math.cos(phi1)*math.cos(phi2)*math.sin(dlambda/2)**2)
        C = 2*math.atan2(math.sqrt(A), math.sqrt(1-A))
        return R*C
    return haversine_km(lat1, lon1, lat2, lon2) <= 4000.0

def pick_mode(src_node, dst_node):
    pair = (src_node["name"], dst_node["name"])
    if pair in TRANSPORT_OVERRIDE:
        return TRANSPORT_OVERRIDE[pair]
    if same_continent(src_node["lat"], src_node["lon"], dst_node["lat"], dst_node["lon"]):
        return "road"
    return INTERCONTINENTAL_MODE

def jitter(val, coeff):
    if val <= 0: 
        return val
    r = (random.random()*2 - 1) * coeff
    return max(0.0, val * (1 + r))

def simulate_supply(env, nodes, edges, demands, writer):
    random.seed(DEFAULT_RANDOM_SEED)
    resources = {}
    for key, nd in nodes.items():
        role = nd["role"]
        cap = ROLE_CAPACITY.get(role, 5)
        resources[key] = simpy.Resource(env, capacity=cap)

    arrivals = []
    role_rank = {"Matière 1ère": 0, "1ère transformation": 1, "Tier 1": 2, "Client": 3}
    comp_paths = defaultdict(list)
    for (a,b,dist,comp) in edges:
        comp_paths[comp].append((a,b,dist))

    def process_unit(component, unit_id):
        path = comp_paths.get(component, [])
        if not path:
            writer.writerow([env.now, "NO_PATH", component, unit_id, "", "", 0.0, 0.0])
            arrivals.append((component, unit_id, env.now))
            return
        involved = set()
        for (s,t,_) in path:
            involved.add(s); involved.add(t)
        seq = sorted(list(involved), key=lambda k: role_rank.get(nodes[k]["role"], 99))
        node_pairs = []
        for i in range(len(seq)-1):
            node_pairs.append((seq[i], seq[i+1]))
        if nodes[seq[-1]]["role"] != "Client":
            for (s,t,dist) in path:
                if nodes[t]["role"] == "Client" and (s,t) not in node_pairs:
                    node_pairs.append((s,t))

        for (s, t) in node_pairs:
            src = nodes[s]; dst = nodes[t]
            proc_days = PROCESSING_TIME_DAYS.get(src["role"], 1.0)
            proc_days = jitter(proc_days, PROCESSING_JITTER)
            with resources[s].request() as req:
                yield req
                writer.writerow([env.now, "START_PROC", component, unit_id, src["name"], src["role"], 0.0, 0.0])
                yield env.timeout(proc_days)
                writer.writerow([env.now, "END_PROC", component, unit_id, src["name"], src["role"], 0.0, 0.0])

            dist_km = None
            for (aa,bb,dd) in path:
                if aa==s and bb==t:
                    dist_km = dd; break
            if dist_km is None:
                def hav(lat1, lon1, lat2, lon2):
                    R = 6371.0
                    import math
                    phi1 = math.radians(lat1); phi2 = math.radians(lat2)
                    dphi = math.radians(lat2-lat1); dlambda = math.radians(lon2-lon1)
                    a = (math.sin(dphi/2)**2 + math.cos(phi1)*math.cos(phi2)*math.sin(dlambda/2)**2)
                    c = 2*math.atan2(math.sqrt(a), math.sqrt(1-a))
                    return R*c
                dist_km = hav(src["lat"], src["lon"], dst["lat"], dst["lon"])

            mode = pick_mode(src, dst)
            speed = SPEEDS_KMPH.get(mode, 60)
            hours = dist_km / max(speed, 1e-6)
            days = hours / 24.0
            days = jitter(days, TRANSIT_JITTER)

            writer.writerow([env.now, f"DEPART_{mode.upper()}", component, unit_id, f"{src['name']}→{dst['name']}", mode, dist_km, speed])
            yield env.timeout(days)
            writer.writerow([env.now, "ARRIVE", component, unit_id, dst["name"], dst["role"], dist_km, speed])

        arrivals.append((component, unit_id, env.now))

    def driver():
        for comp, qty in demands.items():
            for u in range(1, qty+1):
                env.process(process_unit(comp, u))
        yield env.timeout(SIM_HORIZON_DAYS)

    env.process(driver())
    return arrivals
