# -*- coding: utf-8 -*-
"""Accounting integration tests (spec #115-#120/#122-#124)."""
from odoo.exceptions import UserError, ValidationError
from odoo.tests import tagged

from .commercial_common import CommercialCommon


@tagged('post_install', '-at_install')
class TestCollectionAccounting(CommercialCommon):

    def _submitted_collection(self, amount=5000.0, invoices=None,
                              with_journal=True, user=None):
        visit = self._start_visit(self.visit)
        collection = self._collection(visit, amount=amount,
                                      invoices=invoices,
                                      user=user or self.salesman_user)
        # journal + payment method line are set BEFORE submission (they
        # are financial fields locked once submitted — spec #33). The
        # accounting validator sets them in the real flow; in tests the
        # manager (full ACL) pre-fills them.
        if with_journal:
            method_line = self.env[
                'account.payment.method.line'].search([
                    ('journal_id', '=', self._cash_journal().id),
                    ('payment_method_id.payment_type', '=', 'inbound'),
                    ('payment_method_id.code', '=', 'manual'),
                ], limit=1)
            collection.with_user(self.manager_user).write({
                'journal_id': method_line.journal_id.id,
                'payment_method_line_id': method_line.id,
            })
        collection.with_user(user or self.salesman_user).action_submit()
        return collection

    def _validate(self, collection):
        self.env(user=self.accountant_user)[
            'distribution.visit.collection'].browse(
                collection.id).action_validate()

    def test_20_validate_creates_standard_payment(self):
        """Spec #115: validation creates + posts a standard inbound
        customer payment and links it."""
        collection = self._submitted_collection()
        self._validate(collection)
        collection.invalidate_recordset()
        self.assertEqual(collection.state, 'validated')
        self.assertTrue(collection.payment_id)
        payment = collection.payment_id
        self.assertEqual(payment.payment_type, 'inbound')
        self.assertEqual(payment.partner_type, 'customer')
        self.assertEqual(payment.partner_id, self.partner_a)
        self.assertIn(payment.state, ('posted', 'paid'))
        self.assertEqual(collection.payment_state, 'posted')

    def test_21_partial_invoice_payment(self):
        """Spec #116: invoice 10,000 / collection 4,000 → residual 6,000
        through standard reconciliation."""
        invoice = self._customer_invoice(self.partner_a, 10000.0)
        collection = self._submitted_collection(
            amount=4000.0, invoices=invoice)
        self._validate(collection)
        invoice.invalidate_recordset()
        self.assertAlmostEqual(invoice.amount_residual, 6000.0)
        self.assertEqual(invoice.payment_state, 'partial')

    def test_22_multiple_invoice_payment(self):
        """Spec #117: invoices 2,000 + 3,000 settled by one 5,000
        collection."""
        inv_a = self._customer_invoice(self.partner_a, 2000.0)
        inv_b = self._customer_invoice(self.partner_a, 3000.0)
        collection = self._submitted_collection(
            amount=5000.0, invoices=inv_a + inv_b)
        self._validate(collection)
        inv_a.invalidate_recordset()
        inv_b.invalidate_recordset()
        self.assertEqual(inv_a.payment_state, 'paid')
        self.assertEqual(inv_b.payment_state, 'paid')

    def test_23_unallocated_payment_allowed_by_default(self):
        """Spec #118: no invoices + default policy → payment remains
        available customer credit."""
        collection = self._submitted_collection(amount=5000.0)
        self._validate(collection)
        collection.invalidate_recordset()
        self.assertEqual(collection.state, 'validated')
        self.assertIn(collection.payment_id.state, ('posted', 'paid'))

    def test_24_unallocated_payment_blocked_by_policy(self):
        """Spec #42: policy off → unallocated collections blocked."""
        self.company_a.allow_unallocated_customer_collection = False
        visit = self._start_visit(self.visit)
        collection = self._collection(visit, amount=5000.0,
                                      user=self.salesman_user)
        collection.with_user(self.salesman_user).action_submit()
        with self.assertRaises(UserError):
            self._validate(collection)
        self.assertEqual(collection.state, 'submitted')

    def test_25_overpayment_blocked_by_policy(self):
        """Spec #119: invoices 4,000 / collection 5,000 with the policy
        off → blocked at validation."""
        self.company_a.allow_collection_overpayment = False
        invoice = self._customer_invoice(self.partner_a, 4000.0)
        visit = self._start_visit(self.visit)
        collection = self._collection(visit, amount=5000.0)
        collection.with_user(self.manager_user).write(
            {'invoice_ids': [(6, 0, invoice.ids)]})
        collection.with_user(self.salesman_user).action_submit()
        with self.assertRaises(UserError):
            self._validate(collection)
        self.assertEqual(collection.state, 'submitted')

    def test_26_overpayment_allowed_by_policy(self):
        """Spec #43: policy on → excess remains customer credit (standard
        behavior)."""
        self.company_a.allow_collection_overpayment = True
        invoice = self._customer_invoice(self.partner_a, 4000.0)
        collection = self._submitted_collection(
            amount=5000.0, invoices=invoice)
        self._validate(collection)
        invoice.invalidate_recordset()
        self.assertEqual(collection.state, 'validated')
        self.assertEqual(invoice.payment_state, 'paid')

    def test_27_distribution_manager_without_accounting_blocked(self):
        """Spec #122: the distribution manager has NO accounting rights —
        validation must be blocked, no sudo bypass."""
        collection = self._submitted_collection(amount=1000.0)
        with self.assertRaises(UserError):
            collection.with_user(self.manager_user).action_validate()
        self.assertEqual(collection.state, 'submitted')

    def test_28_multi_company_journal_blocked(self):
        """Spec #123: a journal from company B cannot be used on a
        company A collection."""
        journal_b = self.env['account.journal'].create({
            'name': 'Commercial Co B Cash', 'type': 'cash',
            'code': 'CBBH', 'company_id': self.company_b.id})
        visit = self._start_visit(self.visit)
        collection = self._collection(visit, amount=1000.0)
        with self.assertRaises(ValidationError):
            collection.with_user(self.manager_user).write(
                {'journal_id': journal_b.id})

    def test_29_transaction_integrity_on_failure(self):
        """Spec #124: a failing payment creation leaves the collection
        submitted — no half-validated records."""
        visit = self._start_visit(self.visit)
        collection = self._collection(visit, amount=1000.0,
                                      user=self.salesman_user)
        collection.with_user(self.salesman_user).action_submit()
        # make validation fail: no payment method line selected
        with self.assertRaises(UserError):
            self._validate(collection)
        self.assertEqual(collection.state, 'submitted')
        self.assertFalse(collection.payment_id)

    def test_30_validated_with_posted_payment_not_reset(self):
        """Spec #52: a validated collection with a posted payment cannot
        be reset to draft."""
        collection = self._submitted_collection(amount=1000.0)
        self._validate(collection)
        with self.assertRaises(UserError):
            collection.action_reset_draft()
        self.assertEqual(collection.state, 'validated')

    def test_31_invoice_balance_before_after(self):
        """Invoice residual updates through standard accounting only."""
        invoice = self._customer_invoice(self.partner_a, 1000.0)
        residual_before = invoice.amount_residual
        self.assertGreater(residual_before, 0.0)
        collection = self._submitted_collection(
            amount=1000.0, invoices=invoice)
        self._validate(collection)
        invoice.invalidate_recordset()
        self.assertEqual(invoice.amount_residual,
                         residual_before - 1000.0)
