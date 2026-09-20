"""
Distance calculations for GRIDPOINT.

We use the haversine formula (great-circle distance on a sphere) since all
our locations are given as latitude/longitude. This is a standard, defensible
choice for city-scale distance estimation and needs no external API or map data.
"""

import numpy as np

EARTH_RADIUS_KM = 6371.0

# Real road distance is always longer than straight-line ("as the crow flies")
# distance because of street layouts, one-ways, etc. We apply a fixed
# detour factor to approximate real driving distance. This is a documented
# assumption, not a measured value -- see README.
ROAD_DETOUR_FACTOR = 1.3


def haversine_km(lat1, lon1, lat2, lon2) -> float:
    """Great-circle distance between two points, in kilometers."""
    lat1, lon1, lat2, lon2 = map(np.radians, [lat1, lon1, lat2, lon2])
    dlat = lat2 - lat1
    dlon = lon2 - lon1
    a = np.sin(dlat / 2) ** 2 + np.cos(lat1) * np.cos(lat2) * np.sin(dlon / 2) ** 2
    c = 2 * np.arcsin(np.sqrt(a))
    return EARTH_RADIUS_KM * c


def road_distance_km(lat1, lon1, lat2, lon2) -> float:
    """Estimated road (driving) distance, applying the detour factor."""
    return haversine_km(lat1, lon1, lat2, lon2) * ROAD_DETOUR_FACTOR


def distance_matrix(points_a: np.ndarray, points_b: np.ndarray) -> np.ndarray:
    """
    points_a: (n, 2) array of [lat, lon]
    points_b: (m, 2) array of [lat, lon]
    returns: (n, m) matrix of estimated road distances in km
    """
    n = points_a.shape[0]
    m = points_b.shape[0]
    mat = np.zeros((n, m))
    for i in range(n):
        for j in range(m):
            mat[i, j] = road_distance_km(
                points_a[i, 0], points_a[i, 1], points_b[j, 0], points_b[j, 1]
            )
    return mat
