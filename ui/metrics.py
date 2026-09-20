"""Derived numbers shown in more than one place, computed once and consistently."""

import numpy as np


def plan_savings(baseline: dict, result: dict) -> dict:
    """Optimized plan vs. the naive baseline. Costs are day-equivalent; monthly = daily x 30."""
    saved = baseline["total_cost"] - result["total_cost"]
    pct = saved / baseline["total_cost"] * 100 if baseline["total_cost"] else 0.0
    # Distance per order, not total distance: the two networks can serve different
    # numbers of orders, and per-order distance is the fair comparison (see README).
    d_base, d_opt = baseline["avg_km_per_order"], result["avg_km_per_order"]
    dist_pct = (d_base - d_opt) / d_base * 100 if d_base else 0.0
    util = float(np.mean([w["utilization"] for w in result["warehouses"]])) * 100
    return {"daily": saved, "monthly": saved * 30, "pct": pct, "dist_pct": dist_pct, "avg_util": util}
