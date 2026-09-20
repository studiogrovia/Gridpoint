"""Tabular views of optimizer output (shared by Results and Reports)."""

import pandas as pd


def assignments_frame(df: pd.DataFrame, result: dict) -> pd.DataFrame:
    """One row per neighborhood: who serves it, from how far, and how long it takes."""
    df = df.reset_index(drop=True)
    rows = []
    for i, a in enumerate(result["assignments"]):
        served = a["warehouse"] is not None
        rows.append({
            "Neighborhood": df.loc[i, "name"],
            "Orders/day": int(df.loc[i, "daily_orders"]),
            "Traffic": df.loc[i, "traffic_level"],
            "Warehouse": result["warehouses"][a["warehouse"]]["warehouse_id"] if served else "Unserved",
            "Distance (km)": round(a["distance_km"], 1) if served else None,
            "Est. delivery (min)": round(a["delivery_minutes"]) if served else None,
            "Trips/day": int(a["trips"]) if served else None,
            "Main vehicle": str(a["vehicle"]).title() if served else None,
        })
    return pd.DataFrame(rows)


def warehouses_frame(result: dict) -> pd.DataFrame:
    return pd.DataFrame([
        {
            "Warehouse": w["warehouse_id"],
            "Latitude": round(w["lat"], 5),
            "Longitude": round(w["lon"], 5),
            "Orders/day assigned": w["assigned_orders"],
            "Capacity": int(w["capacity"]),
            "Utilization (%)": round(w["utilization"] * 100, 1),
        }
        for w in result["warehouses"]
    ])
