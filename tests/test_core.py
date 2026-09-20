"""
Test suite for the GRIDPOINT optimization engine.

Run with:  python -m pytest -q

These tests assert the PROPERTIES that make the recommendation trustworthy:
determinism, respect for hard constraints, and correct economic behaviour.
"""

import numpy as np
import pandas as pd
import pytest

from core.data_model import load_demo_data, validate_neighborhoods_df
from core.distance import haversine_km, road_distance_km
from core.cost_model import (
    choose_vehicle, plan_fleet, transportation_cost, vehicle_cost_per_km,
    delivery_minutes, VEHICLES,
)
from core.optimizer import optimize_network, baseline_network, simulate_disruption
from core.tradeoff import tradeoff_curve, recommend_k

CFG = dict(capacity_per_warehouse=5500, max_radius_km=20.0, cost_per_warehouse=450_000)


@pytest.fixture(scope="module")
def df():
    return load_demo_data()


# --- distance -------------------------------------------------------------
def test_haversine_known_distance():
    # Bengaluru city centre to Whitefield is roughly 17 km as the crow flies.
    d = haversine_km(12.9716, 77.5946, 12.9698, 77.7500)
    assert 15 < d < 19


def test_road_distance_exceeds_straight_line():
    a = haversine_km(12.97, 77.59, 12.93, 77.61)
    assert road_distance_km(12.97, 77.59, 12.93, 77.61) > a


# --- vehicles, fuel, traffic ---------------------------------------------
def test_vehicle_selection_scales_with_volume():
    assert choose_vehicle(10) == "BIKE"
    assert choose_vehicle(100) == "VAN"
    assert choose_vehicle(1000) == "TRUCK"


def test_fuel_price_hits_thirsty_vehicles_hardest():
    bike = vehicle_cost_per_km("BIKE", 2.0) - vehicle_cost_per_km("BIKE", 1.0)
    truck = vehicle_cost_per_km("TRUCK", 2.0) - vehicle_cost_per_km("TRUCK", 1.0)
    assert truck > bike


def test_traffic_increases_cost_and_time():
    low = transportation_cost(500, 10, "Low")
    high = transportation_cost(500, 10, "High")
    assert high["cost"] > low["cost"]
    assert high["delivery_minutes"] > low["delivery_minutes"]


def test_bikes_are_faster_than_trucks_in_same_traffic():
    assert delivery_minutes(10, "High", "BIKE") < delivery_minutes(10, "High", "TRUCK")


# --- optimizer constraints -----------------------------------------------
def test_optimization_is_deterministic(df):
    a = optimize_network(df, 3, **CFG)
    b = optimize_network(df, 3, **CFG)
    assert [w["lat"] for w in a["warehouses"]] == [w["lat"] for w in b["warehouses"]]


def test_capacity_is_never_exceeded(df):
    res = optimize_network(df, 3, **CFG)
    for w in res["warehouses"]:
        assert w["assigned_orders"] <= CFG["capacity_per_warehouse"]


def test_service_radius_is_respected(df):
    res = optimize_network(df, 3, **CFG)
    for a in res["assignments"]:
        if a["warehouse"] is not None:
            assert a["distance_km"] <= CFG["max_radius_km"] + 1e-9


def test_tight_capacity_reports_unserved_instead_of_lying(df):
    res = optimize_network(df, 1, capacity_per_warehouse=500,
                           max_radius_km=20.0, cost_per_warehouse=450_000)
    assert not res["feasible"]
    assert res["unserved_orders"] > 0


# --- economics ------------------------------------------------------------
def test_optimized_beats_naive_baseline(df):
    opt = optimize_network(df, 3, **CFG)
    base = baseline_network(df, 3, **CFG)
    assert opt["total_cost"] < base["total_cost"]
    assert opt["avg_km_per_order"] <= base["avg_km_per_order"]


