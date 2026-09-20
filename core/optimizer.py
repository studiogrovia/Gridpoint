"""
GRIDPOINT optimization engine.

This module contains the actual mathematical optimization -- no UI code,
no Streamlit -- so it can be tested and run completely independently of
the app (see the bottom of this file for a quick self-test).

APPROACH
--------
Facility location with capacity and service-radius constraints is NP-hard
in general. For a 24-hour hackathon prototype we use a well-known, defensible
heuristic instead of an exact solver:

1. DEMAND-WEIGHTED K-MEANS proposes warehouse locations. Neighborhoods with
   more daily orders pull candidate warehouse locations toward them more
   strongly than low-demand neighborhoods -- this directly implements the
   product requirement that "high-demand neighborhoods should influence the
   optimization more heavily," instead of simply picking the largest area.

2. NEAREST-FEASIBLE ASSIGNMENT. Neighborhoods are assigned to warehouses,
   highest-demand first, to their nearest warehouse that still has:
     - enough remaining capacity (in daily orders), and
     - the neighborhood within the configured maximum service radius.
   A neighborhood that cannot be placed anywhere is flagged UNSERVED so the
   user sees the shortfall rather than getting a silently wrong answer.

3. MULTI-RESTART. K-means depends on random initialization, so we run several
   restarts and keep the lowest-cost FEASIBLE configuration found.

Every location optimize_network() returns can be traced back to these
deterministic steps -- no location is invented or randomly chosen by an
AI/LLM.
"""

import numpy as np
import pandas as pd

from .distance import distance_matrix
from .cost_model import (
    transportation_cost, infrastructure_cost, DEFAULT_FUEL_INDEX, UNSERVED_ORDER_PENALTY,
)

N_RESTARTS = 8
MAX_KMEANS_ITER = 100
RANDOM_SEED = 42


def _weighted_kmeans(points: np.ndarray, weights: np.ndarray, k: int, seed: int) -> np.ndarray:
    """
    Demand-weighted k-means over [lat, lon] points. Centroids are pulled
    toward high-weight (high-demand) points. Returns k centroid coordinates.
    """
    rng = np.random.default_rng(seed)
    n = points.shape[0]
    k = min(k, n)

    probs = weights / weights.sum()
    init_idx = rng.choice(n, size=k, replace=False, p=probs)
    centroids = points[init_idx].copy()

    for _ in range(MAX_KMEANS_ITER):
        dists = distance_matrix(points, centroids)
        assignments = np.argmin(dists, axis=1)

        new_centroids = centroids.copy()
        for c in range(k):
            mask = assignments == c
            if not mask.any():
                new_centroids[c] = points[np.argmax(weights)]
                continue
            new_centroids[c] = np.average(points[mask], axis=0, weights=weights[mask])

        if np.allclose(new_centroids, centroids, atol=1e-6):
            centroids = new_centroids
            break
        centroids = new_centroids

    return centroids


def _assign_neighborhoods(df: pd.DataFrame, warehouse_locations: np.ndarray,
                           capacity: float, max_radius_km: float) -> dict:
    """
    Assign each neighborhood to a warehouse: nearest-feasible first,
    respecting capacity and max service radius.
    """
    points = df[["lat", "lon"]].to_numpy()
    dist_mat = distance_matrix(points, warehouse_locations)

    k = warehouse_locations.shape[0]
    remaining_capacity = np.full(k, capacity, dtype=float)
    assignment = np.full(len(df), -1, dtype=int)
    unserved = []

    # Serve highest-demand neighborhoods first so big demand nodes get their
    # nearest warehouse before capacity is eaten up by smaller ones.
    order = np.argsort(-df["daily_orders"].to_numpy())

    for i in order:
        orders = df.iloc[i]["daily_orders"]
        candidates = np.argsort(dist_mat[i])
        placed = False
        for w in candidates:
            if dist_mat[i, w] > max_radius_km:
                continue
            if remaining_capacity[w] >= orders:
                assignment[i] = w
                remaining_capacity[w] -= orders
                placed = True
                break
        if not placed:
            unserved.append(df.iloc[i]["id"])

    return {
        "assignment": assignment,
        "distances": dist_mat,
        "remaining_capacity": remaining_capacity,
        "unserved_ids": unserved,
    }


