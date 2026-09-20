# GRIDPOINT

**Decide where to build your warehouses before you spend the money.**

![Python](https://img.shields.io/badge/python-3.9%2B-blue)
![Streamlit](https://img.shields.io/badge/built%20with-Streamlit-FF4B4B)
![License](https://img.shields.io/badge/license-MIT-green)

GRIDPOINT is a decision-support web app for logistics and e-commerce teams. You give it the
neighborhoods you deliver to and how many orders each one generates per day. It recommends
**how many warehouses to build, where to put them, which neighborhoods each one should serve,
and what the plan costs compared with the obvious layout**, then lets you stress-test it.

<!--
Add screenshots to docs/screenshots/ and uncomment these lines:

![Dashboard](docs/screenshots/dashboard.png)
![Results](docs/screenshots/results.png)
-->

## Why it exists

The obvious way to place warehouses is "put one in the busiest neighborhood". It is easy, and
it is usually expensive. GRIDPOINT replaces it with a transparent calculation: high-demand
neighborhoods pull warehouses toward them, capacity and delivery-radius limits are respected,
and every rupee, kilometre and minute in the output can be traced to a stated assumption.
Nothing is chosen by a black box or a language model.

## Features

| | |
|---|---|
| **Locations** | Load demo data, upload a CSV, or type neighborhoods in. Errors name the exact row. |
| **Optimization** | Pick warehouse count, capacity, delivery radius and priority (cost, speed or CO₂). Capacity is checked as you type. |
| **Results** | Map of warehouses, neighborhoods and delivery assignments. Before/after comparison, savings, and a plain-English reason for each site. |
| **Dashboard** | KPIs, network map, savings and utilization at a glance, with an honest status: *Ready*, *Feasible*, *Needs attention* or *Out of date*. |
| **Reports** | Charts plus CSV downloads (assignments, warehouses, summary). |
| **What-if simulator** | Change demand growth, fuel price, rent or traffic and re-optimize. |
| **Disruption mode** | Knock a warehouse offline and see who is reassigned and what it costs. |
| **Cost trade-off** | Sweep warehouse counts to find where rent and delivery cost balance. |

Responsive layout (desktop, tablet, phone), colour-blind-safe map colours and reduced-motion support.

## How it works (in one minute)

1. **Distance.** Haversine (great-circle) distance between coordinates, times a 1.3 road-detour factor.
2. **Placement.** Demand-weighted k-means proposes warehouse sites, so busy neighborhoods pull harder. Eight restarts, fixed seeds, deterministic.
3. **Assignment.** Greedy nearest-feasible: biggest neighborhoods choose first, subject to capacity and radius. Anyone who cannot be served is reported as *unserved*, never hidden.
4. **Costing.** Cheapest vehicle mix per lane (a dynamic-programming coin-change problem), plus fuel, traffic, delivery time, CO₂, rent and an unserved-order penalty.
5. **Comparison.** The same number of warehouses placed naively in the top-demand neighborhoods.

**New to the maths?** Read [`docs/MATHEMATICS.md`](docs/MATHEMATICS.md). It explains every step in plain
language with worked examples.

## Quick start

Requires **Python 3.9+** and **Streamlit 1.46+**.

```bash
git clone https://github.com/<your-username>/gridpoint.git
cd gridpoint

python -m venv venv
source venv/bin/activate        # Windows: venv\Scripts\activate

pip install -r requirements.txt
streamlit run app.py
```

Open <http://localhost:8501>, click **Load demo data**, then **Run optimization**.

## Your own data

Upload a CSV with these six columns (a template can be downloaded inside the app):

| Column | Type | Notes |
|---|---|---|
| `name` | text | Neighborhood name |
| `lat`, `lon` | decimal degrees | Latitude −90 to 90, longitude −180 to 180 |
| `area_m2` | number | Greater than 0 |
| `daily_orders` | whole number | 0 or more |
| `traffic_level` | text | `Low`, `Medium` or `High` |

```csv
name,lat,lon,area_m2,daily_orders,traffic_level
Whitefield East,12.9698,77.7500,850000,1450,High
Koramangala Central,12.9352,77.6146,620000,1980,High
```

## Project structure

```
gridpoint/
├── app.py                # Entry point: page config, theme, navigation
├── pages/                # One file per screen (dashboard, locations, optimization, ...)
├── core/                 # The maths. No Streamlit, no Plotly, fully testable
│   ├── distance.py       #   haversine + road detour
│   ├── optimizer.py      #   weighted k-means, assignment, evaluation, disruption
│   ├── cost_model.py     #   vehicles, fleet mix, fuel, traffic, time, CO₂
│   ├── tradeoff.py       #   warehouse-count sweep and recommendation
│   ├── data_model.py     #   CSV validation
│   └── explain.py        #   plain-English explanations
├── ui/                   # Design system, components, maps, charts, state
├── data/                 # Fictional demo dataset
├── docs/MATHEMATICS.md   # The maths in simple terms
├── tests/                # 27 automated tests for core/
└── .streamlit/config.toml
```

The one architectural rule: **`core/` never imports Streamlit or Plotly.** The optimizer can be
tested, or reused in a script or API, without the interface.

## Tests

```bash
python -m pytest -q      # 27 passed
python -m core.optimizer # quick command-line self-test on the demo data
```

## Deploy it (free)

1. Push this repository to GitHub.
2. Go to <https://share.streamlit.io>, sign in with GitHub and choose **New app**.
3. Select the repository, branch `main`, and main file `app.py`. Deploy.

## Assumptions and limitations

Stated plainly, because a planning tool that hides its assumptions is not a planning tool.

- **All cost, fuel, speed, rent and CO₂ constants are illustrative defaults**, editable in the app.
  Replace them with your own numbers before making real decisions.
- **Heuristic, not proven optimal.** Weighted k-means with restarts finds a strong solution, not a
  certified best one.
- **No route planning.** Trips are costed per neighborhood, not as multi-stop rounds.
- **Sites are map points.** A suggested location may not have buildable land.
- **Demand is static.** Growth is a what-if multiplier, not a forecast.
- **Uniform rent.** Real rents vary by site.

## Roadmap

- Snap candidate sites to a real-estate shortlist and solve the discrete problem exactly
  (p-median / capacitated facility location with an ILP solver).
- Per-site rent, multi-stop vehicle routing, demand forecasting with uncertainty.
- Real road distances from a routing service.

## Contributing

Issues and pull requests are welcome. Please run `python -m pytest -q` before submitting, and keep
`core/` free of UI imports.

## License

[MIT](LICENSE)
