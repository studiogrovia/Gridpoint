# The mathematics of GRIDPOINT, in plain language

You do not need a maths degree to follow this. Every idea is explained with an everyday
picture first, then the formula, then a real number taken from the demo dataset.
The code that does each step is named so you can read it alongside.

> All numbers below come from the bundled demo data (12 Bengaluru-style neighborhoods,
> 14,770 orders a day) with the default settings. Costs are illustrative estimates.

---

## The big picture

GRIDPOINT answers three questions, in this order:

1. **Where should the warehouses go?**  Put them near where the orders are.
2. **Which warehouse should serve which neighborhood?**  The nearest one that still has room.
3. **What does that cost?**  Trucks, fuel, drivers, rent, and a penalty for any customer we fail to reach.

It then builds a deliberately *naive* plan (warehouses in the busiest neighborhoods) and
shows how much the smarter plan saves.

```
neighborhoods + orders ──► 1. choose sites ──► 2. assign ──► 3. cost it ──► compare with naive plan
```

---

## 1. Measuring distance  (`core/distance.py`)

**The picture.** The Earth is a ball, not a flat map. A straight line drawn on a flat map
between two far-apart points is slightly wrong. The **haversine formula** gives the true
"as the crow flies" distance over the curved surface, using only latitude and longitude.

```
a = sin²(Δlat / 2) + cos(lat₁) · cos(lat₂) · sin²(Δlon / 2)
distance = 2 · R · arcsin(√a)          where R = 6,371 km (the Earth's radius)
```

**Roads are not crow-flights.** Trucks follow streets, so we multiply by a **detour factor**
of **1.3** (a common planning rule of thumb):

```
road distance ≈ 1.3 × straight-line distance
```

**Example.** Whitefield East to Koramangala Central: straight line **15.17 km**, so road
distance ≈ 15.17 × 1.3 = **19.72 km**.

*Why this is fine:* it needs no map service or internet, and at city scale it is accurate
enough to rank options correctly. The 1.3 is an assumption, not a measurement.

---

## 2. Choosing warehouse sites: the "weighted centre of gravity"  (`core/optimizer.py`)

### 2a. The weighted average

**The picture.** Imagine a flat board with a pin at every neighborhood, and a weight hanging
from each pin equal to its daily orders. Where would you place a single support so the board
balances? Closer to the heavy pins. That balance point is the **weighted average** location.

```
site = Σ (orders × position) / Σ orders
```

**Toy example.** Two neighborhoods: one with 1,000 orders, one with 3,000.

| | plain average | weighted average |
|---|---|---|
| position | (12.930, 77.650) | **(12.945, 77.675)** |

The weighted answer sits three-quarters of the way toward the busy neighborhood,
which is exactly what we want: **big demand should pull the warehouse harder.**

### 2b. But you have several warehouses: k-means

With *k* warehouses, which neighborhoods does each one balance? That is what **k-means**
solves. It repeats two simple moves until nothing changes:

1. **Assign** every neighborhood to its nearest warehouse candidate.
2. **Move** each candidate to the weighted centre of gravity of the neighborhoods it just got.

Like people drifting between shops until every shop is in the middle of its own crowd.
When a full round changes nothing (or moves less than a millionth of a degree), it stops.

### 2c. Restarts

k-means depends on where the candidates start, so a bad start can land in a mediocre
arrangement. GRIDPOINT therefore runs it **8 times from different starting points** and
keeps the best *feasible* result. The seeds are fixed (42, 43, …), so the same input always
gives the same answer.

**Honest note:** this is a strong **heuristic**, not a proof of the absolute best answer.
That is why the app says "Feasible plan" and never "Optimal".

---

## 3. Deciding who serves whom  (`_assign_neighborhoods`)

Each warehouse has a **capacity** (say 5,500 orders a day) and a **maximum service radius**
(say 20 km). The rule is a **greedy** one, meaning: decide step by step, never look back.

