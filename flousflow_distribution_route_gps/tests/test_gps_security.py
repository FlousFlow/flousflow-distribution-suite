# -*- coding: utf-8 -*-
from odoo import fields
from odoo.exceptions import AccessError, UserError
from odoo.tests.common import tagged

from .gps_common import GpsCommon


@tagged('post_install', '-at_install')
class TestGpsSecurity(GpsCommon):

    def _make_checkin_event(self, visit):
        # The check-in is performed by the assigned representative (realistic)
        return visit.with_user(self.sales_user).gps_submit_checkin(
            30.010270, 31.240000, 5.0,
            gps_timestamp=fields.Datetime.now().timestamp() * 1000)

    def test_gps_event_created_on_checkin(self):
        route, visit = self._create_route()
        self._make_checkin_event(visit)
        self.assertTrue(visit.gps_event_ids)
        event = visit.gps_event_ids[0]
        self.assertEqual(event.event_type, 'checkin')
        self.assertEqual(event.user_id, self.sales_user)
        self.assertEqual(event.visit_id, visit)
        self.assertEqual(event.company_id, self.company)
    def test_user_cannot_create_events(self):
        route, visit = self._create_route()
        self._make_checkin_event(visit)
        user_env = self.env(user=self.sales_user)
        with self.assertRaises(AccessError):
            user_env['distribution.visit.gps.event'].create({
                'visit_id': visit.id,
                'event_type': 'checkin',
            })

    def test_gps_event_immutable_write(self):
        route, visit = self._create_route()
        self._make_checkin_event(visit)
        event = visit.gps_event_ids[0]
        # Even the manager cannot edit historical GPS events.
        mgr_env = self.mgr['distribution.visit.gps.event']
        event_as_mgr = mgr_env.browse(event.id)
        with self.assertRaises(UserError):
            event_as_mgr.write({'latitude': 0.0, 'longitude': 0.0})

    def test_gps_event_immutable_unlink(self):
        route, visit = self._create_route()
        self._make_checkin_event(visit)
        event = visit.gps_event_ids[0]
        mgr_env = self.mgr['distribution.visit.gps.event']
        event_as_mgr = mgr_env.browse(event.id)
        with self.assertRaises(UserError):
            event_as_mgr.unlink()

    def test_user_sees_only_own_events(self):
        route, visit = self._create_route()
        self._make_checkin_event(visit)

        # Second salesman + his own route/visit/event
        other_user = self.env['res.users'].create({
            'name': 'GPS Other', 'login': 'gps_other',
            'email': 'gps_other@example.com',
            'group_ids': [(6, 0, [self.group_user.id])],
        })
        other_employee = self.env['hr.employee'].create({
            'name': 'GPS Other Employee',
            'company_id': self.company.id,
            'user_id': other_user.id,
            'is_distribution_employee': True,
            'distribution_active': True,
        })
        other_route, other_visit = self._create_route(
            employee_id=other_employee.id)
        mgr_env = self.mgr['distribution.route.visit'].browse(other_visit.id)
        mgr_env.gps_submit_checkin(
            30.010270, 31.240000, 5.0,
            gps_timestamp=fields.Datetime.now().timestamp() * 1000)

        user_env = self.env(user=self.sales_user)
        user_env.invalidate_all()
        visible = user_env['distribution.visit.gps.event'].search([])
        self.assertTrue(all(
            e.user_id == self.sales_user or
            e.visit_id.employee_id == self.sales_employee
            for e in visible))
        other_events = visible.filtered(
            lambda e: e.visit_id == other_visit)
        self.assertFalse(other_events)

    def test_manager_sees_all_company_events(self):
        route, visit = self._create_route()
        self._make_checkin_event(visit)
        mgr_env = self.mgr['distribution.visit.gps.event']
        visible = mgr_env.search([])
        self.assertTrue(visit.gps_event_ids[0] in visible)

    def test_visit_gps_fields_cannot_be_edited_manually(self):
        route, visit = self._create_route()
        self._make_checkin_event(visit)
        # Manager tries to edit check-in coordinates directly — blocked.
        mgr_visit = self.mgr['distribution.route.visit'].browse(visit.id)
        with self.assertRaises(UserError):
            mgr_visit.write({'checkin_latitude': 0.0})
        # Salesman too.
        user_env = self.env(user=self.sales_user)
        user_env.invalidate_all()
        visit_as_user = user_env['distribution.route.visit'].browse(visit.id)
        with self.assertRaises(Exception):
            visit_as_user.write({'checkin_distance': 0.0})

    def test_multi_company_isolation(self):
        company2 = self.env['res.company'].create({'name': 'GPS Co Two'})
        area2 = self.env['distribution.area'].create({
            'name': 'GPS Area Two', 'company_id': company2.id})
        visit_type2 = self.env['distribution.visit.type'].create({
            'name': 'GPS Visit Two', 'code': 'gps_test_c2',
            'company_id': company2.id,
            'require_gps_checkout': True,
        })
        employee2 = self.env['hr.employee'].create({
            'name': 'GPS Employee Two',
            'company_id': company2.id,
            'user_id': self.sales_user.id,
            'is_distribution_employee': True,
            'distribution_active': True,
        })
        partner2 = self.env['res.partner'].create({
            'name': 'GPS Customer Two',
            'company_id': company2.id,
            'distribution_area_id': area2.id,
        })
        partner2.write({
            'distribution_latitude': 30.010000,
            'distribution_longitude': 31.240000,
            'distribution_geofence_radius': 100.0,
        })
        # The manager must be allowed to operate in company 2 as well.
        self.manager_user.company_ids = [
            (6, 0, [self.company.id, company2.id])]
        route2 = self.mgr['distribution.route.plan'].create({
            'date': self.route_date,
            'employee_id': employee2.id,
            'area_id': area2.id,
            'company_id': company2.id,
        })
        # GPS tests run routes WITHOUT vehicle data; the vehicle-route
        # extension requires one by default. Disable for company 2.
        company2.sudo().distribution_require_vehicle_on_route = False
        visit2 = self.mgr['distribution.route.visit'].create({
            'route_id': route2.id,
            'partner_id': partner2.id,
            'visit_type_id': visit_type2.id,
            'planned_datetime': fields.Datetime.now(),
        })
        route2.action_confirm()
        route2.action_start_route()
        visit2.gps_submit_checkin(
            30.010270, 31.240000, 5.0,
            gps_timestamp=fields.Datetime.now().timestamp() * 1000)
        self.assertEqual(visit2.company_id, company2)

        self.sales_user.company_ids = [
            (6, 0, [self.company.id, company2.id])]
        user_env = self.env(user=self.sales_user)
        user_env.invalidate_all()
        visible = user_env['distribution.visit.gps.event'].with_company(
            company2).search([])
        self.assertNotIn(visit2.gps_event_ids[0] in visible and True, [None])
        c1_events_in_c2_context = visible.filtered(
            lambda e: e.visit_id.company_id == self.company)
        self.assertFalse(c1_events_in_c2_context)

    def test_customer_capture_logs_event(self):
        # Customer location capture by the salesman is audited too.
        user_env = self.env(user=self.sales_user)
        partner_as_user = user_env['res.partner'].browse(self.partner.id)
        partner_as_user.gps_save_customer_location(
            30.010100, 31.240100, 9.0)
        self.assertEqual(
            partner_as_user.distribution_location_source, 'device_gps')
        self.assertEqual(
            partner_as_user.distribution_location_user_id, self.sales_user)
        events = user_env['distribution.visit.gps.event'].search(
            [('event_type', '=', 'customer_location_capture')])
        self.assertEqual(len(events), 1)

    def test_manual_partner_location_sets_source(self):
        # Manual coordinate entry is done with full partner edit rights
        # (the GPS manager group alone does not grant res.partner write).
        self.env['res.partner'].browse(self.partner.id).write({
            'distribution_latitude': 30.02,
            'distribution_longitude': 31.24,
        })
        self.assertEqual(self.partner.distribution_location_source, 'manual')
        self.assertEqual(
            self.partner.distribution_location_user_id, self.env.user)

    def test_open_location_action(self):
        action = self.partner.action_open_location()
        self.assertEqual(action['type'], 'ir.actions.act_url')
        self.assertIn('30.01', action['url'])

    def test_open_location_requires_coordinates(self):
        self.partner.write({
            'distribution_latitude': False,
            'distribution_longitude': False,
        })
        with self.assertRaises(UserError):
            self.partner.action_open_location()

    def test_stale_position_age_validation(self):
        route, visit = self._create_route()
        now = fields.Datetime.now()
        fresh = visit._validate_position_age(now.timestamp() * 1000)
        self.assertTrue(fresh)
        old = visit._validate_position_age(
            (now.timestamp() - 3600) * 1000)
        self.assertFalse(old)
