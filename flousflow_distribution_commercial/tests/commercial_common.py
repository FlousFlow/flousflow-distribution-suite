# -*- coding: utf-8 -*-
"""Shared fixtures for the commercial integration tests."""
from datetime import datetime, time, timedelta

from odoo import fields
from odoo.tests import TransactionCase, tagged


@tagged('post_install', '-at_install')
class CommercialCommon(TransactionCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.company_a = cls.env.company
        cls.company_b = cls.env['res.company'].create(
            {'name': 'Commercial Co B'})

        cls.group_route_manager = cls.env.ref(
            'flousflow_distribution_route_base.'
            'group_distribution_route_manager')
        cls.group_vehicle_manager = cls.env.ref(
            'flousflow_distribution_vehicle.'
            'group_distribution_vehicle_manager')
        cls.group_accounting = cls.env.ref('account.group_account_invoice')

        # Manager: routes + vehicles, NO accounting rights (spec #122)
        cls.manager_user = cls.env['res.users'].create({
            'name': 'Commercial Manager', 'login': 'commercial_manager',
            'email': 'cm@example.com',
            'group_ids': [(6, 0, [cls.group_route_manager.id,
                                  cls.group_vehicle_manager.id,
                                  cls.env.ref(
                                      'sales_team.group_sale_manager').id])],
        })
        cls.manager_user.company_ids = [(6, 0, [cls.company_a.id])]
        # Accounting validator: distribution validator + billing rights
        cls.accountant_user = cls.env['res.users'].create({
            'name': 'Collection Validator', 'login': 'collection_validator',
            'email': 'cv@example.com',
            'group_ids': [(6, 0, [
                cls.env.ref(
                    'flousflow_distribution_commercial.'
                    'group_distribution_collection_validator').id,
                cls.group_accounting.id,
            ])],
        })
        cls.accountant_user.company_ids = [(6, 0, [cls.company_a.id])]
        cls.mgr = cls.env(user=cls.manager_user)
        cls.acc = cls.env(user=cls.accountant_user)

        # neutralize the vehicle-route default for test routes without POS
        cls.company_a.distribution_require_vehicle_on_route = False

        cls.area = cls.env['distribution.area'].create({
            'name': 'Commercial Area', 'company_id': cls.company_a.id})
        cls.visit_type_sale = cls.env['distribution.visit.type'].create({
            'name': 'Commercial Sale Visit', 'code': 'comm_sale',
            'company_id': cls.company_a.id, 'require_customer': True})
        cls.visit_type_collection = cls.env['distribution.visit.type'].create({
            'name': 'Commercial Collection Visit', 'code': 'comm_collect',
            'company_id': cls.company_a.id, 'require_customer': True})
        cls.visit_type_sale.write({'commercial_action_type': 'sale'})
        cls.visit_type_collection.write({'commercial_action_type': 'collection'})

        cls.partner_a = cls.env['res.partner'].create({
            'name': 'Customer A', 'company_id': cls.company_a.id})
        cls.partner_b = cls.env['res.partner'].create({
            'name': 'Customer B', 'company_id': cls.company_a.id})

        cls.product = cls.env['product.product'].create({
            'name': 'Commercial Test Product', 'type': 'consu',
            'list_price': 100.0, 'taxes_id': [(5, 0, 0)],
        })

        # Vehicle + POS (reuse the vehicle configure wizard)
        cls.vehicle_model = cls.env['fleet.vehicle.model'].create({
            'name': 'Commercial Van',
            'brand_id': cls.env['fleet.vehicle.model.brand'].create({
                'name': 'CommBrand'}).id,
        })
        cls.car1 = cls.env['fleet.vehicle'].create({
            'name': 'COMM-01', 'license_plate': 'CM-001',
            'model_id': cls.vehicle_model.id,
            'company_id': cls.company_a.id,
            'is_distribution_vehicle': True})
        cls._configure_vehicle(cls.env, cls.car1)

        # employee assigned to car1 with POS user rights
        cls.emp_ahmed = cls.env['hr.employee'].create({
            'name': 'Ahmed Commercial', 'company_id': cls.company_a.id,
            'is_distribution_employee': True, 'distribution_active': True})
        cls.salesman_user = cls.env['res.users'].create({
            'name': 'Ahmed Commercial Salesman',
            'login': 'commercial_salesman',
            'email': 'cs@example.com',
            'group_ids': [(6, 0, [
                cls.env.ref(
                    'flousflow_distribution_commercial.'
                    'group_distribution_collection_user').id,
                cls.env.ref('point_of_sale.group_pos_user').id,
                cls.env.ref('sales_team.group_sale_salesman').id,
            ])],
            'employee_ids': [(6, 0, [cls.emp_ahmed.id])],
        })
        cls.salesman_user.company_ids = [(6, 0, [cls.company_a.id])]
        cls.emp_ahmed.write({'user_id': cls.salesman_user.id})
        cls.mgr['fleet.vehicle.employee.assignment'].create({
            'employee_id': cls.emp_ahmed.id, 'vehicle_id': cls.car1.id,
            'role': 'sales_rep', 'company_id': cls.company_a.id,
            'date_from': fields.Date.context_today(cls.emp_ahmed)
                         - timedelta(days=7)})

        cls.today = fields.Date.context_today(cls.emp_ahmed)
        # load sale stock into the vehicle so POS orders can be created
        # (vehicle POS blocks negative stock by default)
        cls.main_wh = cls.env['stock.warehouse'].search(
            [('company_id', '=', cls.company_a.id)], limit=1)
        cls.env['distribution.vehicle.transfer.wizard'].create({
            'vehicle_id': cls.car1.id, 'direction': 'load',
            'source_warehouse_id': cls.main_wh.id, 'auto_validate': True,
            'line_ids': [(0, 0, {'product_id': cls.product.id,
                                 'quantity': 1000.0})],
        }).action_confirm()
        cls.route = cls._make_route()
        cls.visit = cls._make_visit()
        # the shared route is confirmed + started: most tests sell on it
        cls.route.action_confirm()
        cls.route.action_start_route()

    @classmethod
    def _make_route(cls):
        route = cls.mgr['distribution.route.plan'].create({
            'date': cls.today,
            'employee_id': cls.emp_ahmed.id,
            'area_id': cls.area.id,
            'company_id': cls.company_a.id,
        })
        return route

    def _new_route(self):
        return self._route()

    def _route(self, start=False):
        route = self.mgr['distribution.route.plan'].create({
            'date': self.today,
            'employee_id': self.emp_ahmed.id,
            'area_id': self.area.id,
            'company_id': self.company_a.id,
        })
        self.env['distribution.route.visit'].create({
            'route_id': route.id, 'sequence': 10,
            'partner_id': self.partner_a.id,
            'visit_type_id': self.visit_type_sale.id,
            'planned_datetime': datetime.combine(
                fields.Date.to_date(route.date), time(10, 0))})
        route.action_confirm()
        if start:
            route.action_start_route()
        return route

    def _start_visit(self, visit):
        if visit.state == 'pending':
            visit.action_start_visit()
        return visit

    @classmethod
    def _configure_vehicle(cls, env, vehicle):
        main_wh = env['stock.warehouse'].search(
            [('company_id', '=', cls.company_a.id)], limit=1)
        env['distribution.vehicle.configure.wizard'].create({
            'vehicle_id': vehicle.id, 'company_id': cls.company_a.id,
            'main_warehouse_id': main_wh.id,
            'warehouse_mode': 'create_new', 'pos_mode': 'create_new',
            'activate': True}).action_confirm()

    # -- visit helpers ----------------------------------------------------
    @classmethod
    def _make_visit(cls, partner=None, vtype=None, route=None):
        return cls.mgr['distribution.route.visit'].create({
            'route_id': (route or cls.route).id,
            'sequence': 20,
            'partner_id': (partner or cls.partner_a).id,
            'visit_type_id': (vtype or cls.visit_type_sale).id,
            'planned_datetime': datetime.combine(
                fields.Date.to_date((route or cls.route).date),
                time(11, 0)),
        })

    def _start_visit(self, visit):
        if visit.state == 'pending':
            visit.action_start_visit()
        return visit

    def _quotation(self, visit, amount=1000.0, partner=None):
        order = self.env(user=self.manager_user)['sale.order'].create({
            'partner_id': (partner or visit.partner_id).id,
            'company_id': visit.company_id.id,
            'distribution_route_id': visit.route_id.id,
            'distribution_visit_id': visit.id,
            'distribution_employee_id': visit.employee_id.id,
            'distribution_vehicle_id': visit.route_id.vehicle_id.id,
        })
        self.env['sale.order.line'].create({
            'order_id': order.id, 'product_id': self.product.id,
            'product_uom_qty': amount / 100.0, 'price_unit': 100.0,
        })
        return order

    def _collection(self, visit, amount=5000.0, method='cash',
                    user=None, invoices=None):
        """Collections are created as the visit owner (visit.user_id)
        so ownership checks and record rules pass in every scenario.
        Zero/negative amounts are refused by the DB CHECK constraint."""
        creator = user or visit.user_id or self.manager_user
        env = self.env(user=creator)
        vals = {'visit_id': visit.id, 'amount': amount,
                'collection_method': method}
        collection = env['distribution.visit.collection'].create(vals)
        if invoices:
            # linking invoices requires read access on account.move —
            # done by the accounting validator in the real flow
            collection.with_user(self.accountant_user).write(
                {'invoice_ids': [(6, 0, invoices.ids)]})
        return collection

    def _collection_expect_fail(self, visit, amount):
        with self.assertRaises(ValidationError):
            self._collection(visit, amount=amount)

    def _cash_journal(self):
        journal = self.env['account.journal'].search(
            [('type', '=', 'cash'), ('company_id', '=', self.company_a.id)],
            limit=1)
        if not journal:
            journal = self.env['account.journal'].create({
                'name': 'Commercial Cash', 'type': 'cash',
                'code': 'CCSH', 'company_id': self.company_a.id})
        return journal

    def _customer_invoice(self, partner, amount, company=None, post=True):
        company = company or self.company_a
        invoice = self.env['account.move'].create({
            'move_type': 'out_invoice',
            'partner_id': partner.id,
            'company_id': company.id,
            'invoice_date': fields.Date.context_today(self.env.user),
            'invoice_line_ids': [(0, 0, {
                'product_id': self.product.id,
                'quantity': 1,
                'price_unit': amount,
            })],
        })
        if post:
            invoice.action_post()
        return invoice