1. Sort neighborhoods from **most orders to fewest**. (Big customers choose first, before the
   space fills up.)
2. For each neighborhood, list warehouses from nearest to farthest.
3. Give it the first warehouse that is **within the radius** and has **enough spare capacity**.
4. If none qualifies, mark it **unserved**. It is reported, never hidden.

```
spare capacity  =  capacity  −  orders already assigned
```

A plan where every neighborhood is placed is called **feasible**.

---

## 4. Turning trips into money, time and CO₂  (`core/cost_model.py`)

### 4a. Cost of one kilometre for each vehicle

```
cost per km  =  driver & upkeep per km  +  fuel price ÷ km per litre
```

| Vehicle | carries (orders) | upkeep ₹/km | km per litre | **cost ₹/km** |
|---|---|---|---|---|
| Bike | 20 | 3.8 | 45 | **6.02** |
| Van | 120 | 6.9 | 14 | **14.04** |
| Truck | 400 | 8.0 | 5 | **28.00** |

(Fuel at ₹100/litre. Raise the "fuel price index" and trucks get hurt most, because they
burn the most fuel per km.)

### 4b. Which vehicles to send: the "coin change" trick

**The picture.** You must carry, say, **1,210 parcels**. Vehicles are like coins:
a truck is a "400-parcel coin" costing ₹28/km, a bike is a "20-parcel coin" costing ₹6.02/km.
Pick the **cheapest set of coins that covers at least 1,210 parcels.**

Sending 4 trucks (1,600 capacity) wastes a whole truck on the last 10 parcels.
The cheaper answer is **3 trucks + 1 bike**:

```
3 × ₹28.00 + 1 × ₹6.02  =  ₹90.02 per km      (vs 4 × ₹28.00 = ₹112.00 per km)
```

This is a classic problem (the **unbounded knapsack** / coin-change problem). It is solved
exactly with **dynamic programming**: work out the cheapest way to carry 10 parcels, then 20,
then 30, and so on, each time reusing the earlier answers. Because every vehicle on a lane
drives the same distance, distance cancels out and the best mix depends only on the order
volume. That is why the results are cached.

### 4c. Traffic

Traffic changes both **cost** (stop-start driving burns fuel) and **time** (lower speed):

| Traffic | distance multiplier | van speed |
|---|---|---|
| Low | ×1.0 | 30 km/h |
| Medium | ×1.2 | 22 km/h |
| High | ×1.5 | 14 km/h |

### 4d. Cost of serving one neighborhood for a day

```
effective distance = road distance × traffic multiplier
daily cost = Σ over vehicles ( trips × effective distance × cost per km )
```

**Example.** 1,210 orders, 8 km away, Medium traffic:
effective distance = 8 × 1.2 = 9.6 km; fleet = 3 trucks + 1 bike →
₹90.02/km × 9.6 km = **₹864 per day** (fuel ≈ 6 litres, CO₂ ≈ 12.7 kg).

### 4e. Delivery time

```
speed = traffic speed × vehicle speed factor      (bike 1.15, van 1.00, truck 0.85)
minutes = 60 × distance ÷ speed  +  18 minutes of loading and hand-over
```

**Example.** A van over 10.4 km in Medium traffic: 60 × 10.4 ÷ 22 = 28.4 min, plus 18 =
**46.4 minutes**. Vehicles on one lane drive in parallel, so the neighborhood is done when the
*slowest* one arrives.

### 4f. Emissions

```
CO₂ = trips × effective distance × grams of CO₂ per km      (bike 60, van 180, truck 420)
```

---

## 5. The total cost we are trying to minimise

Three parts, all put on a **per-day** basis so they can be added:

```
Total cost per day  =  delivery cost
                     +  warehouse rent per month ÷ 30
                     +  penalty × unserved orders          (₹80 per unserved order)
```

**Why the penalty?** Without it, a plan that simply *gave up* on hard-to-reach customers
would look cheaper than one that served everybody. The penalty makes "we didn't deliver"
cost something, so an infeasible plan can never win by cheating.

