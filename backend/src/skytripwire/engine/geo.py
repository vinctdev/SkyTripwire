"""Spherical geometry helpers. Distances in nautical miles, angles in degrees."""

import math

EARTH_RADIUS_NM = 3440.065


def distance_nm(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    """Great-circle distance (haversine)."""
    phi1, phi2 = math.radians(lat1), math.radians(lat2)
    d_phi = phi2 - phi1
    d_lambda = math.radians(lon2 - lon1)
    a = math.sin(d_phi / 2) ** 2 + math.cos(phi1) * math.cos(phi2) * math.sin(d_lambda / 2) ** 2
    return 2 * EARTH_RADIUS_NM * math.asin(min(1.0, math.sqrt(a)))


def initial_bearing(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    """Initial bearing from point 1 to point 2, 0 to 360."""
    phi1, phi2 = math.radians(lat1), math.radians(lat2)
    d_lambda = math.radians(lon2 - lon1)
    y = math.sin(d_lambda) * math.cos(phi2)
    x = math.cos(phi1) * math.sin(phi2) - math.sin(phi1) * math.cos(phi2) * math.cos(d_lambda)
    return (math.degrees(math.atan2(y, x)) + 360) % 360


def destination(lat: float, lon: float, bearing: float, distance: float) -> tuple[float, float]:
    """Point reached from (lat, lon) after ``distance`` nm on the given initial bearing."""
    delta = distance / EARTH_RADIUS_NM
    theta = math.radians(bearing)
    phi1, lambda1 = math.radians(lat), math.radians(lon)
    phi2 = math.asin(
        math.sin(phi1) * math.cos(delta) + math.cos(phi1) * math.sin(delta) * math.cos(theta)
    )
    lambda2 = lambda1 + math.atan2(
        math.sin(theta) * math.sin(delta) * math.cos(phi1),
        math.cos(delta) - math.sin(phi1) * math.sin(phi2),
    )
    return math.degrees(phi2), (math.degrees(lambda2) + 540) % 360 - 180


def enclosing_circle(
    a: tuple[float, float, float], b: tuple[float, float, float]
) -> tuple[float, float, float]:
    """Smallest circle (lat, lon, radius) containing circles a and b (approximation on the sphere,
    exact along the great circle through both centers)."""
    lat1, lon1, r1 = a
    lat2, lon2, r2 = b
    d = distance_nm(lat1, lon1, lat2, lon2)
    if d + r2 <= r1:
        return a
    if d + r1 <= r2:
        return b
    radius = (d + r1 + r2) / 2
    lat, lon = destination(lat1, lon1, initial_bearing(lat1, lon1, lat2, lon2), radius - r1)
    return lat, lon, radius
