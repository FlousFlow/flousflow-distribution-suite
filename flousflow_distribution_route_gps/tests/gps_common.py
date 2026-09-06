# -*- coding: utf-8 -*-
"""Shared fixtures for the GPS test suite."""
from datetime import datetime, time

from odoo import fields
from odoo.tests.common import TransactionCase

MODULE = 'flousflow_distribution_route_gps'


class GpsCommon(TransactionCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.company = cls.env.company
        # GPS tests exercise routes WITHOUT vehicle data. The vehicle-route
        # extension defaults to requiring a vehicle on routes, so switch
        # that requirement off for this suite.
        cls.company.distribution_require_vehicle_on_route = False
        cls.group_user = cls.env.ref(
            'flousflow_distribution_route_base.group_distribution_route_user')
        cls.group_manager = cls.env.ref(
            'flousflow_distribution_route_base.group_distribution_route_manager')

        cls.manager_user = cls.env['res.users'].create({
            'name': 'GPS Manager', 'login': 'gps_manager',
            'email': 'gps_manager@example.com',
            'group_ids': [(6, 0, [cls.group_manager.id])],
        })
        cls.sales_user = cls.env['res.users'].create({
            'name': 'GPS Salesman', 'login': 'gps_salesman',
            'email': 'gps_salesman@example.com',
            'group_ids': [(6, 0, [cls.group_user.id])],
        })
        cls.sales_employee = cls.env['hr.employee'].create({
            'name': 'GPS Salesman Employee',
            'company_id': cls.company.id,
            'user_id': cls.sales_user.id,
            'is_distribution_employee': True,
            'distribution_active': True,
        })
        cls.area = cls.env['distribution.area'].create({
            'name': 'GPS Area', 'company_id': cls.company.id,
            'employee_ids': [(6, 0, [cls.sales_employee.id])],
        })
        cls.visit_type = cls.env['distribution.visit.type'].create({
            'name': 'GPS Visit', 'code': 'gps_test',
            'company_id': cls.company.id,
            'require_gps_checkout': True,
        })
        cls.result_success = cls.env.ref(
            'flousflow_distribution_route_management.visit_result_completed')

        # Customer in downtown Cairo with a GPS location
        cls.partner = cls.env['res.partner'].create({
            'name': 'GPS Supermarket',
            'company_id': cls.company.id,
            'distribution_area_id': cls.area.id,
        })
        cls.partner.write({
            'distribution_latitude': 30.010000,
            'distribution_longitude': 31.240000,
            'distribution_geofence_radius': 100.0,
        })

        cls.mgr = cls.env(user=cls.manager_user)
        cls.route_date = fields.Date.today()

    @classmethod
    def set_param(cls, key, value):
        # set_param(key, False) DELETES the parameter in Odoo; pass an
        # explicit string so False is stored (and read back by our helpers).
        if isinstance(value, bool):
            value = 'True' if value else 'False'
        cls.env['ir.config_parameter'].sudo().set_param(
            'distribution_gps.' + key, value)

    def _create_route(self, **kwargs):
        vals = {
            'date': self.route_date,
            'employee_id': self.sales_employee.id,
            'area_id': self.area.id,
            'company_id': self.company.id,
        }
        vals.update(kwargs)
        route = self.mgr['distribution.route.plan'].create(vals)
        # GPS tests run routes WITHOUT vehicle data; the vehicle-route
        # extension requires one by default. Disable per route company
        # (covers the multi-company test company as well).
        route.company_id.sudo().distribution_require_vehicle_on_route = False
        visit = self.mgr['distribution.route.visit'].create({
            'route_id': route.id,
            'partner_id': self.partner.id,
            'visit_type_id': self.visit_type.id,
            'planned_datetime': datetime.combine(
                route.date, time(10, 0, 0)),
        })
        route.action_confirm()
        route.action_start_route()
        return route, visit

    def _checkin(self, visit, lat, lon, accuracy=5.0,
                 gps_timestamp=None, override=False):
        return visit.gps_submit_checkin(
            lat, lon, accuracy,
            gps_timestamp=gps_timestamp
            if gps_timestamp is not None
            else fields.Datetime.now().timestamp() * 1000,
            override=override,
        )
