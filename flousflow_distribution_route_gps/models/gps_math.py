# -*- coding: utf-8 -*-
"""Pure GPS math helpers (no ORM) — unit-testable in isolation."""
import datetime as dt
import math

# Mean Earth radius in meters (IUGG recommended mean radius R1).
EARTH_RADIUS_METERS = 6371008.8


def epoch_ms_to_datetime(ms):
    """Device GPS epoch timestamp (milliseconds) -> naive UTC datetime
    (Odoo server convention)."""
    return dt.datetime.fromtimestamp(ms / 1000.0, tz=dt.timezone.utc) \
        .replace(tzinfo=None)


def haversine_distance_meters(lat1, lon1, lat2, lon2):
    """Great-circle distance between two points, in meters.

    Haversine formula on a spherical Earth with the mean radius
    EARTH_RADIUS_METERS. Accuracy is within ~0.5% of geodesic
    distance, which is more than enough for geofencing.
    """
    phi1, phi2 = math.radians(lat1), math.radians(lat2)
    dphi = math.radians(lat2 - lat1)
    dlambda = math.radians(lon2 - lon1)
    a = (math.sin(dphi / 2.0) ** 2
         + math.cos(phi1) * math.cos(phi2) * math.sin(dlambda / 2.0) ** 2)
    a = min(1.0, max(0.0, a))
    return 2.0 * EARTH_RADIUS_METERS * math.asin(math.sqrt(a))


def is_valid_latitude(lat):
    return lat is not None and -90.0 <= lat <= 90.0


def is_valid_longitude(lon):
    return lon is not None and -180.0 <= lon <= 180.0


def is_valid_accuracy(accuracy):
    return accuracy is not None and accuracy >= 0.0
