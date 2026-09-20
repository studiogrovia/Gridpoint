"""
Cost, vehicle, fuel, traffic-time and CO2 model for GRIDPOINT.

All numbers here are documented, defensible assumptions for a demo/hackathon
prototype -- not measured real-world data. Every one of them is configurable
from the UI, and every rupee/CO2/minute figure GRIDPOINT shows the user is
labeled as an ESTIMATE.

WHAT THIS MODULE MODELS
-----------------------
1. VEHICLE TYPES      -- bike / van / truck, each with its own payload,
                         fuel efficiency, running cost and emissions.
2. FUEL COST          -- priced explicitly in INR per litre, derived from each
                         vehicle's km-per-litre rather than hidden inside a
                         flat per-km rate. Raising the fuel price in the
                         what-if simulator therefore hurts a truck-heavy
                         network more than a bike-heavy one, which is the
                         behaviour you want from a real planning tool.
3. TRAFFIC            -- affects BOTH cost (congestion burns fuel) and TIME
                         (congestion lowers average speed).
4. DELIVERY TIME      -- estimated minutes per trip, so "Speed" is an actual
                         measured quantity, not a proxy for distance.
"""

# ---------------------------------------------------------------------------
# Vehicle fleet assumptions
# ---------------------------------------------------------------------------
# capacity_orders    : typical e-commerce parcels carried per trip
# nonfuel_cost_per_km: driver wages, maintenance, tyres, insurance (INR/km)
# km_per_litre       : fuel efficiency used to convert fuel price -> INR/km
# co2_g_per_km       : approximate tailpipe CO2, grams per km
# speed_factor       : relative to a car in the same traffic (bikes filter
#                      through congestion; trucks are slower and restricted)
VEHICLES = {
    "BIKE":  {"capacity_orders": 20,  "nonfuel_cost_per_km": 3.8, "km_per_litre": 45,
              "co2_g_per_km": 60,  "speed_factor": 1.15},
    "VAN":   {"capacity_orders": 120, "nonfuel_cost_per_km": 6.9, "km_per_litre": 14,
              "co2_g_per_km": 180, "speed_factor": 1.00},
    "TRUCK": {"capacity_orders": 400, "nonfuel_cost_per_km": 8.0, "km_per_litre": 5,
              "co2_g_per_km": 420, "speed_factor": 0.85},
}

# Congestion raises effective distance/fuel burn (stop-start driving).
TRAFFIC_MULTIPLIERS = {"Low": 1.0, "Medium": 1.2, "High": 1.5}

# Average achievable speed for a van, by traffic level (km/h). Bikes and
# trucks scale off this via their speed_factor.
TRAFFIC_SPEED_KMPH = {"Low": 30.0, "Medium": 22.0, "High": 14.0}

# Fixed time to load at the warehouse + hand over at the neighborhood (minutes
# per trip). Without this, a very short trip looks almost instantaneous.
HANDLING_MINUTES_PER_TRIP = 18.0

# Baseline pump price. The what-if simulator scales this.
BASE_FUEL_PRICE_PER_LITRE = 100.0   # INR/litre
DEFAULT_FUEL_INDEX = 1.0            # 1.0 = baseline price

DEFAULT_WAREHOUSE_COST = 450_000    # INR/month per warehouse (rent + ops)

# A neighborhood that cannot be served by any warehouse (capacity/radius
# exhausted) is not "free" -- it is a lost or failed delivery (refund, lost
# sale, reputational damage). We apply a documented per-order penalty so
# total-cost comparisons can never favour an infeasible network just because
# unmet demand went uncosted. Placeholder assumption, not a measured figure.
UNSERVED_ORDER_PENALTY = 80         # INR per unserved order per day


def fuel_price(fuel_index: float = DEFAULT_FUEL_INDEX) -> float:
    """Effective pump price in INR/litre for a given price index."""
    return BASE_FUEL_PRICE_PER_LITRE * fuel_index


def vehicle_cost_per_km(vehicle: str, fuel_index: float = DEFAULT_FUEL_INDEX) -> float:
    """
    Total running cost per km = fixed (driver/maintenance) + fuel.
    Fuel component = price_per_litre / km_per_litre.
    """
    spec = VEHICLES[vehicle]
    return spec["nonfuel_cost_per_km"] + fuel_price(fuel_index) / spec["km_per_litre"]


_FLEET_CACHE = {}
_DP_UNIT = 10   # granularity of the fleet DP, in orders


