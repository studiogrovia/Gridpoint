"""
Abstract city layout helpers for the Demand Map page.

We draw neighborhoods as irregular "blob" polygons on a synthetic 2D canvas
(not real street-map tiles) so each neighborhood's drawn area roughly
matches its supplied area_m2, giving an intuitive sense of city shape
without needing real map geometry data.
"""

import numpy as np


def latlon_to_canvas(lat, lon, lat0, lon0, scale=90.0):
    """
    Project lat/lon to a flat x/y canvas, centered on (lat0, lon0), using a
    simple equirectangular projection. Fine at city scale; not meant for
    large-area geographic accuracy.
    """
    x = (np.asarray(lon) - lon0) * scale * np.cos(np.radians(lat0))
    y = (np.asarray(lat) - lat0) * scale
    return x, y


def generate_blob_polygon(cx, cy, area_m2, seed, irregularity=0.35, num_points=14):
    """
    Generate a closed irregular polygon centered at (cx, cy) on the canvas,
    whose area approximates area_m2 (in canvas units).

    We don't attempt exact area matching (unnecessary precision for a demo
    visualization) -- we size a base radius from the target area assuming a
    roughly circular footprint, then jitter each vertex radius so the shape
    looks like an organic neighborhood boundary rather than a perfect circle,
    while preserving relative sizing between neighborhoods.
    """
    rng = np.random.default_rng(seed)

    # Visual-scale calibration constant -- not a real unit conversion. It only
    # needs to preserve RELATIVE sizing between neighborhoods on the canvas.
    area_canvas = area_m2 / 45000.0
    base_radius = np.sqrt(area_canvas / np.pi)

    angles = np.linspace(0, 2 * np.pi, num_points, endpoint=False)
    angles += rng.uniform(-0.15, 0.15, size=num_points)
    radii = base_radius * (1 + rng.uniform(-irregularity, irregularity, size=num_points))

    xs = cx + radii * np.cos(angles)
    ys = cy + radii * np.sin(angles)
    return xs.tolist() + [xs[0]], ys.tolist() + [ys[0]]
