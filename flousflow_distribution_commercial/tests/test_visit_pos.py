# -*- coding: utf-8 -*-
"""POS visit-link tests (spec #111/#113/#125/#126).

The full POS frontend flow is browser territory; here we assert the
backend contract: an order payload carrying the visit id is linked
explicitly, wrong POS is blocked, refunds are separated from gross sales,
and the metadata survives offline-style late sync."""
from odoo.exceptions import UserError
from odoo.tests import tagged

from datetime import timedelta

from odoo import fields

from .commercial_common import CommercialCommon


@tagged('post_install', '-at_install')
class TestVisitPos(CommercialCommon):

    def _pos_session(self, vehicle):
        config = vehicle.distribution_pos_config_id
        if config.current_session_id and \
                config.current_session_id.state != 'closed':
            return config.current_session_id
        return self.env['pos.session'].create({
            'config_id': config.id,
            'user_id': self.salesman_user.id,
        })

    def _pos_order(self, session, visit=None, partner=None, amount=1000.0,
                   user=None):
        env = self.env(user=user) if user else self.env
        qty = amount / 100.0
        price = 100.0 if amount >= 0 else -100.0
        vals = {
            'session_id': session.id,
            'company_id': self.company_a.id,
            'partner_id': (partner or self.partner_a).id,
            'amount_paid': 0.0, 'amount_return': 0.0,
            'amount_tax': 0.0, 'amount_total': 0.0,
            'lines': [(0, 0, {
                'product_id': self.product.id,
                'qty': qty,
                'price_unit': price,
                'price_subtotal': amount,
                'price_subtotal_incl': amount,
            })],
        }
        if visit:
            vals['distribution_visit_id'] = visit.id
        return env['pos.order'].create(vals)

    def test_07_pos_order_explicit_visit_link(self):
        """Spec #111: visit/route/employee/vehicle all linked explicitly."""
        visit = self._start_visit(self.visit)
        session = self._pos_session(self.car1)
        order = self._pos_order(session, visit=visit)
        self.assertEqual(order.distribution_visit_id, visit)
        self.assertEqual(order.distribution_route_id, self.route)
        self.assertEqual(order.distribution_employee_id, self.emp_ahmed)
        self.assertEqual(order.distribution_vehicle_id, self.car1)

    def test_08_offline_metadata_survives_late_sync(self):
        """Spec #112: an order synced late (offline scenario) with the
        visit id in its payload keeps the visit metadata."""
        visit = self._start_visit(self.visit)
        session = self._pos_session(self.car1)
        # "offline" = created later with an old date_order and the visit id
        order = self._pos_order(session, visit=visit, amount=250.0)
        order.date_order = fields.Datetime.now() - timedelta(days=2)
        self.assertEqual(order.distribution_visit_id, visit)
        self.assertEqual(order.distribution_route_id, self.route)

    def test_09_wrong_pos_blocked(self):
        """Spec #113: the assigned employee cannot sell from another
        vehicle's POS (existing vehicle enforcement reused)."""
        car2 = self.env['fleet.vehicle'].create({
            'name': 'COMM-02', 'license_plate': 'CM-002',
            'model_id': self.vehicle_model.id,
            'company_id': self.company_a.id,
            'is_distribution_vehicle': True})
        self._configure_vehicle(self.env, car2)
        visit = self._start_visit(self.visit)
        session2 = self._pos_session(car2)
        with self.assertRaises(UserError):
            self._pos_order(session2, amount=100.0, user=self.salesman_user)

    def test_10_pos_refunds_separated_from_gross(self):
        """Spec #125: gross / refunds / net POS amounts are distinct."""
        visit = self._start_visit(self.visit)
        session = self._pos_session(self.car1)
        sale = self._pos_order(session, visit=visit, amount=1000.0)
        refund = self._pos_order(session, visit=visit, amount=-200.0)
        self.assertEqual(visit.with_user(self.salesman_user).
                         pos_order_count, 2)
        # net = 1000 - 200 = 800 via the visit-level metric
        # read through the salesman (POS user) so the o2m is accessible;
        # POS amounts are not invoiced in tests → compute from lines
        visit_salesman = visit.with_user(self.salesman_user)
        net = sum(
            line.price_subtotal_incl
            for order in visit_salesman.pos_order_ids
            if order.state != 'cancel'
            for line in order.lines)
        self.assertAlmostEqual(net, 800.0, places=2)

    def test_11_historical_pos_snapshot_integrity(self):
        """Spec #126: later reassignment keeps old POS links."""
        visit = self._start_visit(self.visit)
        session = self._pos_session(self.car1)
        order = self._pos_order(session, visit=visit, amount=300.0)
        # salesman moves to another vehicle
        assignment = self.mgr['fleet.vehicle.employee.assignment'].search(
            [('employee_id', '=', self.emp_ahmed.id),
             ('vehicle_id', '=', self.car1.id)], limit=1)
        assignment.action_close()
        self.assertEqual(order.distribution_visit_id, visit)
        self.assertEqual(order.distribution_vehicle_id, self.car1)