def plan_fleet(orders: int, fuel_index: float = DEFAULT_FUEL_INDEX) -> dict:
    """
    Choose the CHEAPEST MIX of vehicles that can carry `orders` parcels.

    This is an unbounded-knapsack / coin-change problem. We must cover at
    least `orders` units of payload, each vehicle type is a "coin" with
    payload c_v and per-km price p_v, and we minimise total price:

        minimise   sum_v  n_v * p_v
        subject to sum_v  n_v * c_v  >= orders,   n_v integer >= 0

    Distance cancels out of the objective (every vehicle on this lane drives
    the same distance), so the optimal MIX is distance-independent and can be
    solved once per order volume and cached.

    Why a DP and not "use the biggest vehicle"? Because the last partial load
    matters. A truck carries 400 parcels at Rs 28/km; sending a whole truck
    out for a 10-parcel remainder costs far more than a bike at Rs 6/km. The
    DP finds those mixed fleets automatically -- e.g. 1,210 orders becomes
    3 trucks + 1 bike, not 4 trucks.

    Returns {"VAN": 2, "TRUCK": 3, ...} with vehicle counts (= trips).
    """
    orders = max(1, int(orders))
    key = (orders, round(float(fuel_index), 4))
    if key in _FLEET_CACHE:
        return _FLEET_CACHE[key]

    units = -(-orders // _DP_UNIT)                       # ceiling division
    coins = [(v, max(1, VEHICLES[v]["capacity_orders"] // _DP_UNIT),
              vehicle_cost_per_km(v, fuel_index)) for v in VEHICLES]

    INF = float("inf")
    best = [INF] * (units + 1)
    pick = [None] * (units + 1)
    best[0] = 0.0
    for u in range(1, units + 1):
        for name, cap, price in coins:
            prev = max(0, u - cap)                       # overshoot is allowed
            if best[prev] + price < best[u]:
                best[u] = best[prev] + price
                pick[u] = name

    fleet, u = {}, units
    while u > 0 and pick[u] is not None:
        name = pick[u]
        fleet[name] = fleet.get(name, 0) + 1
        u = max(0, u - max(1, VEHICLES[name]["capacity_orders"] // _DP_UNIT))

    if not fleet:
        fleet = {"BIKE": 1}
    _FLEET_CACHE[key] = fleet
    return fleet


def choose_vehicle(orders: int) -> str:
    """The single smallest vehicle able to carry this volume in one trip."""
    if orders <= VEHICLES["BIKE"]["capacity_orders"]:
        return "BIKE"
    if orders <= VEHICLES["VAN"]["capacity_orders"]:
        return "VAN"
    return "TRUCK"


def delivery_minutes(distance_km: float, traffic_level: str, vehicle: str) -> float:
    """
    Estimated one-way door-to-door time for a single trip, in minutes.

        speed = base_speed(traffic) * vehicle_speed_factor
        time  = 60 * distance / speed  +  handling time

    Traffic therefore changes the ANSWER, not just the price: in heavy
    congestion a far-but-fast corridor can beat a near-but-jammed one.
    """
    base_speed = TRAFFIC_SPEED_KMPH.get(traffic_level, 22.0)
    speed = base_speed * VEHICLES[vehicle]["speed_factor"]
    return (distance_km / speed) * 60.0 + HANDLING_MINUTES_PER_TRIP


def transportation_cost(orders: int, distance_km: float, traffic_level: str,
                        fuel_index: float = DEFAULT_FUEL_INDEX) -> dict:
    """
    Estimate the DAILY cost of serving `orders` orders over `distance_km`
    under the given traffic conditions.

        trips             = ceil(orders / vehicle capacity)
        effective_distance= distance * traffic_multiplier
        cost              = trips * effective_distance * cost_per_km
        fuel_litres       = trips * effective_distance / km_per_litre
        co2               = trips * effective_distance * co2_per_km
        time              = trips * one-way trip time

    Returns every component separately so the UI can show WHY a number moved
    (more trips? longer distance? pricier fuel?) instead of one opaque total.
    """
    traffic_mult = TRAFFIC_MULTIPLIERS.get(traffic_level, 1.0)
    effective_distance = distance_km * traffic_mult
    fleet = plan_fleet(orders, fuel_index)

    cost = litres = co2_grams = 0.0
    slowest = 0.0
    for vehicle, trips in fleet.items():
        spec = VEHICLES[vehicle]
        cost += trips * effective_distance * vehicle_cost_per_km(vehicle, fuel_index)
        litres += trips * effective_distance / spec["km_per_litre"]
        co2_grams += trips * effective_distance * spec["co2_g_per_km"]
        # Vehicles in the fleet drive in parallel, so the neighborhood is only
        # fully served once the SLOWEST vehicle arrives.
        slowest = max(slowest, delivery_minutes(effective_distance, traffic_level, vehicle))

    return {
        "fleet": fleet,
        "vehicle": max(fleet, key=lambda v: VEHICLES[v]["capacity_orders"]),
        "trips": sum(fleet.values()),
        "effective_distance_km": effective_distance,
        "fuel_litres": litres,
        "fuel_cost": litres * fuel_price(fuel_index),
        "cost": cost,
        "co2_kg": co2_grams / 1000.0,
        "delivery_minutes": slowest,
        "minutes_per_trip": slowest,
    }


def infrastructure_cost(num_warehouses: int, cost_per_warehouse: float = DEFAULT_WAREHOUSE_COST) -> float:
    """Total MONTHLY warehouse rent/ops cost across the network. Estimate only."""
    return num_warehouses * cost_per_warehouse
