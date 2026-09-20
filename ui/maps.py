"""
Plotly map builders.

Visual language (kept identical on every page so the legend never changes):
  * Coloured circle .......... a neighborhood. Size = orders/day, colour = the
                               warehouse that serves it (or traffic level on the
                               plain demand map).
  * Thin line ................ a delivery assignment, in the warehouse's colour.
  * Large navy circle + ring . a proposed warehouse, labelled W1, W2...
                               Size grows with capacity utilisation.
  * Grey ring ................ a current (naive-layout) site, optional layer.
  * Grey circle .............. a neighborhood that could not be served.
  * Red circle ............... a warehouse that is offline (Disruption mode).

Only warehouses carry on-map labels; neighborhood names appear on hover, which
is what keeps a dense city readable without overlapping text. The basemap is
Carto Positron, a deliberately quiet grey map so the data is the loudest thing.
"""

import html
import zlib

import numpy as np
import plotly.graph_objects as go

from core.geometry import latlon_to_canvas, generate_blob_polygon
from .theme import (CURRENT_SITE_COLOR, DANGER, INK, LINE, PAPER, PLOTLY_FONT, TRAFFIC_COLORS,
                    UNSERVED_COLOR, warehouse_color)

MAP_STYLE = "carto-positron"


def _esc(value) -> str:
    return html.escape(str(value), quote=False)


def _bubble_sizes(orders, max_orders: float) -> list:
    """Area-proportional sizing: diameter scales with sqrt(orders)."""
    orders = np.asarray(orders, dtype=float)
    return (10 + 24 * np.sqrt(np.clip(orders, 0, None) / max(max_orders, 1))).tolist()


def _center_zoom(lats, lons, width_px: int = 520):
    """Centre and zoom that frame every point with some padding (no fixed city assumed)."""
    lats, lons = np.asarray(lats, dtype=float), np.asarray(lons, dtype=float)
    lat_c, lon_c = (lats.min() + lats.max()) / 2, (lons.min() + lons.max()) / 2
    lat_span = max(lats.max() - lats.min(), 0.01) * 1.35
    lon_span = max((lons.max() - lons.min()) * np.cos(np.radians(lat_c)), 0.01) * 1.35
    zoom = float(np.log2(360 * width_px / (512 * max(lat_span, lon_span))))
    return {"lat": float(lat_c), "lon": float(lon_c)}, float(np.clip(zoom, 3, 15))


def _finish(fig, lats, lons, height: int) -> go.Figure:
    center, zoom = _center_zoom(lats, lons)
    fig.update_layout(
        map=dict(style=MAP_STYLE, center=center, zoom=zoom),
        height=height, margin=dict(l=0, r=0, t=0, b=0), showlegend=False,
        paper_bgcolor="rgba(0,0,0,0)",
        hoverlabel=dict(bgcolor="#FFFFFF", bordercolor=LINE,
                        font=dict(family=PLOTLY_FONT, size=13, color=INK)),
    )
    return fig


# --- Locations page -------------------------------------------------------
def build_demand_map(df, height: int = 480) -> go.Figure:
    """Where the neighborhoods are. Size = orders/day, colour = traffic level."""
    fig = go.Figure()
    max_orders = max(int(df["daily_orders"].max()), 1)
    for level in ("Low", "Medium", "High"):
        sub = df[df["traffic_level"] == level]
        if sub.empty:
            continue
        hover = [
            f"<b>{_esc(r['name'])}</b><br>{int(r['daily_orders']):,} orders/day"
            f"<br>{r['area_m2']:,.0f} m\u00b2 \u00b7 {level} traffic"
            for _, r in sub.iterrows()
        ]
        fig.add_trace(go.Scattermap(
            lat=sub["lat"].tolist(), lon=sub["lon"].tolist(), mode="markers",
            marker=dict(size=_bubble_sizes(sub["daily_orders"], max_orders),
                        color=TRAFFIC_COLORS[level], opacity=0.85),
            hovertext=hover, hoverinfo="text", showlegend=False,
        ))
    return _finish(fig, df["lat"], df["lon"], height)


