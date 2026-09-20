"""Number formatting shared by every page."""


def num(value, decimals: int = 0) -> str:
    return f"{float(value):,.{decimals}f}"


def inr(value, decimals: int = 0, signed: bool = False) -> str:
    """Rupees with Indian digit grouping: 450000 -> ₹4,50,000."""
    v = float(value)
    negative = round(v, decimals) < 0
    v = abs(round(v, decimals))
    whole, _, frac = f"{v:.{decimals}f}".partition(".")
    if len(whole) > 3:
        head, tail = whole[:-3], whole[-3:]
        groups = []
        while len(head) > 2:
            groups.insert(0, head[-2:])
            head = head[:-2]
        if head:
            groups.insert(0, head)
        whole = ",".join(groups + [tail])
    sign = "\u2212" if negative else ("+" if signed else "")
    return f"{sign}\u20b9{whole}" + (f".{frac}" if frac else "")


def pct(value, decimals: int = 0, signed: bool = False) -> str:
    v = float(value)
    sign = "+" if signed and v > 0 else ("\u2212" if v < 0 else "")
    return f"{sign}{abs(v):.{decimals}f}%"
