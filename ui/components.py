"""
Reusable presentational components.

Every function here renders something; none of them decide *what* to show or
touch the optimizer. HTML is built as single-line strings (no indentation, no
blank lines) because Streamlit's markdown parser turns indented lines into
code blocks. Anything that can come from user data (neighborhood names from a
CSV, for instance) is escaped.
"""

import html

import streamlit as st

from .theme import WAREHOUSE_COLORS


def _e(value) -> str:
    return html.escape(str(value), quote=True)


def _md(markup: str) -> None:
    st.markdown(markup, unsafe_allow_html=True)


# --- Buttons ------------------------------------------------------------
def button(label: str, *, key: str, kind: str = "secondary", icon: str = None,
           disabled: bool = False, help: str = None) -> bool:
    """
    One button style everywhere: `kind="primary"` for the single main action on
    a page, `"secondary"` for everything else. Full width inside its column so
    touch targets stay large on phones.

    Streamlit renamed `use_container_width` to `width="stretch"`; we try the
    new spelling first and fall back so the app works on either.
    """
    kwargs = dict(key=key, type=kind, disabled=disabled, help=help)
    if icon:
        kwargs["icon"] = icon
    try:
        return st.button(label, width="stretch", **kwargs)
    except Exception:
        return st.button(label, use_container_width=True, **kwargs)


def stretch(fn, *args, **kwargs):
    """Call a Streamlit element with 'fill the container' width, on old or new Streamlit."""
    try:
        return fn(*args, width="stretch", **kwargs)
    except Exception:
        return fn(*args, use_container_width=True, **kwargs)


# --- Layout -------------------------------------------------------------
def card(key: str):
    """A white, rounded content card. `key` must be unique on the page."""
    return st.container(key=f"gpcard_{key}")


def card_header(title: str, description: str = None) -> None:
    desc = f'<p class="gp-card__desc">{_e(description)}</p>' if description else ""
    _md(f'<div class="gp-card__head"><div class="gp-card__title">{_e(title)}</div>{desc}</div>')


def status_pill(kind: str, text: str) -> str:
    return f'<span class="gp-pill gp-pill--{_e(kind)}"><span class="gp-pill__dot"></span>{_e(text)}</span>'


def page_header(title: str, subtitle: str = None, status: tuple = None) -> None:
    pill = status_pill(*status) if status else ""
    sub = f'<p class="gp-sub">{_e(subtitle)}</p>' if subtitle else ""
    _md(
        f'<div class="gp-head"><div class="gp-head__row">'
        f'<div class="gp-title" role="heading" aria-level="1">{_e(title)}</div>{pill}</div>{sub}</div>'
    )


def stepper(current: str, done: dict) -> None:
    """
    Three-step tracker for the real sequence Locations -> Optimization -> Results.
    `done` maps step key -> bool so the tracker reflects actual progress.
    """
    steps = [("locations", "Locations"), ("optimization", "Optimization"), ("results", "Results")]
    parts = []
    for i, (key, label) in enumerate(steps):
        if key == current:
            state, glyph = "current", str(i + 1)
        elif done.get(key):
            state, glyph = "done", "\u2713"
        else:
            state, glyph = "todo", str(i + 1)
        aria = ' aria-current="step"' if state == "current" else ""
        parts.append(
            f'<div class="gp-step gp-step--{state}"{aria}>'
            f'<span class="gp-step__dot">{glyph}</span><span>{_e(label)}</span></div>'
        )
        if i < len(steps) - 1:
            bar_done = " gp-step__bar--done" if done.get(key) and key != current else ""
            parts.append(f'<div class="gp-step__bar{bar_done}"></div>')
    _md(f'<nav class="gp-steps" aria-label="Progress">{"".join(parts)}</nav>')


def _tip(text: str) -> str:
    if not text:
        return ""
    return f'<span class="gp-tip" tabindex="0" role="note" aria-label="{_e(text)}" data-tip="{_e(text)}">i</span>'


def kpi_grid(items: list, *, cols: int = None, compact: bool = False) -> None:
    """
    items: dicts with label, value and optional sub, help, tone
    ("positive" | "negative"), hero (bool, spans two columns), text (bool,
    smaller value for words instead of numbers). The grid reflows 5 -> 3 -> 2
    columns on tablet and phone.
    """
    cols = cols or min(max(len(items), 2), 5)
    cells = []
    for it in items:
        cls = ["gp-kpi"]
        if it.get("hero"):
            cls.append("gp-kpi--hero")
        if it.get("text"):
            cls.append("gp-kpi--text")
        if it.get("tone"):
            cls.append(f"gp-kpi--{it['tone']}")
        sub = f'<div class="gp-kpi__sub">{_e(it["sub"])}</div>' if it.get("sub") else ""
        cells.append(
            f'<div class="{" ".join(cls)}"><div class="gp-kpi__label"><span>{_e(it["label"])}</span>'
            f'{_tip(it.get("help"))}</div><div class="gp-kpi__value">{_e(it["value"])}</div>{sub}</div>'
        )
    extra = " gp-kpis--compact" if compact else ""
    _md(f'<div class="gp-kpis gp-kpis--{cols}{extra}">{"".join(cells)}</div>')


def savings_panel(label: str, value: str, sub: str, good: bool) -> None:
    """The one dark panel: the headline number the whole tool exists to produce."""
    cls = "gp-hero__value gp-hero__value--good" if good else "gp-hero__value"
    _md(
        f'<div class="gp-hero"><div class="gp-hero__label">{_e(label)}</div>'
        f'<div class="{cls}">{_e(value)}</div><div class="gp-hero__sub">{_e(sub)}</div></div>'
    )