def build_area_map(df, height: int = 480) -> go.Figure:
    """
    Abstract 'area view': each neighborhood drawn as a patch sized by its area
    and shaded by demand. No street map, so it works for any coordinates.
    """
    lat0, lon0 = df["lat"].mean(), df["lon"].mean()
    xs, ys = latlon_to_canvas(df["lat"].to_numpy(), df["lon"].to_numpy(), lat0, lon0)
    coords = np.column_stack([xs, ys])
    max_orders = max(int(df["daily_orders"].max()), 1)
    fig = go.Figure()

    # Faint links between each neighborhood and its nearest neighbour, for context.
    drawn = set()
    for i in range(len(df)):
        d = np.linalg.norm(coords - coords[i], axis=1)
        d[i] = np.inf
        j = int(np.argmin(d))
        pair = frozenset((i, j))
        if len(df) > 1 and pair not in drawn:
            drawn.add(pair)
            fig.add_trace(go.Scatter(
                x=[coords[i, 0], coords[j, 0]], y=[coords[i, 1], coords[j, 1]], mode="lines",
                line=dict(color="#C5CFDD", width=1.5, dash="dot"), hoverinfo="skip", showlegend=False))

    light, dark = np.array([214, 227, 251]), np.array([20, 52, 140])
    for i, row in df.reset_index(drop=True).iterrows():
        # crc32 (not hash()) so the shapes are identical on every restart.
        seed = zlib.crc32(str(row["id"]).encode())
        px, py = generate_blob_polygon(coords[i, 0], coords[i, 1], row["area_m2"], seed=seed)
        t = row["daily_orders"] / max_orders
        r, g, b = (light + (dark - light) * t).astype(int)
        fig.add_trace(go.Scatter(
            x=px, y=py, fill="toself", mode="lines",
            line=dict(color="rgba(255,255,255,.9)", width=1.5), fillcolor=f"rgba({r},{g},{b},0.9)",
            text=(f"<b>{_esc(row['name'])}</b><br>{int(row['daily_orders']):,} orders/day<br>"
                  f"{row['area_m2']:,.0f} m\u00b2 \u00b7 {row['traffic_level']} traffic"),
            hoverinfo="text", showlegend=False))

    fig.update_layout(
        height=height, showlegend=False, plot_bgcolor=PAPER, paper_bgcolor="rgba(0,0,0,0)",
        xaxis=dict(visible=False), yaxis=dict(visible=False, scaleanchor="x"),
        margin=dict(l=0, r=0, t=0, b=0),
        hoverlabel=dict(bgcolor="#FFFFFF", bordercolor=LINE,
                        font=dict(family=PLOTLY_FONT, size=13, color=INK)),
    )
    return fig


# --- Results / Dashboard / Disruption ---------------------------------------
def _hub(fig, lat, lon, label, size, core_color, hover) -> None:
    """A warehouse: white halo underneath, coloured core on top, label centred."""
    fig.add_trace(go.Scattermap(
        lat=[lat], lon=[lon], mode="markers", marker=dict(size=size + 9, color="#FFFFFF", opacity=0.95),
        hoverinfo="skip", showlegend=False))
    fig.add_trace(go.Scattermap(
        lat=[lat], lon=[lon], mode="markers+text", marker=dict(size=size, color=core_color),
        text=[label], textposition="middle center", textfont=dict(color="#FFFFFF", size=12, family=PLOTLY_FONT),
        hovertext=[hover], hoverinfo="text", showlegend=False))


