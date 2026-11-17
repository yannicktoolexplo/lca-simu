"""Explicit recurring factory workdays, independent of planning allowances."""
from datetime import date, timedelta


def resolve_manufacturing_work_calendar(payload, *, nodes, produced_pairs,
                                        origin_date, through_day):
    """Expand a calendar known at J0 through the whole bounded planning support.

    This is a declared resource assumption, not observed future production.
    Factory shutdowns, quality calendars and tau remain separate contracts.
    """
    if payload is None:
        return {}
    if (not isinstance(payload, dict) or type(payload.get("schema_version")) is not int
            or payload["schema_version"] != 1
            or not isinstance(payload.get("rows"), list) or not payload["rows"]
            or type(through_day) is not int or through_day < 0):
        raise ValueError("Work calendar requires schema1, explicit rows and a bounded horizon")
    origin = date.fromisoformat(origin_date)
    factories = {str(n.get("id")) for n in nodes if n.get("type") == "factory"}
    seen, result = set(), {}
    for row in payload["rows"]:
        if not isinstance(row, dict):
            raise ValueError("Work calendar rows must be objects")
        node, weekdays = row.get("node_id"), row.get("working_weekdays")
        if (node not in factories or node in seen
                or not any(p[0] == node for p in produced_pairs)
                or type(row.get("known_day")) is not int or row["known_day"] > 0
                or not isinstance(row.get("provenance"), str) or not row["provenance"].strip()
                or not isinstance(weekdays, list) or not weekdays
                or any(type(d) is not int or d < 0 or d > 6 for d in weekdays)
                or len(set(weekdays)) != len(weekdays)):
            raise ValueError("Work calendar needs one modeled factory, known weekdays and provenance")
        seen.add(node)
        closed = frozenset(day for day in range(through_day + 1)
                           if (origin + timedelta(days=day)).weekday() not in weekdays)
        for pair in produced_pairs:
            if pair[0] == node:
                result[pair] = closed
    return result