def _evaluate_configuration(df: pd.DataFrame, warehouse_locations: np.ndarray,
                             capacity: float, max_radius_km: float,
                             cost_per_warehouse: float, fuel_index: float) -> dict:
    """Assign neighborhoods to a candidate warehouse layout and cost it out."""
    df = df.reset_index(drop=True)
    assign_result = _assign_neighborhoods(df, warehouse_locations, capacity, max_radius_km)
    assignment = assign_result["assignment"]
    dist_mat = assign_result["distances"]

    total_transport_cost = 0.0
    total_distance = 0.0
    total_co2_kg = 0.0
    total_fuel_litres = 0.0
    total_order_km = 0.0
    total_order_km_all = 0.0
    total_orders_all = 0
    total_orders_served = 0
    weighted_minutes = 0.0
    worst_minutes = 0.0
    vehicle_mix = {}
    per_neighborhood = []

    for i, row in df.iterrows():
        w = assignment[i]
        if w == -1:
            # This neighborhood could not be served within capacity/radius.
            # We still count the distance its parcels WOULD have to travel
            # (to the nearest warehouse), because in reality that demand does
            # not vanish -- somebody has to drive it. Without this, a network
            # that simply abandons its most remote customers would post a
            # flattering "shorter average delivery" number. Its cost is
            # carried separately by the unserved-order penalty.
            nearest = int(np.argmin(dist_mat[i]))
            total_order_km_all += dist_mat[i, nearest] * int(row["daily_orders"])
            total_orders_all += int(row["daily_orders"])
            per_neighborhood.append({
                "id": row["id"], "name": row["name"], "warehouse": None,
                "distance_km": None, "cost": None, "vehicle": None,
                "delivery_minutes": None, "trips": None, "fuel_litres": None,
            })
            continue
        dist = dist_mat[i, w]
        tc = transportation_cost(row["daily_orders"], dist, row["traffic_level"], fuel_index)
        total_transport_cost += tc["cost"]
        total_distance += dist
        total_co2_kg += tc["co2_kg"]
        total_fuel_litres += tc["fuel_litres"]
        for veh, trips in tc["fleet"].items():
            vehicle_mix[veh] = vehicle_mix.get(veh, 0) + trips
        # Order-weighted average: a slow route serving 2,000 orders/day matters
        # far more to customers than a slow route serving 50.
        orders = int(row["daily_orders"])
        total_orders_served += orders
        # Order-weighted distance ("order-km") is the metric that actually
        # matters: 2,000 parcels travelling 5 km is a bigger logistics burden
        # than 50 parcels travelling 15 km. A plain sum of per-neighborhood
        # distances would treat those as 5 km vs 15 km and rank them backwards.
        total_order_km += dist * orders
        total_order_km_all += dist * orders
        total_orders_all += orders
        weighted_minutes += tc["minutes_per_trip"] * orders
        worst_minutes = max(worst_minutes, tc["minutes_per_trip"])
        per_neighborhood.append({
            "id": row["id"], "name": row["name"], "warehouse": int(w),
            "distance_km": dist, "cost": tc["cost"], "vehicle": tc["vehicle"],
            "delivery_minutes": tc["minutes_per_trip"], "trips": tc["trips"],
            "fuel_litres": tc["fuel_litres"],
        })

    infra_cost_monthly = infrastructure_cost(len(warehouse_locations), cost_per_warehouse)
    unserved_orders = int(df[df["id"].isin(assign_result["unserved_ids"])]["daily_orders"].sum())
    unserved_penalty_cost = unserved_orders * UNSERVED_ORDER_PENALTY

    # transportation cost is a daily figure; infrastructure cost is monthly.
    # total_cost is expressed as a daily-equivalent so the two are comparable
    # and can be safely added -- infra cost is amortized over a 30-day month.
    # The unserved-order penalty is included so an infeasible network can
    # never look artificially cheaper than a feasible one.
    total_cost = total_transport_cost + (infra_cost_monthly / 30) + unserved_penalty_cost
    feasible = len(assign_result["unserved_ids"]) == 0

    warehouses = []
    for w_idx in range(len(warehouse_locations)):
        assigned_orders = df.iloc[[i for i in range(len(df)) if assignment[i] == w_idx]]["daily_orders"].sum()
        warehouses.append({
            "warehouse_id": f"W{w_idx + 1}",
            "lat": float(warehouse_locations[w_idx][0]),
            "lon": float(warehouse_locations[w_idx][1]),
            "capacity": capacity,
            "assigned_orders": int(assigned_orders),
            "utilization": round(assigned_orders / capacity, 3) if capacity else 0,
        })

    return {
        "feasible": feasible,
        "unserved_ids": assign_result["unserved_ids"],
        "unserved_orders": unserved_orders,
        "unserved_penalty_cost": unserved_penalty_cost,
        "warehouses": warehouses,
        "assignments": per_neighborhood,
        "total_transport_cost": total_transport_cost,
        "total_infra_cost": infra_cost_monthly,
        "total_cost": total_cost,
        "total_distance_km": total_distance,
        "total_co2_kg": total_co2_kg,
        "total_fuel_litres": total_fuel_litres,
        "total_order_km": total_order_km,
        # Distance per parcel, comparable across networks even when they serve
        # different numbers of orders (e.g. an infeasible baseline that drops a
        # neighborhood). Comparing raw distance sums in that situation flatters
        # the network that simply gave up on its hardest customers.
        "avg_km_per_order": (total_order_km_all / total_orders_all) if total_orders_all else 0.0,
        "avg_km_per_served_order": (total_order_km / total_orders_served) if total_orders_served else 0.0,
        "orders_served": total_orders_served,
        "avg_delivery_minutes": (weighted_minutes / total_orders_served) if total_orders_served else 0.0,
        "worst_delivery_minutes": worst_minutes,
        "vehicle_mix": vehicle_mix,
    }


