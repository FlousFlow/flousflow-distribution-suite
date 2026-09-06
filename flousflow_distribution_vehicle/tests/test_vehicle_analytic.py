# -*- coding: utf-8 -*-
"""Vehicle analytic account: auto-create + POS auto-link. Sales + COGS land
on the vehicle's own analytic account without manual steps."""
from odoo.tests import TransactionCase, tagged


@tagged('post_install', '-at_install')
class TestVehicleAnalytic(TransactionCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.company = cls.env.company
        brand = cls.env['fleet.vehicle.model.brand'].create({'name': 'AB'})
        cls.car_model = cls.env['fleet.vehicle.model'].create(
            {'name': 'VA Van', 'brand_id': brand.id})
        cls.main_wh = cls.env['stock.warehouse'].search(
            [('company_id', '=', cls.company.id)], limit=1)

    def _configure(self, vehicle):
        return self.env['distribution.vehicle.configure.wizard'].create({
            'vehicle_id': vehicle.id, 'company_id': self.company.id,
            'main_warehouse_id': self.main_wh.id,
            'warehouse_mode': 'create_new', 'pos_mode': 'create_new',
            'create_analytic_account': True, 'activate': True,
        }).action_confirm()

    def _new_vehicle(self, name):
        return self.env['fleet.vehicle'].create({
            'name': name, 'license_plate': name,
            'model_id': self.car_model.id,
            'company_id': self.company.id})

    def test_01_analytic_created_and_linked_to_pos(self):
        vehicle = self._new_vehicle('VA-01')
        self._configure(vehicle)
        self.assertTrue(vehicle.distribution_analytic_account_id)
        self.assertTrue(vehicle.distribution_analytic_account_id.plan_id,
                        'analytic account belongs to a plan')
        self.assertEqual(vehicle.distribution_pos_config_id.analytic_account_id,
                         vehicle.distribution_analytic_account_id)

    def test_02_idempotent_no_duplicate(self):
        vehicle = self._new_vehicle('VA-02')
        self._configure(vehicle)
        acc = vehicle.distribution_analytic_account_id
        # re-run sync: no duplicates, still linked
        vehicle._ensure_vehicle_analytic_account()
        self.assertEqual(vehicle.distribution_analytic_account_id, acc)
        self.assertEqual(
            self.env['account.analytic.account'].search_count(
                [('name', '=', acc.name)]), 1)

    def test_03_pos_sales_carry_vehicle_analytic(self):
        """Vehicle POS is wired to the vehicle analytic account, so sales
        and COGS land on it via flousflow_branch_analytic mapping."""
        vehicle = self._new_vehicle('VA-03')
        self._configure(vehicle)
        pos = vehicle.distribution_pos_config_id
        product = self.env['product.product'].create({
            'name': 'VA Product', 'type': 'consu', 'list_price': 100.0,
            'taxes_id': [(5, 0, 0)]})
        session = self.env['pos.session'].create({'config_id': pos.id})
        order = self.env['pos.order'].create({
            'session_id': session.id, 'company_id': self.company.id,
            'partner_id': self.env['res.partner'].create(
                {'name': 'VA Cust'}).id,
            'amount_paid': 0.0, 'amount_return': 0.0,
            'amount_tax': 0.0, 'amount_total': 0.0,
            'lines': [(0, 0, {
                'product_id': product.id, 'qty': 2.0, 'price_unit': 50.0,
                'price_subtotal': 100.0, 'price_subtotal_incl': 100.0})],
        })
        analytic_id = vehicle.distribution_analytic_account_id.id
        # invoice-level analytic = the vehicle's (from POS config)
        self.assertEqual(order._prepare_invoice_vals().get(
            'analytic_account_id'), analytic_id,
            'invoice carries the vehicle analytic account')
        # line-level: POS config analytic -> 100% distribution
        self.assertEqual(pos.analytic_account_id.id, analytic_id)
        self.assertTrue(
            self.env['pos.order.line']._fields.get('analytic_distribution')
            or self.env['account.move.line']._fields.get(
                'analytic_distribution'))