def summary_rows(rows: list) -> None:
    """Label/value rows, e.g. for the plan summary."""
    body = "".join(
        f'<div class="gp-row"><span class="gp-row__k">{_e(k)}</span><span class="gp-row__v">{_e(v)}</span></div>'
        for k, v in rows
    )
    _md(f'<div class="gp-rows">{body}</div>')


def empty_state(title: str, body: str) -> None:
    """An empty screen is an invitation: say what is missing and what to do."""
    _md(f'<div class="gp-empty"><div class="gp-empty__title">{_e(title)}</div><p class="gp-empty__body">{_e(body)}</p></div>')


# --- Map legend ---------------------------------------------------------
def legend(items: list) -> None:
    """
    items: (kind, label[, color]) tuples. kinds: dot, dots, hub, ring, line.
    For 'dots' the third element is a list of colours.
    """
    out = []
    for item in items:
        kind, label = item[0], item[1]
        color = item[2] if len(item) > 2 else None
        if kind == "dot":
            sw = f'<span class="gp-sw gp-sw--dot" style="background:{_e(color)}"></span>'
        elif kind == "dots":
            dots = "".join(f'<i style="background:{_e(c)}"></i>' for c in (color or WAREHOUSE_COLORS[:3]))
            sw = f'<span class="gp-sw gp-sw--dots">{dots}</span>'
        elif kind == "hub":
            sw = '<span class="gp-sw gp-sw--hub"></span>'
        elif kind == "ring":
            sw = f'<span class="gp-sw gp-sw--ring" style="--gp-ring:{_e(color)}"></span>'
        else:
            sw = f'<span class="gp-sw gp-sw--line" style="--gp-line-c:{_e(color)}"></span>'
        out.append(f'<span class="gp-legend__item">{sw}<span>{_e(label)}</span></span>')
    _md(f'<div class="gp-legend" role="list">{"".join(out)}</div>')


# --- Loading states -----------------------------------------------------
def skeleton_kpis(n: int = 4, cols: int = None):
    """Placeholder KPI cards. Returns the placeholder so the caller can .empty() it."""
    ph = st.empty()
    cols = cols or min(max(n, 2), 5)
    cells = '<div class="gp-kpi"><div class="gp-skel" style="height:.9rem;width:55%"></div>' \
            '<div class="gp-skel" style="height:1.8rem;width:75%;margin-top:.7rem"></div></div>' * n
    ph.markdown(
        f'<div class="gp-kpis gp-kpis--{cols}" aria-busy="true" aria-label="Loading">{cells}</div>',
        unsafe_allow_html=True,
    )
    return ph


def skeleton_block(height_px: int = 320):
    ph = st.empty()
    ph.markdown(
        f'<div class="gp-skel" aria-busy="true" aria-label="Loading" style="height:{int(height_px)}px"></div>',
        unsafe_allow_html=True,
    )
    return ph


# --- Comparison table ---------------------------------------------------
def delta_chip(base: float, new: float, *, lower_is_better: bool = True, unit: str = "%") -> str:
    """A '-12%' style chip, green when the change is an improvement."""
    if base in (0, None) or new is None:
        return '<span class="gp-delta">\u2014</span>'
    change = (new - base) / abs(base) * 100
    if abs(change) < 0.05:
        return '<span class="gp-delta">No change</span>'
    improved = (change < 0) == lower_is_better
    sign = "+" if change > 0 else "\u2212"
    cls = "gp-delta--good" if improved else "gp-delta--bad"
    return f'<span class="gp-delta {cls}">{sign}{abs(change):.0f}{unit}</span>'


def comparison_table(headers: list, rows: list, total_row: int = None) -> None:
    """
    rows: lists of cell strings; cells starting with '<' are treated as
    trusted HTML (delta chips), everything else is escaped.
    """
    head = "".join(f"<th>{_e(h)}</th>" for h in headers)
    body = []
    for i, row in enumerate(rows):
        cells = "".join(
            f"<td>{c if str(c).startswith('<') else _e(c)}</td>" for c in row
        )
        cls = ' class="gp-total"' if total_row is not None and i == total_row else ""
        body.append(f"<tr{cls}>{cells}</tr>")
    _md(f'<div class="gp-table-wrap"><table class="gp-table"><thead><tr>{head}</tr></thead><tbody>{"".join(body)}</tbody></table></div>')


# --- First-visit welcome --------------------------------------------------
def welcome_panel() -> None:
    steps = [
        ("1", "Load neighborhoods", "Upload a CSV, type rows in, or start with the sample city."),
        ("2", "Set your limits", "Choose how many warehouses, their capacity and the longest delivery radius."),
        ("3", "Read the plan", "See where to build, who each warehouse serves, and what it saves."),
    ]
    items = "".join(
        f'<div class="gp-how__item"><div class="gp-how__n">Step {n}</div>'
        f'<div class="gp-how__t">{_e(t)}</div><div class="gp-how__d">{_e(d)}</div></div>'
        for n, t, d in steps
    )
    _md(
        '<div class="gp-welcome">'
        '<div class="gp-welcome__title" role="heading" aria-level="1">Plan your warehouse network before you build it</div>'
        '<p class="gp-welcome__lead">Give GRIDPOINT your neighborhoods and daily orders. It recommends how many '
        'warehouses to build, where to put them, which neighborhoods each one serves, and what that costs '
        'compared with the obvious layout.</p>'
        f'<div class="gp-how">{items}</div></div>'
    )
