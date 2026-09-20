"""
Natural-language explanation layer for GRIDPOINT.

IMPORTANT: this module never invents numbers. It only reads values the
optimizer already computed (see optimizer.py) and turns them into sentences.
This keeps the "AI explanation" honest -- it explains real results, it
doesn't generate its own answer.
"""


def explain_warehouse(warehouse: dict, assignments: list, all_warehouses: list, max_radius_km: float) -> str:
    """Template-based explanation of why a warehouse ended up where it did."""
    served = [
        a for a in assignments
        if a["warehouse"] is not None
        and all_warehouses[a["warehouse"]]["warehouse_id"] == warehouse["warehouse_id"]
    ]
    n_served = len(served)
    top = sorted(served, key=lambda a: a["distance_km"] or 0)[:3]
    top_names = ", ".join(a["name"] for a in top) if top else "no neighborhoods yet"

    util_pct = round(warehouse["utilization"] * 100)

    return (
        f"{warehouse['warehouse_id']} serves {n_served} neighborhood(s), including {top_names}. "
        f"It is running at {util_pct}% of its configured capacity "
        f"({warehouse['assigned_orders']:,} of {int(warehouse['capacity']):,} daily orders). "
        f"All assigned neighborhoods fall within the {max_radius_km:.1f} km maximum "
        f"service radius set for this network."
    )


def explain_disruption(disruption: dict) -> str:
    """Template-based explanation of the impact of a simulated warehouse failure."""
    n_affected = len(disruption["affected_neighborhoods"])
    reassigned = ", ".join(disruption["reassigned_to"]) if disruption["reassigned_to"] else "no warehouse (unserved)"
    unserved = disruption.get("still_unserved_ids", [])

    text = (
        f"If {disruption['failed_warehouse_id']} fails, {n_affected} neighborhood(s) "
        f"({disruption['affected_orders']:,} daily orders) are affected. "
        f"GRIDPOINT reassigns them to {reassigned}, adding an estimated "
        f"₹{disruption['additional_daily_cost']:,.0f} per day in logistics cost "
        f"and {disruption['additional_distance_km']:.1f} extra km of daily delivery distance."
    )
    if unserved:
        text += (
            f" Warning: {len(unserved)} neighborhood(s) could not be reassigned "
            f"within current capacity/radius limits."
        )
    return text