def build_network_map(df, result: dict, *, baseline: dict = None, show_lines: bool = True,
                      show_current: bool = False, offline: dict = None, height: int = 520) -> go.Figure:
    """
    The recommended network. `result` is an optimizer result whose assignments
    line up row-for-row with `df`. Pass `baseline` with show_current=True to
    overlay the current (naive) sites; pass `offline` (a warehouse dict) to
    mark a failed warehouse during a disruption.
    """
    df = df.reset_index(drop=True)
    warehouses = result["warehouses"]
    max_orders = max(int(df["daily_orders"].max()), 1)
    fig = go.Figure()
    all_lats, all_lons = list(df["lat"]), list(df["lon"])

    # 1. Current (naive) sites, underneath everything else.
    if show_current and baseline:
        for w in baseline["warehouses"]:
            all_lats.append(w["lat"]); all_lons.append(w["lon"])
            fig.add_trace(go.Scattermap(
                lat=[w["lat"]], lon=[w["lon"]], mode="markers",
                marker=dict(size=30, color=CURRENT_SITE_COLOR, opacity=0.95),
                hoverinfo="skip", showlegend=False))
            fig.add_trace(go.Scattermap(
                lat=[w["lat"]], lon=[w["lon"]], mode="markers", marker=dict(size=19, color="#FFFFFF"),
                hovertext=[f"Current site (naive layout)<br>{w['assigned_orders']:,} orders/day assigned"],
                hoverinfo="text", showlegend=False))

    # 2. Delivery assignments: one trace per warehouse (None breaks the line).
    if show_lines:
        for idx, w in enumerate(warehouses):
            lats, lons = [], []
            for i, a in enumerate(result["assignments"]):
                if a["warehouse"] == idx:
                    lats += [df.loc[i, "lat"], w["lat"], None]
                    lons += [df.loc[i, "lon"], w["lon"], None]
            if lats:
                fig.add_trace(go.Scattermap(
                    lat=lats, lon=lons, mode="lines",
                    line=dict(width=1.6, color=warehouse_color(w["warehouse_id"])),
                    opacity=0.55, hoverinfo="skip", showlegend=False))

    # 3. Neighborhoods, one trace per serving warehouse (plus unserved).
    groups = {}
    for i, a in enumerate(result["assignments"]):
        groups.setdefault(a["warehouse"], []).append(i)
    for key, members in groups.items():
        sub = df.loc[members]
        if key is None:
            color, name = UNSERVED_COLOR, "Unserved"
        else:
            color, name = warehouse_color(warehouses[key]["warehouse_id"]), warehouses[key]["warehouse_id"]
        hover = []
        for i in members:
            a, r = result["assignments"][i], df.loc[i]
            if key is None:
                detail = "<b>Unserved</b> \u2013 outside capacity or radius limits"
            else:
                detail = f"Served by <b>{name}</b> \u00b7 {a['distance_km']:.1f} km \u00b7 ~{a['delivery_minutes']:.0f} min"
            hover.append(f"<b>{_esc(r['name'])}</b><br>{int(r['daily_orders']):,} orders/day<br>{detail}")
        fig.add_trace(go.Scattermap(
            lat=sub["lat"].tolist(), lon=sub["lon"].tolist(), mode="markers",
            marker=dict(size=_bubble_sizes(sub["daily_orders"], max_orders), color=color, opacity=0.88),
            hovertext=hover, hoverinfo="text", showlegend=False))

    # 4. Proposed warehouses, on top.
    for w in warehouses:
        all_lats.append(w["lat"]); all_lons.append(w["lon"])
        size = 28 + 14 * min(w["utilization"], 1.2)
        hover = (f"<b>{w['warehouse_id']}</b> \u00b7 proposed warehouse<br>"
                 f"{w['assigned_orders']:,} of {int(w['capacity']):,} orders/day "
                 f"({w['utilization'] * 100:.0f}%)")
        _hub(fig, w["lat"], w["lon"], w["warehouse_id"], size, INK, hover)

    # 5. A failed warehouse (disruption mode).
    if offline:
        all_lats.append(offline["lat"]); all_lons.append(offline["lon"])
        _hub(fig, offline["lat"], offline["lon"], offline["warehouse_id"], 34, DANGER,
             f"<b>{offline['warehouse_id']}</b> \u00b7 offline")

    return _finish(fig, all_lats, all_lons, height)