def optimize_network(df: pd.DataFrame, num_warehouses: int, capacity_per_warehouse: float,
                      max_radius_km: float, cost_per_warehouse: float,
                      fuel_index: float = DEFAULT_FUEL_INDEX, priority: str = "Cost") -> dict:
    """
    Main entry point. Given neighborhood demand data and network configuration,
    return the best feasible warehouse layout found.

    priority: "Cost" | "Speed" | "Sustainability" -- which metric breaks ties
    between otherwise-similar feasible configurations found across restarts.
    """
    df = df.reset_index(drop=True)
    points = df[["lat", "lon"]].to_numpy()
    weights = df["daily_orders"].to_numpy().astype(float)
    weights = np.where(weights <= 0, 1.0, weights)

    best = None
    for restart in range(N_RESTARTS):
        seed = RANDOM_SEED + restart
        centroids = _weighted_kmeans(points, weights, num_warehouses, seed)
        result = _evaluate_configuration(
            df, centroids, capacity_per_warehouse, max_radius_km, cost_per_warehouse, fuel_index
        )

        if priority == "Speed":
            # Speed is scored on order-weighted delivery TIME, which accounts
            # for traffic and vehicle type -- not raw distance.
            score = result["avg_delivery_minutes"]
        elif priority == "Sustainability":
            score = result["total_co2_kg"]
        else:
            score = result["total_cost"]

        candidate_key = (0 if result["feasible"] else 1, len(result["unserved_ids"]), score)

        if best is None or candidate_key < best["_key"]:
            result["_key"] = candidate_key
            best = result

    best.pop("_key", None)
    best["num_warehouses"] = num_warehouses
    best["priority"] = priority
    return best


def baseline_network(df: pd.DataFrame, num_warehouses: int, capacity_per_warehouse: float,
                      max_radius_km: float, cost_per_warehouse: float,
                      fuel_index: float = DEFAULT_FUEL_INDEX) -> dict:
    """
    The "naive" comparison network: the SAME number of warehouses as the
    optimized plan, but placed in the top-N highest-demand neighborhoods
    with no clustering or demand-weighted math -- i.e. exactly the naive
    "put a warehouse in the biggest neighborhood" strategy the product spec
    explicitly wants GRIDPOINT to beat.

    Using the same warehouse count as the optimized network is important:
    it isolates the value of WHERE the warehouses are placed, rather than
    conflating it with how many warehouses were built (more warehouses
    always costs more in fixed infrastructure, regardless of placement
    quality).
    """
    df = df.reset_index(drop=True)
    top_idx = df["daily_orders"].nlargest(min(num_warehouses, len(df))).index
    locations = df.loc[top_idx, ["lat", "lon"]].to_numpy()
    result = _evaluate_configuration(
        df, locations, capacity_per_warehouse, max_radius_km,
        cost_per_warehouse=cost_per_warehouse, fuel_index=fuel_index,
    )
    result["num_warehouses"] = len(locations)
    result["priority"] = "None (naive baseline: warehouses in top-demand neighborhoods)"
    return result


