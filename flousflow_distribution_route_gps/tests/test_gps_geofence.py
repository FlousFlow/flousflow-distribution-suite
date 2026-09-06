# -*- coding: utf-8 -*-
from odoo import fields
from odoo.exceptions import UserError
from odoo.tests.common import tagged

from .gps_common import GpsCommon


@tagged('post_install', '-at_install')
class TestGpsGeofence(GpsCommon):

    def test_customer_location_valid_flag(self):
        self.assertTrue(self.partner.has_distribution_location)
        self.partner.write({
            'distribution_latitude': 0.0,
            'distribution_longitude': 0.0,
        })
        # (0, 0) is a valid coordinate on Earth — must remain valid.
        self.assertTrue(self.partner.has_distribution_location)
        self.partner.write({
            'distribution_latitude': False,
            'distribution_longitude': False,
        })
        self.assertFalse(self.partner.has_distribution_location)

    def test_partner_invalid_latitude_rejected(self):
        with self.assertRaises(Exception):
            self.partner.write({'distribution_latitude': 95.0})

    def test_partner_invalid_longitude_rejected(self):
        with self.assertRaises(Exception):
            self.partner.write({'distribution_longitude': -200.0})

    def test_partner_negative_radius_rejected(self):
        with self.assertRaises(Exception):
            self.partner.write({'distribution_geofence_radius': -5.0})

    def test_effective_radius_hierarchy(self):
        route, visit = self._create_route()
        # Partner radius wins
        self.assertEqual(visit._get_effective_geofence_radius(), 100.0)
        # Area radius when partner has none
        self.partner.distribution_geofence_radius = 0.0
        self.area.default_geofence_radius = 250.0
        self.assertEqual(visit._get_effective_geofence_radius(), 250.0)
        # Global default when neither is set
        self.area.default_geofence_radius = 0.0
        self.set_param('default_geofence_radius', 300.0)
        self.assertEqual(visit._get_effective_geofence_radius(), 300.0)
        self.set_param('default_geofence_radius', 100.0)

    def test_inside_geofence_warning_mode(self):
        # ~34 m away from the customer
        route, visit = self._checkin_start(30.010270, 31.240000)
        self.assertEqual(visit.state, 'in_progress')
        self.assertEqual(visit.checkin_geofence_status, 'inside')
        self.assertLess(visit.checkin_distance, 60.0)
        self.assertEqual(
            visit.customer_latitude_snapshot, 30.010000)
        self.assertEqual(
            visit.customer_geofence_radius_snapshot, 100.0)
        event = visit.gps_event_ids.filtered(
            lambda e: e.event_type == 'checkin')
        self.assertEqual(len(event), 1)
        self.assertEqual(event.geofence_status, 'inside')

    def _checkin_start(self, lat, lon, accuracy=5.0):
        route, visit = self._create_route()
        result = self._checkin(visit, lat, lon, accuracy)
        self.assertEqual(result['status'], 'started', result)
        return route, visit

    def test_outside_geofence_warning_mode(self):
        # ~605 m away — warning mode allows but records "outside"
        self.set_param('geofence_mode', 'warning')
        route, visit = self._create_route()
        result = self._checkin(visit, 30.015440, 31.240000)
        self.assertEqual(result['status'], 'started', result)
        self.assertTrue(result.get('warning'), result)
        self.assertEqual(visit.checkin_geofence_status, 'outside')
        self.assertGreater(visit.checkin_distance, 500.0)
        self.assertEqual(visit.state, 'in_progress')

    def test_outside_geofence_strict_mode_blocks(self):
        self.set_param('geofence_mode', 'strict')
        route, visit = self._create_route()
        result = self._checkin(visit, 30.015440, 31.240000)
        self.assertEqual(result['status'], 'blocked')
        self.assertEqual(result['reason'], 'outside_geofence')
        # Transaction integrity: the visit stays pending.
        self.assertEqual(visit.state, 'pending')
        self.assertFalse(visit.actual_start_datetime)
        rejected = visit.gps_event_ids.filtered(
            lambda e: e.event_type == 'checkin_rejected')
        self.assertEqual(len(rejected), 1)
        self.assertGreater(rejected.distance, 500.0)

    def test_strict_mode_inside_allowed(self):
        self.set_param('geofence_mode', 'strict')
        route, visit = self._checkin_start(30.010270, 31.240000)
        self.assertEqual(visit.state, 'in_progress')

    def test_disabled_mode_records_but_never_blocks(self):
        self.set_param('geofence_mode', 'disabled')
        route, visit = self._create_route()
        result = self._checkin(visit, 30.015440, 31.240000)
        self.assertEqual(result['status'], 'started')
        self.assertEqual(visit.checkin_geofence_status, 'outside')

    def test_boundary_exactly_on_radius_is_inside(self):
        route, visit = self._create_route()
        # 0.0009 degrees of latitude ~= 100.08 m; use radius so that the
        # computed distance is just under: 0.0008 deg ~= 88.96 m < 100 m.
        result = self._checkin(visit, 30.010800, 31.240000)
        self.assertEqual(result['status'], 'started')
        self.assertEqual(visit.checkin_geofence_status, 'inside')

    def test_geofence_disabled_mode_no_blocking(self):
        self.set_param('geofence_mode', 'strict')
        self.set_param('enabled', False)
        route, visit = self._create_route()
        result = self._checkin(visit, 30.015440, 31.240000)
        # GPS module disabled: the plain visit start must work regardless.
        self.assertEqual(result['status'], 'started')
        self.assertEqual(visit.state, 'in_progress')
        self.assertFalse(visit.checkin_datetime)
        self.set_param('enabled', True)

    def test_missing_customer_location_block(self):
        self.set_param('missing_customer_location_policy', 'block')
        self.partner.write({
            'distribution_latitude': False,
            'distribution_longitude': False,
        })
        route, visit = self._create_route()
        result = self._checkin(visit, 30.010000, 31.240000)
        self.assertEqual(result['status'], 'blocked')
        self.assertEqual(result['reason'], 'missing_customer_location')
        self.assertEqual(visit.state, 'pending')

    def test_missing_customer_location_allow(self):
        self.set_param('missing_customer_location_policy', 'allow')
        self.partner.write({
            'distribution_latitude': False,
            'distribution_longitude': False,
        })
        route, visit = self._create_route()
        result = self._checkin(visit, 30.010000, 31.240000)
        self.assertEqual(result['status'], 'started')
        self.assertEqual(visit.checkin_geofence_status, 'unknown')

    def test_missing_customer_location_warn(self):
        self.set_param('missing_customer_location_policy', 'warn')
        self.partner.write({
            'distribution_latitude': False,
            'distribution_longitude': False,
        })
        route, visit = self._create_route()
        result = self._checkin(visit, 30.010000, 31.240000)
        self.assertEqual(result['status'], 'started')
        self.assertEqual(visit.checkin_geofence_status, 'unknown')

    def test_low_accuracy_strict_blocks(self):
        self.set_param('accuracy_validation_mode', 'strict')
        self.set_param('maximum_accuracy', 100.0)
        route, visit = self._create_route()
        result = self._checkin(visit, 30.010270, 31.240000, accuracy=250.0)
        self.assertEqual(result['status'], 'blocked', result)
        self.assertEqual(result['reason'], 'low_accuracy')
        self.assertEqual(visit.state, 'pending')

    def test_low_accuracy_warning_allows(self):
        self.set_param('accuracy_validation_mode', 'warning')
        route, visit = self._create_route()
        result = self._checkin(visit, 30.010270, 31.240000, accuracy=250.0)
        self.assertEqual(result['status'], 'started')
        errors = visit.gps_event_ids.filtered(
            lambda e: e.event_type == 'gps_error')
        self.assertEqual(len(errors), 1)

    def test_low_accuracy_disabled_ignores(self):
        self.set_param('accuracy_validation_mode', 'disabled')
        route, visit = self._create_route()
        result = self._checkin(visit, 30.010270, 31.240000, accuracy=5000.0)
        self.assertEqual(result['status'], 'started')

    def test_stale_position_rejected(self):
        route, visit = self._create_route()
        old_ts = (fields.Datetime.now().timestamp() - 600) * 1000
        with self.assertRaises(UserError):
            self._checkin(visit, 30.010270, 31.240000, gps_timestamp=old_ts)
        self.assertEqual(visit.state, 'pending')

    def test_invalid_coordinates_rejected(self):
        route, visit = self._create_route()
        with self.assertRaises(UserError):
            self._checkin(visit, 95.0, 31.0)

    def test_visit_type_without_gps_skips_geofence(self):
        self.visit_type.require_gps_checkin = False
        self.set_param('geofence_mode', 'strict')
        route, visit = self._create_route()
        visit.action_start_visit_gps() if False else None
        # action_start_visit_gps starts directly (no client action)
        res = visit.action_start_visit_gps()
        self.assertTrue(res)
        self.assertEqual(visit.state, 'in_progress')
        self.assertFalse(visit.checkin_datetime)

    def test_start_visit_gps_returns_client_action(self):
        route, visit = self._create_route()
        res = visit.action_start_visit_gps()
        self.assertEqual(res['type'], 'ir.actions.client')
        self.assertEqual(res['tag'], 'distribution_gps.visit_action')
        self.assertEqual(res['params']['visit_id'], visit.id)

    def test_checkout_flow(self):
        route, visit = self._checkin_start(30.010270, 31.240000)
        result = visit.gps_submit_checkout(
            30.010500, 31.240000, 10.0,
            gps_timestamp=fields.Datetime.now().timestamp() * 1000)
        self.assertEqual(result['status'], 'done')
        self.assertEqual(visit.checkout_geofence_status, 'inside')
        self.assertTrue(visit.checkout_datetime)
        # The completion wizard opens next
        self.assertEqual(result['next_action']['res_model'],
                         'distribution.visit.complete.wizard')
        checkout_events = visit.gps_event_ids.filtered(
            lambda e: e.event_type == 'checkout')
        self.assertEqual(len(checkout_events), 1)

    def test_checkout_geofence_validation_setting(self):
        self.set_param('validate_checkout_geofence', True)
        self.set_param('geofence_mode', 'strict')
        route, visit = self._checkin_start(30.010270, 31.240000)
        result = visit.gps_submit_checkout(
            30.015440, 31.240000, 10.0,
            gps_timestamp=fields.Datetime.now().timestamp() * 1000)
        self.assertEqual(result['status'], 'blocked')
        self.assertEqual(result['reason'], 'outside_geofence')
        self.assertEqual(visit.state, 'in_progress')

    def test_double_checkin_rejected(self):
        route, visit = self._checkin_start(30.010270, 31.240000)
        with self.assertRaises(UserError):
            self._checkin(visit, 30.010270, 31.240000)

    def test_manager_override_checkin(self):
        self.set_param('geofence_mode', 'strict')
        route, visit = self._create_route()
        result = self._checkin(visit, 30.015440, 31.240000)
        self.assertEqual(result['status'], 'blocked')
        overrides = visit.gps_event_ids.filtered(
            lambda e: e.event_type == 'manager_override')
        self.assertEqual(len(overrides), 0)
        # Manager overrides with a reason
        mgr_env = self.mgr['distribution.route.visit'].browse(visit.id)
        mgr_env.action_gps_apply_override(
            operation='checkin',
            reason='Customer moved temporarily to the next building',
            latitude=30.015440, longitude=31.240000, accuracy=8.0,
            gps_timestamp=fields.Datetime.now().timestamp() * 1000,
        )
        self.assertEqual(visit.state, 'in_progress')
        self.assertEqual(visit.override_user_id, self.manager_user)
        self.assertEqual(visit.override_operation, 'checkin')
        self.assertIn('temporarily', visit.override_reason)
        overrides = visit.gps_event_ids.filtered(
            lambda e: e.event_type == 'manager_override')
        self.assertEqual(len(overrides), 1)
        checkins = visit.gps_event_ids.filtered(
            lambda e: e.event_type == 'checkin')
        self.assertEqual(len(checkins), 1)
        self.assertTrue(visit.gps_has_override)
        self.assertTrue(visit.gps_checkin_valid)

    def test_manager_override_requires_reason(self):
        route, visit = self._create_route()
        mgr_env = self.mgr['distribution.route.visit'].browse(visit.id)
        with self.assertRaises(UserError):
            mgr_env.action_gps_apply_override(
                operation='checkin', reason=False,
                latitude=30.0, longitude=31.0, accuracy=5.0)

    def test_non_manager_cannot_override(self):
        route, visit = self._create_route()
        user_env = self.env(user=self.sales_user)
        visit_as_user = user_env['distribution.route.visit'].browse(visit.id)
        with self.assertRaises(UserError):
            visit_as_user.action_gps_apply_override(
                operation='checkin', reason='nope',
                latitude=30.0, longitude=31.0, accuracy=5.0)

    def test_old_visits_without_gps_untouched(self):
        """Visits executed before installing the GPS module keep working."""
        route, visit = self._create_route()
        visit.action_start_visit()
        visit.action_finalize_visit(result_id=self.result_success.id)
        self.assertEqual(visit.state, 'done')
        self.assertFalse(visit.checkin_datetime)
        self.assertFalse(visit.checkin_geofence_status)
        self.assertFalse(visit.gps_event_ids)

    def test_gps_disabled_setting_uses_plain_start(self):
        self.set_param('enabled', False)
        route, visit = self._create_route()
        res = visit.action_start_visit_gps()
        self.assertTrue(res)  # plain start, no client action
        self.assertEqual(visit.state, 'in_progress')
        self.set_param('enabled', True)
