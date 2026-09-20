"""
Infrastructure-vs-delivery trade-off explorer.

THE CENTRAL TENSION IN NETWORK DESIGN
-------------------------------------
Build MORE warehouses  -> customers are closer -> delivery cost falls,
                          but fixed rent/infrastructure cost rises.
Build FEWER warehouses -> rent is cheap, but every parcel travels further,
                          burning more fuel and more delivery time.

Formally, with k warehouses:

    TotalCost(k) = Transport(k)  +  Infra(k)  +  Penalty(k)
                   \\_ falls _/      \\_ rises _/   \\_ infeasibility _/
                   roughly as        linearly       (unserved demand)
                   O(1/sqrt(k))      in k

Transport(k) decreases with diminishing returns: in a roughly uniform city,
mean distance to the nearest of k facilities scales as ~1/sqrt(k) (halving
average distance needs about four times as many warehouses). Infra(k) is
strictly linear. A decreasing convex function plus an increasing linear one
has a single interior minimum -- so sweeping k and reading off the bottom of
the U-curve is a mathematically sound way to choose the warehouse count,
rather than guessing.

This module runs the full optimizer once per k and returns the curve, so the
recommendation is measured on the user's own data, not assumed.
"""

import pandas as pd

from .optimizer import optimize_network
from .cost_model import DEFAULT_FUEL_INDEX


def tradeoff_curve(df: pd.DataFrame, k_min: int, k_max: int,
                   capacity_per_warehouse: float, max_radius_km: float,
                   cost_per_warehouse: float,
                   fuel_index: float = DEFAULT_FUEL_INDEX,
                   priority: str = "Cost") -> pd.DataFrame:
    """
    Re-optimize the network for every warehouse count in [k_min, k_max] and
    return one row per k with its cost breakdown.

    All costs are returned as DAILY-EQUIVALENT figures (monthly rent is
    amortized over 30 days) so infrastructure and delivery can legitimately
    be added together and compared on the same axis.
    """
    k_max = int(min(k_max, len(df)))
    rows = []
    for k in range(int(k_min), k_max + 1):
        res = optimize_network(
            df, num_warehouses=k,
            capacity_per_warehouse=capacity_per_warehouse,
            max_radius_km=max_radius_km,
            cost_per_warehouse=cost_per_warehouse,
            fuel_index=fuel_index,
            priority=priority,
        )
        rows.append({
            "warehouses": k,
            "delivery_cost": res["total_transport_cost"],
            "infrastructure_cost": res["total_infra_cost"] / 30.0,
            "penalty_cost": res["unserved_penalty_cost"],
            "total_cost": res["total_cost"],
            "distance_km": res["total_distance_km"],
            "avg_delivery_minutes": res["avg_delivery_minutes"],
            "co2_kg": res["total_co2_kg"],
            "fuel_litres": res["total_fuel_litres"],
            "feasible": res["feasible"],
            "unserved_orders": res["unserved_orders"],
        })
    return pd.DataFrame(rows)


def recommend_k(curve: pd.DataFrame) -> dict:
    """
    Read the sweet spot off the curve: the cheapest FEASIBLE warehouse count
    (every neighborhood served). If no k is feasible in the swept range, fall
    back to the lowest-cost option and flag it, so the user is told the truth
    instead of being shown a fake optimum.
    """
    feasible = curve[curve["feasible"]]
    pool = feasible if len(feasible) else curve
    best = pool.loc[pool["total_cost"].idxmin()]

    marginal = None
    nxt = curve[curve["warehouses"] == best["warehouses"] + 1]
    if len(nxt):
        # What the NEXT warehouse would cost you -- the sentence a CFO wants:
        # "warehouse #4 adds Rs X/day of rent but only saves Rs Y/day of driving."
        row = nxt.iloc[0]
        marginal = {
            "next_k": int(row["warehouses"]),
            "extra_infra": row["infrastructure_cost"] - best["infrastructure_cost"],
            "delivery_saved": best["delivery_cost"] - row["delivery_cost"],
            "net": row["total_cost"] - best["total_cost"],
        }

    return {
        "k": int(best["warehouses"]),
        "total_cost": float(best["total_cost"]),
        "delivery_cost": float(best["delivery_cost"]),
        "infrastructure_cost": float(best["infrastructure_cost"]),
        "feasible": bool(best["feasible"]),
        "any_feasible": bool(len(feasible)),
        "marginal": marginal,
    }
