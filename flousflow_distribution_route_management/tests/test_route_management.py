# -*- coding: utf-8 -*-
from datetime import datetime, timedelta, time

from odoo import fields
from odoo.exceptions import AccessError, UserError, ValidationError
from odoo.tests.common import TransactionCase, tagged


@tagged('post_install', '-at_install')
class TestDistributionRouteManagement(TransactionCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.company = cls.env.company
        # Route management tests exercise routes WITHOUT vehicle data. The
        # vehicle-route extension defaults to requiring a vehicle on
        # routes, so switch that requirement off for this suite.
        cls.company.distribution_require_vehicle_on_route = False

        # Groups
        cls.group_user = cls.env.ref(
            'flousflow_distribution_route_base.group_distribution_route_user')
        cls.group_manager = cls.env.ref(
            'flousflow_distribution_route_base.group_distribution_route_manager')

        # Manager user
        cls.manager_user = cls.env['res.users'].create({
            'name': 'Distribution Manager',
            'login': 'dist_route_manager',
            'email': 'manager@example.com',
            'group_ids': [(6, 0, [cls.group_manager.id])],
        })

        # Representative user + employee
        cls.sales_user = cls.env['res.users'].create({
            'name': 'Ahmed Salesman',
            'login': 'dist_route_salesman',
            'email': 'salesman@example.com',
            'group_ids': [(6, 0, [cls.group_user.id])],
        })
        cls.sales_employee = cls.env['hr.employee'].create({
            'name': 'Ahmed Employee',
            'company_id': cls.company.id,
            'user_id': cls.sales_user.id,
            'is_distribution_employee': True,
            'distribution_active': True,
        })
        cls.other_user = cls.env['res.users'].create({
            'name': 'Mohamed Salesman',
            'login': 'dist_route_other',
            'email': 'other@example.com',
            'group_ids': [(6, 0, [cls.group_user.id])],
        })
        cls.other_employee = cls.env['hr.employee'].create({
            'name': 'Mohamed Employee',
            'company_id': cls.company.id,
            'user_id': cls.other_user.id,
            'is_distribution_employee': True,
            'distribution_active': True,
        })

        # Master data
        cls.area = cls.env['distribution.area'].create({
            'name': 'Maadi',
            'company_id': cls.company.id,
            'employee_ids': [(6, 0, [cls.sales_employee.id])],
        })
        cls.visit_type = cls.env['distribution.visit.type'].create({
            'name': 'Sales Visit',
            'code': 'sales_test',
            'company_id': cls.company.id,
            'require_customer': True,
        })
        cls.partner = cls.env['res.partner'].create({
            'name': 'Supermarket Al Noor',
            'company_id': cls.company.id,
        })
        cls.result_success = cls.env.ref(
            'flousflow_distribution_route_management.visit_result_completed')
        cls.result_unsuccess = cls.env.ref(
            'flousflow_distribution_route_management.visit_result_customer_closed')
        cls.result_notes_required = cls.env.ref(
            'flousflow_distribution_route_management.visit_result_other')

        # Route template
        cls.route_date = fields.Date.today()
        cls.mgr = cls.env(user=cls.manager_user)

    def _create_route(self, **kwargs):
        vals = {
            'date': self.route_date,
            'employee_id': self.sales_employee.id,
            'area_id': self.area.id,
            'company_id': self.company.id,
        }
        vals.update(kwargs)
        return self.mgr['distribution.route.plan'].create(vals)

    def _create_visit(self, route, **kwargs):
        vals = {
            'route_id': route.id,
            'sequence': 10,
            'partner_id': self.partner.id,
            'visit_type_id': self.visit_type.id,
            'planned_datetime': datetime.combine(
                route.date, time(10, 0, 0)),
            'planned_duration': 30.0,
        }
        vals.update(kwargs)
        return self.mgr['distribution.route.visit'].create(vals)

    # ------------------------------------------------------------------
    # Creation & confirmation
    # ------------------------------------------------------------------
    def test_01_create_route_with_sequence(self):
        route = self._create_route()
        self.assertTrue(route.name.startswith('ROUTE/'))
        self.assertEqual(route.state, 'draft')
        self.assertEqual(route.user_id, self.sales_user)

    def test_02_confirm_route(self):
        route = self._create_route()
        self._create_visit(route)
        route.action_confirm()
        self.assertEqual(route.state, 'confirmed')

    def test_03_cannot_confirm_empty_route(self):
        route = self._create_route()
        with self.assertRaises(UserError):
            route.action_confirm()

    def test_04_required_customer_by_visit_type(self):
        route = self._create_route()
        with self.assertRaises(ValidationError):
            self._create_visit(route, partner_id=False)

    def test_05_area_must_match_employee(self):
        other_area = self.env['distribution.area'].create({
            'name': 'Nasr City',
            'company_id': self.company.id,
        })
        route = self._create_route(area_id=other_area.id)
        self._create_visit(route)
        with self.assertRaises(ValidationError):
            route.action_confirm()

    # ------------------------------------------------------------------
    # Execution
    # ------------------------------------------------------------------
    def test_06_start_route(self):
        route = self._create_route()
        self._create_visit(route)
        route.action_confirm()
        route.action_start_route()
        self.assertEqual(route.state, 'in_progress')
        self.assertTrue(route.actual_start_datetime)
        self.assertFalse(route.actual_end_datetime)

    def test_07_start_visit_records_actual_start(self):
        route = self._create_route()
        visit = self._create_visit(route)
        route.action_confirm()
        route.action_start_route()
        visit.action_start_visit()
        self.assertEqual(visit.state, 'in_progress')
        self.assertTrue(visit.actual_start_datetime)

    def test_08_cannot_start_visit_before_route(self):
        route = self._create_route()
        visit = self._create_visit(route)
        route.action_confirm()
        with self.assertRaises(UserError):
            visit.action_start_visit()

    def test_09_complete_visit(self):
        route = self._create_route()
        visit = self._create_visit(route)
        route.action_confirm()
        route.action_start_route()
        visit.action_start_visit()
        visit.action_finalize_visit(result_id=self.result_success.id)
        self.assertEqual(visit.state, 'done')
        self.assertTrue(visit.actual_end_datetime)
        self.assertTrue(visit.completion_datetime)
        self.assertEqual(visit.result_id, self.result_success)

    def test_10_required_result(self):
        route = self._create_route()
        visit = self._create_visit(route)
        route.action_confirm()
        route.action_start_route()
        visit.action_start_visit()
        with self.assertRaises(UserError):
            visit.action_finalize_visit(result_id=False)

    def test_11_required_result_notes(self):
        route = self._create_route()
        visit = self._create_visit(route)
        route.action_confirm()
        route.action_start_route()
        visit.action_start_visit()
        with self.assertRaises(UserError):
            visit.action_finalize_visit(
                result_id=self.result_notes_required.id,
                result_notes=False,
            )

    def test_12_unsuccessful_result_requires_failure_reason(self):
        route = self._create_route()
        visit = self._create_visit(route)
        route.action_confirm()
        route.action_start_route()
        visit.action_start_visit()
        with self.assertRaises(UserError):
            visit.action_finalize_visit(
                result_id=self.result_unsuccess.id,
                failure_reason=False,
            )
        visit.action_finalize_visit(
            result_id=self.result_unsuccess.id,
            failure_reason='Customer was closed',
        )
        self.assertEqual(visit.state, 'done')
        self.assertFalse(visit.result_id.is_success)

    def test_13_actual_duration_and_arrival_variance(self):
        route = self._create_route()
        visit = self._create_visit(route)
        route.action_confirm()
        route.action_start_route()
        visit.action_start_visit()
        start = fields.Datetime.now()
        visit.write({
            'actual_start_datetime': start,
        })
        visit.action_finalize_visit(
            result_id=self.result_success.id,
            employee_notes='Done',
        )
        # Actual end is now() — duration must be >= 0 minutes
        self.assertGreaterEqual(visit.actual_duration, 0.0)
        # Arrival variance = actual start - planned start (in minutes)
        planned = visit.planned_datetime
        expected = (start - planned).total_seconds() / 60.0
        self.assertAlmostEqual(visit.arrival_variance_minutes, expected, places=1)

    def test_14_skip_visit_requires_reason(self):
        route = self._create_route()
        visit = self._create_visit(route)
        route.action_confirm()
        route.action_start_route()
        with self.assertRaises(UserError):
            visit.action_skip_visit(False)
        visit.action_skip_visit('Customer shop was closed')
        self.assertEqual(visit.state, 'cancelled')

    # ------------------------------------------------------------------
    # Route completion & counters
    # ------------------------------------------------------------------
    def test_15_cannot_complete_with_pending_visit(self):
        route = self._create_route()
        self._create_visit(route)
        route.action_confirm()
        route.action_start_route()
        with self.assertRaises(UserError):
            route.action_complete_route()

    def test_16_complete_route_and_rates(self):
        route = self._create_route()
        v1 = self._create_visit(route, sequence=10)
        v2 = self._create_visit(route, sequence=20)
        route.action_confirm()
        route.action_start_route()
        v1.action_start_visit()
        v1.action_finalize_visit(result_id=self.result_success.id)
        v2.action_start_visit()
        v2.action_finalize_visit(
            result_id=self.result_unsuccess.id,
            failure_reason='No answer',
        )
        self.assertTrue(route.can_complete)
        route.action_complete_route()
        self.assertEqual(route.state, 'completed')
        self.assertTrue(route.actual_end_datetime)
        self.assertEqual(route.visit_count, 2)
        self.assertEqual(route.done_visit_count, 2)
        self.assertEqual(route.remaining_visit_count, 0)
        self.assertAlmostEqual(route.execution_rate, 100.0)
        self.assertAlmostEqual(route.success_rate, 50.0)

    def test_17_cancelled_visit_excluded_from_execution(self):
        route = self._create_route()
        v1 = self._create_visit(route)
        v2 = self._create_visit(route, sequence=20)
        route.action_confirm()
        route.action_start_route()
        v1.action_start_visit()
        v1.action_finalize_visit(result_id=self.result_success.id)
        v2.action_skip_visit('Not reachable')
        route.action_complete_route()
        self.assertEqual(route.done_visit_count, 1)
        self.assertEqual(route.cancelled_visit_count, 1)
        self.assertAlmostEqual(route.execution_rate, 100.0)

    def test_18_force_complete_requires_manager_and_reason(self):
        route = self._create_route()
        self._create_visit(route)
        route.action_confirm()
        route.action_start_route()
        with self.assertRaises(UserError):
            route.action_complete_route(force=True, reason=False)
        route.action_complete_route(force=True, reason='Site closure')
        self.assertEqual(route.state, 'completed')
        self.assertEqual(route.cancelled_visit_count, 1)

    # ------------------------------------------------------------------
    # Security
    # ------------------------------------------------------------------
    def test_19_user_sees_only_own_routes(self):
        route = self._create_route()
        other_route = self._create_route(employee_id=self.other_employee.id)
        self._create_visit(route)
        self._create_visit(other_route)
        route.action_confirm()
        other_route.action_confirm()

        own_env = self.env(user=self.sales_user)
        Route = own_env['distribution.route.plan']
        visible = Route.search([('id', 'in', [route.id, other_route.id])])
        self.assertIn(route, visible)
        self.assertNotIn(other_route, visible)

        other_env = self.env(user=self.other_user)
        visible_other = other_env['distribution.route.plan'].search(
            [('id', 'in', [route.id, other_route.id])])
        self.assertIn(other_route, visible_other)
        self.assertNotIn(route, visible_other)

    def test_20_user_sees_only_own_visits(self):
        route = self._create_route()
        other_route = self._create_route(employee_id=self.other_employee.id)
        visit = self._create_visit(route)
        other_visit = self._create_visit(other_route)
        route.action_confirm()
        other_route.action_confirm()

        own_env = self.env(user=self.sales_user)
        Visit = own_env['distribution.route.visit']
        visible = Visit.search([('id', 'in', [visit.id, other_visit.id])])
        self.assertIn(visit, visible)
        self.assertNotIn(other_visit, visible)

    def test_21_manager_sees_all(self):
        route = self._create_route()
        other_route = self._create_route(employee_id=self.other_employee.id)
        manager_env = self.env(user=self.manager_user)
        visible = manager_env['distribution.route.plan'].search(
            [('id', 'in', [route.id, other_route.id])])
        self.assertEqual(len(visible), 2)

    def test_22_user_cannot_modify_after_confirm(self):
        route = self._create_route()
        self._create_visit(route)
        route.action_confirm()
        user_env = self.env(user=self.sales_user)
        Route = user_env['distribution.route.plan']
        route_as_user = Route.browse(route.id)
        # invalidate cache so record rules re-apply on read
        user_env.invalidate_all()
        with self.assertRaises(UserError):
            route_as_user.write({'employee_id': self.other_employee.id})
        with self.assertRaises(UserError):
            route_as_user.write({'notes': 'hacked'})

    def test_23_user_cannot_create_route_or_visit(self):
        user_env = self.env(user=self.sales_user)
        with self.assertRaises(AccessError):
            user_env['distribution.route.plan'].create({
                'date': self.route_date,
                'employee_id': self.sales_employee.id,
                'area_id': self.area.id,
            })
        route = self._create_route()
        self._create_visit(route)
        route.action_confirm()
        user_env.invalidate_all()
        with self.assertRaises(AccessError):
            user_env['distribution.route.visit'].create({
                'route_id': route.id,
                'visit_type_id': self.visit_type.id,
                'partner_id': self.partner.id,
                'planned_datetime': datetime.combine(
                    self.route_date, time(11, 0, 0)),
            })

    # ------------------------------------------------------------------
    # Multi-company
    # ------------------------------------------------------------------
    def test_24_multi_company_isolation(self):
        company2 = self.env['res.company'].create({'name': 'Company Two'})
        area2 = self.env['distribution.area'].create({
            'name': 'Area C2',
            'company_id': company2.id,
        })
        employee2 = self.env['hr.employee'].create({
            'name': 'Employee C2',
            'company_id': company2.id,
            'user_id': self.sales_user.id,
            'is_distribution_employee': True,
            'distribution_active': True,
        })
        route_c1 = self._create_route()
        route_c2 = self.env['distribution.route.plan'].create({
            'date': self.route_date,
            'employee_id': employee2.id,
            'area_id': area2.id,
            'company_id': company2.id,
        })
        self.sales_user.company_ids = [(6, 0, [self.company.id, company2.id])]
        user_env = self.env(user=self.sales_user)
        user_env.invalidate_all()
        visible = user_env['distribution.route.plan'].with_company(
            company2).search(
                [('id', 'in', [route_c1.id, route_c2.id])])
        self.assertIn(route_c2, visible)
        self.assertNotIn(route_c1, visible)

    # ------------------------------------------------------------------
    # Duplicate behavior
    # ------------------------------------------------------------------
    def test_25_duplicate_resets_execution(self):
        route = self._create_route()
        visit = self._create_visit(route)
        route.action_confirm()
        route.action_start_route()
        visit.action_start_visit()
        visit.action_finalize_visit(result_id=self.result_success.id)
        route.action_complete_route()

        dup = route.copy()
        self.assertEqual(dup.state, 'draft')
        self.assertNotEqual(dup.name, route.name)
        self.assertFalse(dup.actual_start_datetime)
        self.assertFalse(dup.actual_end_datetime)
        self.assertEqual(len(dup.visit_ids), 1)
        dup_visit = dup.visit_ids
        self.assertEqual(dup_visit.state, 'pending')
        self.assertFalse(dup_visit.result_id)
        self.assertFalse(dup_visit.actual_start_datetime)
        self.assertEqual(dup_visit.partner_id, self.partner)

    # ------------------------------------------------------------------
    # Integrations
    # ------------------------------------------------------------------
    def test_26_partner_visit_history(self):
        route = self._create_route()
        self._create_visit(route)
        route.action_confirm()
        self.partner.invalidate_recordset(['distribution_visit_count'])
        self.assertEqual(self.partner.distribution_visit_count, 1)
        action = self.partner.action_view_distribution_visits()
        self.assertEqual(action['domain'], [('partner_id', '=', self.partner.id)])

    def test_27_employee_route_history(self):
        route = self._create_route()
        self._create_visit(route)
        route.action_confirm()
        self.sales_employee.invalidate_recordset(
            ['distribution_route_count', 'distribution_visit_count'])
        self.assertEqual(self.sales_employee.distribution_route_count, 1)
        self.assertEqual(self.sales_employee.distribution_visit_count, 1)

    def test_28_planned_date_must_match_route_date(self):
        route = self._create_route()
        with self.assertRaises(ValidationError):
            self._create_visit(
                route,
                planned_datetime=datetime.combine(
                    route.date + timedelta(days=5), time(10, 0, 0)),
            )
