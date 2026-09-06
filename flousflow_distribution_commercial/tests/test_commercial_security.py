# -*- coding: utf-8 -*-
"""Security + multi-company tests (spec #86-#91/#101)."""
import psycopg2

from odoo.exceptions import AccessError, UserError, ValidationError
from odoo.tests import tagged

from .commercial_common import CommercialCommon


@tagged('post_install', '-at_install')
class TestCommercialSecurity(CommercialCommon):

    def _submitted(self, employee_user):
        """A submitted collection recorded by employee_user's visit."""
        emp = employee_user.employee_ids[:1]
        route = self.env['distribution.route.plan'].sudo().create({
            'date': self.today, 'employee_id': emp.id,
            'area_id': self.area.id, 'company_id': self.company_a.id})
        visit = self.env['distribution.route.visit'].sudo().create({
            'route_id': route.id, 'sequence': 10,
            'partner_id': self.partner_a.id,
            'visit_type_id': self.visit_type_sale.id,
            'planned_datetime': False})
        collection = self.env[
            'distribution.visit.collection'].sudo().create({
                'visit_id': visit.id, 'amount': 1000.0,
                'collection_method': 'cash',
                'create_uid': employee_user.id})
        collection.with_user(employee_user).action_submit()
        return collection

    def test_32_salesman_isolation(self):
        """Spec #91: salesman A cannot read salesman B's collections."""
        user_a = self.salesman_user
        user_b = self.env['res.users'].create({
            'name': 'Salesman C', 'login': 'commercial_salesman_c',
            'email': 'csc@example.com',
            'group_ids': [(6, 0, [
                self.env.ref(
                    'flousflow_distribution_commercial.'
                    'group_distribution_collection_user').id])],
        })
        emp_b = self.env['hr.employee'].create({
            'name': 'Salesman C Emp', 'company_id': self.company_a.id,
            'is_distribution_employee': True, 'distribution_active': True,
            'user_id': user_b.id})
        user_b.company_ids = [(6, 0, [self.company_a.id])]

        own = self._submitted(user_a)
        other = self._submitted(user_b)

        visible = self.env(user=user_a)[
            'distribution.visit.collection'].search([])
        self.assertIn(own, visible)
        self.assertNotIn(other, visible)
        with self.assertRaises(AccessError):
            other.with_user(user_a).read(['amount'])

    def test_33_accounting_sees_collections(self):
        """Spec #89: accounting users get read access to collection
        records for review."""
        collection = self._submitted(self.salesman_user)
        readable = self.env(user=self.accountant_user)[
            'distribution.visit.collection'].browse(collection.id)
        self.assertEqual(readable.amount, 1000.0)

    def test_34_multi_company_visit_journal(self):
        """Spec #123/#90: cross-company collection data is rejected."""
        emp_b = self.env['hr.employee'].sudo().create({
            'name': 'B Commercial Emp', 'company_id': self.company_b.id,
            'is_distribution_employee': True, 'distribution_active': True})
        area_b = self.env['distribution.area'].sudo().create({
            'name': 'B Commercial Area', 'company_id': self.company_b.id,
            'employee_ids': [(6, 0, [emp_b.id])]})
        visit_type_b = self.env['distribution.visit.type'].sudo().create({
            'name': 'B Sale Visit', 'code': 'b_sale',
            'company_id': self.company_b.id, 'require_customer': True})
        partner_b = self.env['res.partner'].sudo().create({
            'name': 'Customer B Co', 'company_id': self.company_b.id})
        visit_b = self.env['distribution.route.visit'].sudo().create({
            'route_id': self.env['distribution.route.plan'].sudo().create({
                'date': self.today, 'employee_id': emp_b.id,
                'area_id': area_b.id, 'company_id': self.company_b.id}).id,
            'sequence': 10, 'partner_id': partner_b.id,
            'visit_type_id': visit_type_b.id,
            'planned_datetime': False,
            'company_id': self.company_b.id})
        # company-B collection + company-A journal → company mismatch
        collection = self.env[
            'distribution.visit.collection'].sudo().create({
            'visit_id': visit_b.id, 'amount': 100.0,
            'collection_method': 'cash'})
        journal_a = self.env['account.journal'].sudo().create({
            'name': 'A Cash for B Test', 'type': 'cash', 'code': 'CSHA2',
            'company_id': self.company_a.id})
        with self.assertRaises(ValidationError):
            # sudo write: we are testing the company constraint itself,
            # not the manager's company record rules
            collection.sudo().write({'journal_id': journal_a.id})

    def test_35_validator_group_has_no_accounting_by_itself(self):
        """Spec #36: the validator group alone never posts payments."""
        validator_user = self.env['res.users'].create({
            'name': 'Operational Validator',
            'login': 'operational_validator',
            'email': 'ov@example.com',
            'group_ids': [(6, 0, [
                self.env.ref(
                    'flousflow_distribution_commercial.'
                    'group_distribution_collection_validator').id])],
        })
        validator_user.company_ids = [(6, 0, [self.company_a.id])]
        collection = self._submitted(self.salesman_user)
        with self.assertRaises(UserError):
            collection.with_user(validator_user).action_validate()
        self.assertEqual(collection.state, 'submitted')