def test_fleet_mix_is_cheaper_than_rounding_up(df):
    # 1,210 orders should NOT be 4 trucks: 3 trucks + 1 bike is cheaper.
    fleet = plan_fleet(1210)
    naive = -(-1210 // VEHICLES["TRUCK"]["capacity_orders"]) * vehicle_cost_per_km("TRUCK")
    smart = sum(n * vehicle_cost_per_km(v) for v, n in fleet.items())
    assert smart < naive
    assert sum(n * VEHICLES[v]["capacity_orders"] for v, n in fleet.items()) >= 1210


def test_more_warehouses_shorten_deliveries(df):
    far = optimize_network(df, 2, **CFG)["avg_km_per_order"]
    near = optimize_network(df, 5, **CFG)["avg_km_per_order"]
    assert near < far


def test_demand_growth_raises_cost(df):
    grown = df.copy()
    grown["daily_orders"] = (grown["daily_orders"] * 1.5).astype(int)
    assert (optimize_network(grown, 3, **CFG)["total_transport_cost"]
            > optimize_network(df, 3, **CFG)["total_transport_cost"])


def test_speed_priority_beats_cost_priority_on_time(df):
    fast = optimize_network(df, 3, **CFG, priority="Speed")
    cheap = optimize_network(df, 3, **CFG, priority="Cost")
    assert fast["avg_delivery_minutes"] <= cheap["avg_delivery_minutes"] + 1e-6


# --- trade-off and disruption --------------------------------------------
def test_tradeoff_infrastructure_rises_delivery_falls(df):
    curve = tradeoff_curve(df, 2, 5, **CFG)
    assert curve["infrastructure_cost"].is_monotonic_increasing
    assert curve["delivery_cost"].iloc[-1] < curve["delivery_cost"].iloc[0]
    rec = recommend_k(curve)
    assert 2 <= rec["k"] <= 5


def test_disruption_costs_more_than_healthy_network(df):
    res = optimize_network(df, 3, **CFG)
    dis = simulate_disruption(df, res, "W1", **CFG)
    assert dis["affected_orders"] > 0
    assert dis["additional_daily_cost"] > 0


# --- data validation ------------------------------------------------------
def test_missing_column_is_rejected():
    with pytest.raises(ValueError):
        validate_neighborhoods_df(pd.DataFrame({"name": ["A"], "lat": [12.9]}))


def test_invalid_traffic_level_is_rejected():
    bad = pd.DataFrame({"name": ["A"], "lat": [12.9], "lon": [77.6],
                        "area_m2": [1000], "daily_orders": [10], "traffic_level": ["Insane"]})
    with pytest.raises(ValueError):
        validate_neighborhoods_df(bad)


def _rows(**overrides):
    base = {"name": ["A", "B"], "lat": [12.9, 12.95], "lon": [77.6, 77.65],
            "area_m2": [1000, 2000], "daily_orders": [10, 20], "traffic_level": ["Low", "High"]}
    base.update(overrides)
    return pd.DataFrame(base)


def test_valid_rows_are_accepted_and_given_ids():
    out = validate_neighborhoods_df(_rows())
    assert list(out["id"]) == ["N01", "N02"]


@pytest.mark.parametrize("overrides, fragment", [
    ({"lat": [95, 12.9]}, "Latitude must be between"),
    ({"lon": [77.6, 200]}, "Longitude must be between"),
    ({"area_m2": [0, 5]}, "Area must be greater than zero"),
    ({"daily_orders": [-1, 5]}, "cannot be negative"),
    ({"name": ["A", "  "]}, "needs a name"),
    ({"traffic_level": ["Low", None]}, "traffic_level"),
])
def test_bad_values_are_rejected_with_a_row_specific_message(overrides, fragment):
    with pytest.raises(ValueError) as err:
        validate_neighborhoods_df(_rows(**overrides))
    assert fragment in str(err.value)
    assert "row" in str(err.value) or "traffic_level" in str(err.value)


def test_empty_table_is_rejected():
    with pytest.raises(ValueError):
        validate_neighborhoods_df(_rows().iloc[0:0])
