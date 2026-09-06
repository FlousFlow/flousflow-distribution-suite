# -*- coding: utf-8 -*-
"""Quotation / Sale Order integration tests (spec #109/#110/#126)."""
from odoo.exceptions import UserError, ValidationError
from odoo.tests import tagged

from .commercial_common import CommercialCommon


@tagged('post_install', '-at_install')
class TestVisitSales(CommercialCommon):

    def test_01_create_quotation_from_visit(self):
        """Spec #109: quotation links visit/route/employee/company."""
        visit = self._start_visit(self.visit)
        result = visit.with_user(self.salesman_user).action_create_quotation()
        order = self.env['sale.order'].browse(result['res_id'])
        self.assertEqual(order.partner_id, self.partner_a)
        self.assertEqual(order.distribution_visit_id, visit)
        self.assertEqual(order.distribution_route_id, self.route)
        self.assertEqual(order.distribution_employee_id, self.emp_ahmed)
        self.assertEqual(order.company_id, self.company_a)
        self.assertEqual(order.state, 'draft')

    def test_02_quotation_confirm_keeps_snapshot(self):
        """Spec #14: confirming later keeps route/visit/employee/vehicle.
        Even closing the employee assignment changes nothing (#126)."""
        visit = self._start_visit(self.visit)
        result = visit.action_create_quotation()
        order = self.env['sale.order'].browse(result['res_id'])
        order.action_confirm()
        self.assertEqual(order.state, 'sale')
        self.assertEqual(order.distribution_visit_id, visit)
        self.assertEqual(order.distribution_route_id, self.route)
        self.assertEqual(order.distribution_vehicle_id, self.car1)
        # later: employee moved away — old sale snapshot untouched
        assignment = self.mgr['fleet.vehicle.employee.assignment'].search(
            [('employee_id', '=', self.emp_ahmed.id),
             ('vehicle_id', '=', self.car1.id)], limit=1)
        assignment.action_close()
        self.assertEqual(order.distribution_vehicle_id, self.car1)
        self.assertEqual(order.distribution_visit_id, visit)

    def test_03_salesman_b_cannot_use_visit_a(self):
        """Spec #110: another salesman cannot create from A's visit."""
        other_user = self.env['res.users'].create({
            'name': 'Other Salesman', 'login': 'other_commercial_salesman2',
            'email': 'ocs2@example.com',
            'group_ids': [(6, 0, [
                self.env.ref(
                    'flousflow_distribution_commercial.'
                    'group_distribution_collection_user').id])],
        })
        other_emp = self.env['hr.employee'].create({
            'name': 'Other Commercial Emp 2', 'company_id': self.company_a.id,
            'is_distribution_employee': True, 'distribution_active': True})
        other_user.employee_ids = [(6, 0, [other_emp.id])]
        other_user.company_ids = [(6, 0, [self.company_a.id])]
        visit = self._start_visit(self.visit)
        with self.assertRaises(UserError):
            visit.with_user(other_user).action_create_quotation()

    def test_04_quotation_requires_customer(self):
        """A visit without a customer cannot produce a quotation."""
        visit_type_free = self.env['distribution.visit.type'].create({
            'name': 'Free Visit', 'code': 'free_comm',
            'company_id': self.company_a.id, 'require_customer': False,
            'commercial_action_type': 'sale'})
        visit = self.env['distribution.route.visit'].create({
            'route_id': self.route.id, 'sequence': 30,
            'partner_id': self.partner_a.id,
            'visit_type_id': visit_type_free.id,
            'planned_datetime': False})
        visit.with_user(self.manager_user).write({'partner_id': False})
        with self.assertRaises(UserError):
            visit.action_create_quotation()

    def test_05_visit_commercial_metrics(self):
        """Quotation vs confirmed separation — no double counting (#7)."""
        visit = self._start_visit(self.visit)
        # read metrics through the salesman so POS o2m stays accessible
        visit = visit.with_user(self.salesman_user)
        order = self.env(user=self.salesman_user)['sale.order'].create({
            'partner_id': self.partner_a.id,
            'company_id': self.company_a.id,
            'distribution_route_id': self.route.id,
        })
        order.distribution_visit_id = visit.id
        self.env['sale.order.line'].create({
            'order_id': order.id, 'product_id': self.product.id,
            'product_uom_qty': 8.5, 'price_unit': 100.0})
        self.assertEqual(visit.quotation_amount_total, 850.0)
        self.assertEqual(visit.confirmed_sale_amount_total, 0.0)
        self.assertTrue(visit.has_quotation)
        self.assertFalse(visit.has_confirmed_sale)
        order.action_confirm()
        visit.invalidate_recordset(['quotation_amount_total',
                                    'confirmed_sale_amount_total'])
        self.assertEqual(visit.quotation_amount_total, 0.0)
        self.assertEqual(visit.confirmed_sale_amount_total, 850.0)
        self.assertTrue(visit.has_confirmed_sale)

    def test_06_customer_mismatch_managed_override(self):
        """Spec #10: salesman cannot change the visit customer on the
        order; a distribution manager may override."""
        visit = self._start_visit(self.visit)
        order = self.env(user=self.salesman_user, su=False)['sale.order'].create({
            'partner_id': self.partner_a.id,
            'company_id': self.company_a.id,
            'distribution_route_id': self.route.id,
            'distribution_visit_id': visit.id,
        })
        with self.assertRaises(ValidationError):
            mismatch_env = self.env(user=self.salesman_user, su=False)
            order.with_env(mismatch_env).write(
                {'partner_id': self.partner_b.id})
        # manager override: allowed
        order.with_user(self.manager_user).write(
            {'partner_id': self.partner_b.id})