**Example (demo data, 3 warehouses):**

| | delivery | rent ÷ 30 | penalty | **total / day** |
|---|---|---|---|---|
| GRIDPOINT | ₹9,600 | ₹45,000 | ₹0 | **₹54,600** |
| Naive plan | ₹9,316 | ₹45,000 | 640 orders × ₹80 = ₹51,200 | **₹1,05,516** |

The "priority" setting only changes what is used to pick between similar plans:
lowest **cost**, shortest **delivery minutes**, or lowest **CO₂**. Feasible plans always beat
infeasible ones first.

---

## 6. Is it actually better? The comparison

The **naive plan** uses the *same number of warehouses*, but simply places them in the
top-demand neighborhoods. Using the same number isolates what we care about, **where** they
are, not **how many**.

```
daily savings   =  naive total cost − GRIDPOINT total cost
monthly savings =  daily savings × 30
```

**Example:** ₹1,05,516 − ₹54,600 = **₹50,916 per day**, about **₹15.3 lakh per month**.

**Fair distance comparison.** We compare **kilometres per order**, not total kilometres:

```
km per order = Σ (distance × orders) ÷ Σ orders
```

Two reasons. Weighting by orders is right, because 2,000 parcels travelling 5 km is a bigger
job than 50 parcels travelling 15 km. And a plan that leaves a far neighborhood unserved would
otherwise look "shorter" just by dropping its hardest customers.

---

## 7. How many warehouses? The U-shaped curve  (`core/tradeoff.py`)

More warehouses means customers are closer (delivery gets cheaper) but there is more rent.
Two forces pull in opposite directions:

```
Total(k) =  Delivery(k)   +   Rent(k)   +   Penalty(k)
            falls with k      rises in a    only if some
            (slowly)          straight line customers are unserved
```

**The 1/√k intuition.** In an evenly spread city, the average distance to the nearest of *k*
warehouses shrinks like **1 ÷ √k**. To *halve* the average distance you need about **four
times** as many warehouses. Each extra warehouse helps less than the one before, but always
costs the same rent. A curve that drops with diminishing returns plus a rising straight line
makes a **U shape**, and the bottom of the U is the sweet spot.

GRIDPOINT does not assume this: it **runs the full optimizer for every k** you choose and
reads the cheapest *feasible* one off your own data. It also reports the marginal case:
*"warehouse #4 adds ₹X of rent but saves only ₹Y of driving."*

---

## 8. What if a warehouse fails?  (`simulate_disruption`)

Remove the warehouse, keep the others exactly where they are, and re-run the assignment
step (section 3) for **all** neighborhoods against the survivors. Then report:

```
extra cost per day = new total cost − old total cost
```

Neighborhoods that no survivor can take (out of radius or out of capacity) are listed as
still unserved. That gap is your resilience risk.

---

## Glossary

| Term | Meaning |
|---|---|
| **Heuristic** | A smart, fast method that finds a very good answer without proving it is the very best. |
| **Feasible** | Every neighborhood is served within capacity and radius. |
| **Greedy** | Make the best-looking choice at each step and never go back. |
| **k-means** | Repeatedly assign points to the nearest centre, then move each centre to its group's balance point. |
| **Weighted average** | An average where bigger things count for more. |
| **Dynamic programming** | Solve small versions of a problem first and reuse those answers to solve bigger ones. |
| **Haversine** | The formula for distance between two latitude/longitude points over a curved Earth. |
| **Order-km** | Orders × kilometres travelled: a measure of the total delivery workload. |

## What this model does *not* do

- **No route planning.** It costs trips per neighborhood, not multi-stop delivery rounds.
- **Sites are points on a map.** k-means may suggest a spot with no available land.
- **Demand is a single number** per neighborhood, placed at its centre.
- **Constants are placeholders** (fuel price, rent, penalty, speeds). Replace them with your
  own numbers for real decisions.
