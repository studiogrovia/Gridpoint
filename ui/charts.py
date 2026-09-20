"""
Chart builders with one shared look: transparent background (so the card shows
through), light horizontal gridlines only, value labels on the bars instead of
hunting along an axis, and no legend unless it carries information.
"""

import plotly.graph_objects as go

from .format import inr
from .theme import (CURRENT_SITE_COLOR, INK, LINE, MUTED, PLOTLY_FONT, PRIMARY,
                    WAREHOUSE_COLORS, warehouse_color)

CHART_CONFIG = {"displayModeBar": False}


def _base(fig: go.Figure, height: int, *, legend: bool = False, margin: dict = None) -> go.Figure:
    fig.update_layout(
        height=height, showlegend=legend,
        paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(0,0,0,0)",
        font=dict(family=PLOTLY_FONT, size=13, color=INK),
        margin=margin or dict(l=4, r=4, t=8, b=4),
        hoverlabel=dict(bgcolor="#FFFFFF", bordercolor=LINE,
                        font=dict(family=PLOTLY_FONT, size=13, color=INK)),
    )
    fig.update_xaxes(showgrid=False, zeroline=False, linecolor=LINE,
                     tickfont=dict(size=12, color=MUTED), title_font=dict(size=13, color=MUTED))
    fig.update_yaxes(gridcolor="#EEF2F7", zeroline=False, linecolor="rgba(0,0,0,0)",
                     tickfont=dict(size=12, color=MUTED), title_font=dict(size=13, color=MUTED))
    return fig


def hbar(labels: list, values: list, *, fmt, color: str = PRIMARY, colors: list = None) -> go.Figure:
    """Ranked horizontal bars with value labels (best for long neighborhood names)."""
    n = len(labels)
    top = max(values) if values else 1
    fig = go.Figure(go.Bar(
        x=values, y=labels, orientation="h", marker_color=colors or color,
        text=[fmt(v) for v in values], textposition="outside", cliponaxis=False,
        textfont=dict(size=12, color=INK), hovertemplate="%{y}: %{text}<extra></extra>",
    ))
    _base(fig, max(240, 34 * n + 40), margin=dict(l=4, r=48, t=4, b=4))
    fig.update_yaxes(autorange="reversed", automargin=True, showgrid=False, tickfont=dict(size=13, color=INK))
    fig.update_xaxes(range=[0, top * 1.05], showticklabels=False, showgrid=False)
    return fig


def demand_chart(df) -> go.Figure:
    d = df.sort_values("daily_orders", ascending=False)
    return hbar(d["name"].tolist(), d["daily_orders"].tolist(), fmt=lambda v: f"{int(v):,}")


def distance_chart(result: dict) -> go.Figure:
    served = [a for a in result["assignments"] if a["distance_km"] is not None]
    served.sort(key=lambda a: a["distance_km"], reverse=True)
    warehouses = result["warehouses"]
    colors = [warehouse_color(warehouses[a["warehouse"]]["warehouse_id"]) for a in served]
    return hbar([a["name"] for a in served], [a["distance_km"] for a in served],
                fmt=lambda v: f"{v:.1f} km", colors=colors)


def utilization_chart(result: dict) -> go.Figure:
    ws = result["warehouses"]
    util = [w["utilization"] * 100 for w in ws]
    fig = go.Figure(go.Bar(
        x=[w["warehouse_id"] for w in ws], y=util,
        marker_color=[warehouse_color(w["warehouse_id"]) for w in ws],
        text=[f"{u:.0f}%" for u in util], textposition="outside", cliponaxis=False,
        hovertemplate="%{x}: %{text} of capacity<extra></extra>",
    ))
    _base(fig, 280, margin=dict(l=4, r=4, t=24, b=4))
    fig.add_hline(y=100, line_dash="dot", line_color=MUTED, line_width=1,
                  annotation_text="Capacity", annotation_position="top left",
                  annotation_font=dict(size=12, color=MUTED))
    fig.update_yaxes(range=[0, max(115, (max(util) if util else 0) * 1.15)], ticksuffix="%")
    return fig


def cost_compare_chart(baseline: dict, result: dict) -> go.Figure:
    labels = ["Current (naive)", "GRIDPOINT"]
    values = [baseline["total_cost"], result["total_cost"]]
    fig = go.Figure(go.Bar(
        x=labels, y=values, marker_color=[CURRENT_SITE_COLOR, PRIMARY], width=0.5,
        text=[inr(v) for v in values], textposition="outside", cliponaxis=False,
        hovertemplate="%{x}: %{text} per day<extra></extra>",
    ))
    _base(fig, 280, margin=dict(l=4, r=4, t=24, b=4))
    fig.update_yaxes(range=[0, max(values) * 1.18], showticklabels=False)
    return fig


def tradeoff_chart(curve, rec: dict) -> go.Figure:
    fig = go.Figure()
    series = [
        ("Delivery cost", "delivery_cost", PRIMARY, 3),
        ("Infrastructure cost", "infrastructure_cost", WAREHOUSE_COLORS[1], 3),
        ("Total cost", "total_cost", INK, 4),
    ]
    for name, col, color, width in series:
        fig.add_trace(go.Scatter(
            x=curve["warehouses"], y=curve[col], name=name, mode="lines+markers",
            line=dict(color=color, width=width), marker=dict(size=8),
            hovertemplate=f"{name}: " + "\u20b9%{y:,.0f}/day<extra></extra>",
        ))
    _base(fig, 400, legend=True, margin=dict(l=4, r=8, t=8, b=4))
    fig.add_vline(x=rec["k"], line_dash="dash", line_color=MUTED, line_width=1,
                  annotation_text=f"Sweet spot: {rec['k']}", annotation_position="top",
                  annotation_font=dict(size=12, color=INK))
    fig.update_layout(legend=dict(orientation="h", y=-0.18, x=0, font=dict(size=13)))
    fig.update_xaxes(title_text="Number of warehouses", dtick=1)
    fig.update_yaxes(title_text="Estimated cost, \u20b9 per day", tickprefix="\u20b9", separatethousands=True)
    return fig