def simulate_disruption(df: pd.DataFrame, optimized_result: dict, failed_warehouse_id: str,
                         capacity_per_warehouse: float, max_radius_km: float,
                         cost_per_warehouse: float, fuel_index: float = DEFAULT_FUEL_INDEX) -> dict:
    """
    Simulate one warehouse going offline: remove it, try to reassign its
    neighborhoods to the remaining warehouses (respecting capacity and
    radius), and report the cost/impact of the disruption.
    """
    df = df.reset_index(drop=True)
    surviving = [w for w in optimized_result["warehouses"] if w["warehouse_id"] != failed_warehouse_id]
    if not surviving:
        return {"error": "Cannot simulate failure: no warehouses would remain."}

    affected = [
        a for a in optimized_result["assignments"]
        if a["warehouse"] is not None
        and optimized_result["warehouses"][a["warehouse"]]["warehouse_id"] == failed_warehouse_id
    ]
    affected_ids = {a["id"] for a in affected}
    affected_orders = int(df[df["id"].isin(affected_ids)]["daily_orders"].sum())

    surviving_locations = np.array([[w["lat"], w["lon"]] for w in surviving])
    new_result = _evaluate_configuration(
        df, surviving_locations, capacity_per_warehouse, max_radius_km, cost_per_warehouse, fuel_index,
    )

    # _evaluate_configuration numbers warehouses fresh from the array we gave
    # it (W1, W2, ...), which would confusingly relabel a surviving warehouse
    # (e.g. the old W2) as "W1". Re-stamp the original warehouse_ids back on
    # so the recovery plan refers to warehouses by the names the user already
    # knows from the Optimization Results page.
    for idx, original in enumerate(surviving):
        new_result["warehouses"][idx]["warehouse_id"] = original["warehouse_id"]
    for a in new_result["assignments"]:
        if a["warehouse"] is not None:
            a["warehouse_id"] = surviving[a["warehouse"]]["warehouse_id"]

    additional_cost = new_result["total_cost"] - optimized_result["total_cost"]
    additional_distance = new_result["total_distance_km"] - optimized_result["total_distance_km"]

    reassigned_to = sorted({
        new_result["warehouses"][a["warehouse"]]["warehouse_id"]
        for a in new_result["assignments"]
        if a["id"] in affected_ids and a["warehouse"] is not None
    })

    return {
        "failed_warehouse_id": failed_warehouse_id,
        "affected_neighborhoods": sorted(affected_ids),
        "affected_orders": affected_orders,
        "still_unserved_ids": new_result["unserved_ids"],
        "reassigned_to": reassigned_to,
        "additional_daily_cost": additional_cost,
        "additional_distance_km": additional_distance,
        "new_network": new_result,
    }


if __name__ == "__main__":
    # Quick self-test: run against the demo dataset with no Streamlit involved.
    from .data_model import load_demo_data

    demo_df = load_demo_data()
    print("Total daily orders in demo data:", int(demo_df["daily_orders"].sum()))

    res = optimize_network(demo_df, num_warehouses=3, capacity_per_warehouse=5500,
                            max_radius_km=20.0, cost_per_warehouse=450_000)
    base = baseline_network(demo_df, num_warehouses=3, capacity_per_warehouse=5500,
                             max_radius_km=20.0, cost_per_warehouse=450_000)

    print("Feasible:", res["feasible"], "| Unserved:", res["unserved_ids"])
    print("Total cost/day-equiv (optimized):", round(res["total_cost"]))
    print("Total cost/day-equiv (baseline):", round(base["total_cost"]))
    for wh in res["warehouses"]:
        print(wh)
