# -*- coding: utf-8 -*-
"""Operational collection workflow tests (spec #114/#121/#51)."""
from datetime import datetime, time

import psycopg2

from odoo import fields
from odoo.exceptions import UserError, ValidationError
from odoo.tests import tagged

from .commercial_common import CommercialCommon


@tagged('post_install', '-at_install')
class TestVisitCollection(CommercialCommon):

    def test_12_record_and_submit_collection(self):
        """Spec #114: salesman records + submits; no payment yet."""
        visit = self._start_visit(self.visit)
        result = visit.with_user(self.salesman_user).action_record_collection()
        collection = self.env['distribution.visit.collection'].browse(
            result['res_id'])
        self.assertEqual(collection.state, 'draft')
        self.assertEqual(collection.partner_id, self.partner_a)
        self.assertEqual(collection.employee_id, self.emp_ahmed)
        self.assertEqual(collection.currency_id, self.company_a.currency_id)
        self.assertTrue(collection.name.startswith('COL/'))
        collection.amount = 5000.0
        collection.collection_method = 'cash'
        collection.action_submit()
        self.assertEqual(collection.state, 'submitted')
        self.assertFalse(collection.payment_id)
        self.assertEqual(collection.payment_state, 'not_created')

    def test_13_zero_amount_blocked(self):
        """Spec #79: no zero collections — refused by the amount CHECK."""
        visit = self._start_visit(self.visit)
        with self.assertRaises(psycopg2.errors.CheckViolation):
            self._collection(visit, amount=0.0)

    def test_14_submitted_locked_for_salesman(self):
        """Spec #33/#121: submitted collection is locked; the salesman
        cannot change the amount, and cannot delete it either."""
        visit = self._start_visit(self.visit)
        collection = self._collection(
            visit, amount=5000.0, user=self.salesman_user)
        collection.with_user(self.salesman_user).action_submit()
        with self.assertRaises(UserError):
            collection.with_user(self.salesman_user).write({'amount': 500.0})
        with self.assertRaises(UserError):
            collection.with_user(self.salesman_user).write(
                {'collection_method': 'bank_transfer'})
        with self.assertRaises(UserError):
            collection.with_user(self.salesman_user).unlink()

    def test_15_salesman_cannot_validate(self):
        """Spec #34/#35: submission does not post payments; the salesman
        cannot validate."""
        visit = self._start_visit(self.visit)
        collection = self._collection(visit, user=self.salesman_user)
        collection.with_user(self.salesman_user).action_submit()
        with self.assertRaises(UserError):
            collection.with_user(self.salesman_user).action_validate()
        self.assertEqual(collection.state, 'submitted')

    def test_16_reject_requires_reason(self):
        """Spec #51: rejection with mandatory reason."""
        visit = self._start_visit(self.visit)
        collection = self._collection(visit, user=self.salesman_user)
        collection.with_user(self.salesman_user).action_submit()
        with self.assertRaises(UserError):
            self.acc['distribution.visit.collection'].browse(
                collection.id).action_reject('')
        self.acc['distribution.visit.collection'].browse(
            collection.id).action_reject('Suspicious receipt')
        self.assertEqual(collection.state, 'rejected')
        self.assertEqual(collection.rejected_by, self.accountant_user)
        self.assertTrue(collection.rejection_reason)

    def test_17_reset_rejected_to_draft(self):
        """Spec #52: rejected collections can be reset to draft by a
        validator/manager."""
        visit = self._start_visit(self.visit)
        collection = self._collection(visit, user=self.salesman_user)
        collection.with_user(self.salesman_user).action_submit()
        self.acc['distribution.visit.collection'].browse(
            collection.id).action_reject('Wrong customer')
        self.acc['distribution.visit.collection'].browse(
            collection.id).action_reset_draft()
        self.assertEqual(collection.state, 'draft')
        self.assertFalse(collection.rejection_reason)

    def test_18_visit_commercial_enforcement_strict(self):
        """Spec #75-#78: strict mode blocks a collection-type visit with
        no collection, but an unsuccessful result always completes."""
        self.company_a.commercial_validation_mode = 'strict'
        self.company_a.collection_visit_requires_collection_record = True
        # a second employee avoids the one-route-in-progress guard
        emp2 = self.env['hr.employee'].create({
            'name': 'Second Commercial Emp',
            'company_id': self.company_a.id,
            'is_distribution_employee': True, 'distribution_active': True})
        route = self.mgr['distribution.route.plan'].create({
            'date': self.today, 'employee_id': emp2.id,
            'area_id': self.area.id, 'company_id': self.company_a.id})
        visit = self.env['distribution.route.visit'].create({
            'route_id': route.id, 'sequence': 10,
            'partner_id': self.partner_a.id,
            'visit_type_id': self.visit_type_collection.id,
            'planned_datetime': datetime.combine(
                fields.Date.to_date(route.date), time(11, 0))})
        route.action_confirm()
        route.action_start_route()
        visit.with_user(self.manager_user).action_start_visit()
        success = self.env.ref(
            'flousflow_distribution_route_management.visit_result_completed')
        refusal = self.env.ref(
            'flousflow_distribution_route_management.'
            'visit_result_customer_closed')
        with self.assertRaises(UserError):
            visit.with_user(self.manager_user).action_finalize_visit(
                result_id=success.id)
        # customer refused → completes without any collection (#78)
        visit.with_user(self.manager_user).action_finalize_visit(
            result_id=refusal.id, failure_reason='Customer refused')
        self.assertEqual(visit.state, 'done')
        self.assertFalse(visit.collection_ids)

    def test_19_no_zero_collection_records(self):
        """Spec #79: the collection model refuses zero/negative amounts."""
        visit = self._start_visit(self.visit)
        with self.assertRaises(psycopg2.errors.CheckViolation):
            self._collection(visit, amount=0.0)
        with self.assertRaises(psycopg2.errors.CheckViolation):
            self._collection(visit, amount=-5.0)
