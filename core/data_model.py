"""
Data models and loading utilities for GRIDPOINT.

A "neighborhood" is one demand node in the city: it has a location,
a physical area, a daily order volume, and a traffic level.
"""

from dataclasses import dataclass
import os
import pandas as pd

REQUIRED_COLUMNS = ["name", "lat", "lon", "area_m2", "daily_orders", "traffic_level"]
VALID_TRAFFIC_LEVELS = {"Low", "Medium", "High"}

DEMO_DATA_PATH = os.path.join(os.path.dirname(__file__), "..", "data", "demo_bengaluru.csv")


@dataclass
class Neighborhood:
    id: str
    name: str
    lat: float
    lon: float
    area_m2: float
    daily_orders: int
    traffic_level: str


def load_demo_data() -> pd.DataFrame:
    """Load the fictional Bengaluru-style demo dataset."""
    df = pd.read_csv(DEMO_DATA_PATH)
    return validate_neighborhoods_df(df)


def _rows(mask) -> str:
    """Human-readable row list ("rows 2, 5 and 9") for error messages. Rows are 1-based data rows."""
    idx = [int(i) + 1 for i in mask[mask].index]
    shown = ", ".join(str(i) for i in idx[:5])
    if len(idx) > 5:
        shown += f" and {len(idx) - 5} more"
    return ("row " if len(idx) == 1 else "rows ") + shown


def validate_neighborhoods_df(df: pd.DataFrame) -> pd.DataFrame:
    """
    Check that an uploaded/entered dataframe has the columns GRIDPOINT needs,
    coerce types, and assign a stable neighborhood id if missing.
    Raises ValueError with a human-readable message (naming the offending
    rows) if something is wrong, so the UI can show it inline as-is.
    """
    missing = [c for c in REQUIRED_COLUMNS if c not in df.columns]
    if missing:
        raise ValueError(
            f"Your data is missing required column(s): {', '.join(missing)}. "
            f"Expected columns: {', '.join(REQUIRED_COLUMNS)}"
        )

    df = df.copy().reset_index(drop=True)
    if len(df) == 0:
        raise ValueError("Add at least one neighborhood to continue.")

    for col in ["lat", "lon", "area_m2"]:
        df[col] = pd.to_numeric(df[col], errors="coerce")
    df["daily_orders"] = pd.to_numeric(df["daily_orders"], errors="coerce").fillna(0).astype(int)

    bad_numeric = df[["lat", "lon", "area_m2"]].isna().any(axis=1)
    if bad_numeric.any():
        raise ValueError(
            f"Latitude, longitude and area must be numbers ({_rows(bad_numeric)}). Please fix and try again."
        )

    bad_lat = (df["lat"] < -90) | (df["lat"] > 90)
    if bad_lat.any():
        raise ValueError(f"Latitude must be between -90 and 90 ({_rows(bad_lat)}).")
    bad_lon = (df["lon"] < -180) | (df["lon"] > 180)
    if bad_lon.any():
        raise ValueError(f"Longitude must be between -180 and 180 ({_rows(bad_lon)}).")

    bad_area = df["area_m2"] <= 0
    if bad_area.any():
        raise ValueError(f"Area must be greater than zero ({_rows(bad_area)}).")
    bad_orders = df["daily_orders"] < 0
    if bad_orders.any():
        raise ValueError(f"Daily orders cannot be negative ({_rows(bad_orders)}).")

    bad_name = df["name"].isna() | (df["name"].astype(str).str.strip() == "")
    if bad_name.any():
        raise ValueError(f"Every neighborhood needs a name ({_rows(bad_name)}).")
    df["name"] = df["name"].astype(str).str.strip()

    bad_traffic = set(df["traffic_level"].dropna().unique()) - VALID_TRAFFIC_LEVELS
    if bad_traffic or df["traffic_level"].isna().any():
        found = sorted(str(v) for v in bad_traffic) or ["(blank)"]
        raise ValueError(
            f"traffic_level must be one of {sorted(VALID_TRAFFIC_LEVELS)}. "
            f"Found invalid value(s): {found}"
        )

    if "id" not in df.columns:
        df.insert(0, "id", [f"N{i+1:02d}" for i in range(len(df))])

    return df


def dataframe_to_neighborhoods(df: pd.DataFrame) -> list:
    return [
        Neighborhood(
            id=row["id"],
            name=row["name"],
            lat=row["lat"],
            lon=row["lon"],
            area_m2=row["area_m2"],
            daily_orders=row["daily_orders"],
            traffic_level=row["traffic_level"],
        )
        for _, row in df.iterrows()
    ]
