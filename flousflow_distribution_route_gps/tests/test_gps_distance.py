# -*- coding: utf-8 -*-
from odoo.tests.common import tagged

from .gps_common import GpsCommon
from ..models.gps_math import (
    EARTH_RADIUS_METERS,
    haversine_distance_meters,
    is_valid_latitude,
    is_valid_longitude,
)


@tagged('post_install', '-at_install')
class TestGpsDistance(GpsCommon):

    def test_haversine_one_degree_longitude_on_equator(self):
        """1 degree of longitude on the equator = 2*pi*R/360."""
        expected = 2 * 3.141592653589793 * EARTH_RADIUS_METERS / 360.0
        distance = haversine_distance_meters(0.0, 0.0, 0.0, 1.0)
        self.assertAlmostEqual(distance, expected, delta=1.0)

    def test_haversine_one_degree_latitude(self):
        expected = 2 * 3.141592653589793 * EARTH_RADIUS_METERS / 360.0
        distance = haversine_distance_meters(0.0, 0.0, 1.0, 0.0)
        self.assertAlmostEqual(distance, expected, delta=1.0)

    def test_haversine_quarter_circumference(self):
        """(0,0) -> (0,90) is a quarter of the great circle."""
        expected = 3.141592653589793 * EARTH_RADIUS_METERS / 2.0
        distance = haversine_distance_meters(0.0, 0.0, 0.0, 90.0)
        self.assertAlmostEqual(distance, expected, delta=10.0)

    def test_haversine_same_point_is_zero(self):
        self.assertEqual(haversine_distance_meters(30.0, 31.0, 30.0, 31.0), 0.0)

    def test_haversine_known_reference_points(self):
        """Independent reference: Cairo Tahrir (30.0444, 31.2357) to
        Cairo Tower (30.0459, 31.2243) is about 1.15 km (publicly known
        straight-line distance, checked on a map)."""
        distance = haversine_distance_meters(
            30.0444, 31.2357, 30.0459, 31.2243)
        self.assertAlmostEqual(distance, 1150.0, delta=150.0)

    def test_haversine_symmetry(self):
        d1 = haversine_distance_meters(30.0100, 31.2400, 30.0150, 31.2410)
        d2 = haversine_distance_meters(30.0150, 31.2410, 30.0100, 31.2400)
        self.assertAlmostEqual(d1, d2, places=6)

    def test_valid_latitude_longitude_ranges(self):
        self.assertTrue(is_valid_latitude(-90.0))
        self.assertTrue(is_valid_latitude(90.0))
        self.assertTrue(is_valid_latitude(0.0))
        self.assertFalse(is_valid_latitude(90.0001))
        self.assertFalse(is_valid_latitude(-90.0001))
        self.assertTrue(is_valid_longitude(180.0))
        self.assertTrue(is_valid_longitude(-180.0))
        self.assertFalse(is_valid_longitude(180.0001))
        self.assertFalse(is_valid_longitude(None))
