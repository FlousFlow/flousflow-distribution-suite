# -*- coding: utf-8 -*-
"""Full Core Phase test suite (spec tests 1-20 + end-to-end)."""
from odoo import fields
from odoo.exceptions import AccessError, UserError, ValidationError
from odoo.tests import tagged

from odoo.addons.point_of_sale.tests.common import TestPoSCommon


@tagged('post_install', '-at_install')
class TestDistributionVehicle(TestPoSCommon):
    """Core phase: vehicle ↔ warehouse ↔ POS ↔ employees ↔ loading."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        # Employee creation needs HR rights; the manager group implies them.
        cls.env.user.group_ids |= cls.env.ref('hr.group_hr_user')
        cls.env = cls.env(user=cls.env.ref('base.user_admin').id) \
            if False else cls.env
        cls.env.user.group_ids |= cls.env.ref(
            'flousflow_distribution_vehicle.group_distribution_vehicle_manager')
        cls.company = cls.env.company

        cls.emp_ahmed = cls.env['hr.employee'].create({
            'name': 'Ahmed Sales', 'company_id': cls.company.id})
        cls.emp_mohamed = cls.env['hr.employee'].create({
            'name': 'Mohamed Sales', 'company_id': cls.company.id})
        cls.emp_driver = cls.env['hr.employee'].create({
            'name': 'Mohamed Driver', 'company_id': cls.company.id})

        cls.sales_user = cls.env['res.users'].create({
            'name': 'Ahmed POS User', 'login': 'dist_vehicle_ahmed',
            'email': 'ahmed.veh@example.com',
            'group_ids': [(6, 0, [
                cls.env.ref('flousflow_distribution_vehicle.'
                            'group_distribution_vehicle_user').id,
                cls.env.ref('point_of_sale.group_pos_user').id,
            ])],
            'employee_ids': [(6, 0, [cls.emp_ahmed.id])],
        })

        cls.main_wh = cls.env['stock.warehouse'].create({
            'name': 'Main Cairo Warehouse', 'code': 'MWH',
            'company_id': cls.company.id,
        })

        cls.product = cls.create_product(
            'Vehicle Test Product', cls.categ_anglo, 100.0,
            standard_price=60.0)

        cls.vehicle_model = cls.env['fleet.vehicle.model'].create({
            'name': 'Test Van',
            'brand_id': cls.env['fleet.vehicle.model.brand'].create({
                'name': 'TestBrand'}).id,
        })
        cls.car1 = cls.env['fleet.vehicle'].create({
            'name': 'CAR-001', 'license_plate': 'ABC-123',
            'model_id': cls.vehicle_model.id,
            'company_id': cls.company.id,
            'is_distribution_vehicle': True,
        })
        cls.car2 = cls.env['fleet.vehicle'].create({
            'name': 'CAR-002', 'license_plate': 'XYZ-789',
            'model_id': cls.vehicle_model.id,
            'company_id': cls.company.id,
            'is_distribution_vehicle': True,
        })
        cls._configure(cls.car1, 1)
        cls._configure(cls.car2, 2)

        cls.vehicle_user_group = cls.env.ref(
            'flousflow_distribution_vehicle.group_distribution_vehicle_user')

    # ------------------------------------------------------------------
    @classmethod
    def _configure(cls, vehicle, seq):
        wizard = cls.env['distribution.vehicle.configure.wizard'].create({
            'vehicle_id': vehicle.id,
            'company_id': cls.company.id,
            'main_warehouse_id': cls.main_wh.id,
            'warehouse_mode': 'create_new',
            'pos_mode': 'create_new',
            'activate': True,
        })
        wizard.new_warehouse_name = '%s Warehouse' % vehicle.name
        wizard.action_confirm()

        journal = cls.env['account.journal'].create({
            'name': '%s Cash' % vehicle.name,
            'type': 'cash',
            'code': 'V%03d' % seq,
            'company_id': cls.company.id,
        })
        pm = cls.env['pos.payment.method'].create({
            'name': '%s Cash' % vehicle.name,
            'journal_id': journal.id,
            'receivable_account_id': cls.pos_receivable_cash.id,
            'company_id': cls.company.id,
        })
        vehicle.distribution_pos_config_id.write({
            'payment_method_ids': [(6, 0, pm.ids)],
        })

    def _session(self, vehicle):
        """Open (or reuse) the current session for the vehicle POS."""
        config = vehicle.distribution_pos_config_id
        if not config.current_session_id or \
                config.current_session_id.state == 'closed':
            config.open_ui()
        return config.current_session_id

    def _sell(self, vehicle, product, qty, user=None):
        """Backend POS order paid in cash from the vehicle POS config."""
        env = self.env if user is None else self.env(user=user)
        pos_config = vehicle.distribution_pos_config_id
        session = env['pos.session'].browse(
            self._session(vehicle).id)
        order = env['pos.order'].create({
            'amount_total': 0, 'amount_paid': 0, 'amount_tax': 0,
            'amount_return': 0,
            'date_order': fields.Datetime.to_string(fields.Datetime.now()),
            'company_id': self.company.id,
            'session_id': session.id,
            'lines': [(0, 0, {
                'product_id': product.id,
                'qty': qty,
                'price_unit': product.lst_price,
                'price_subtotal': product.lst_price * qty,
                'price_subtotal_incl': product.lst_price * qty,
                'tax_ids': [(6, 0, product.taxes_id.ids)],
            })],
        })
        order.lines._onchange_amount_line_all()
        order._compute_prices()
        # Payment is bookkeeping: run it with the manager env (POS wizards
        # need POS admin). The authorization under test happens at create.
        payment_context = {'active_ids': order.ids, 'active_id': order.id}
        payment = self.env['pos.make.payment'].with_context(
            **payment_context).create({
            'amount': product.lst_price * qty,
            'payment_method_id': pos_config.payment_method_ids[:1].id,
        })
        payment.with_context(**payment_context).check()
        return order

    def _load(self, vehicle, product, qty):
        wizard = self.env['distribution.vehicle.transfer.wizard'].create({
            'vehicle_id': vehicle.id,
            'direction': 'load',
            'source_warehouse_id': self.main_wh.id,
            'auto_validate': True,
            'line_ids': [(0, 0, {'product_id': product.id, 'quantity': qty})],
        })
        return wizard.action_confirm()

    def _unload(self, vehicle, product, qty):
        wizard = self.env['distribution.vehicle.transfer.wizard'].create({
            'vehicle_id': vehicle.id,
            'direction': 'unload',
            'source_warehouse_id': self.main_wh.id,
            'auto_validate': True,
            'line_ids': [(0, 0, {'product_id': product.id, 'quantity': qty})],
        })
        return wizard.action_confirm()

    def _qty(self, warehouse, product):
        return self.env['stock.quant']._get_available_quantity(
            product, warehouse.lot_stock_id)

    def _refund(self, order, product, qty):
        refund = self.env['pos.order'].browse(order.refund()['res_id'])
        refund.lines.write({'qty': -abs(qty)})
        refund._compute_prices()
        payment_context = {'active_ids': refund.ids, 'active_id': refund.id}
        refund_payment = self.env['pos.make.payment'].with_context(
            **payment_context).create({
            'amount': refund.amount_total,
            'payment_method_id': order.session_id.config_id
            .payment_method_ids[:1].id,
        })
        refund_payment.with_context(**payment_context).check()
        return refund

    # ------------------------------------------------------------------
    # Tests 1-4: configuration
    # ------------------------------------------------------------------
    def test_01_vehicle_flag_and_config(self):
        self.assertTrue(self.car1.is_distribution_vehicle)
        self.assertTrue(self.car1.distribution_active)
        self.assertEqual(self.car1.distribution_status, 'ready')

    def test_02_vehicle_warehouse_created(self):
        self.assertTrue(self.car1.distribution_warehouse_id)
        self.assertIn('Warehouse', self.car1.distribution_warehouse_id.name)
        self.assertEqual(self.car1.distribution_warehouse_id.company_id,
                         self.company)
        self.assertNotEqual(self.car1.distribution_warehouse_id, self.main_wh)

    def test_03_warehouse_unique_per_active_vehicle(self):
        with self.assertRaises(ValidationError):
            self.car2.distribution_warehouse_id = \
                self.car1.distribution_warehouse_id

    def test_04_vehicle_warehouse_pos_chain(self):
        config = self.car1.distribution_pos_config_id
        self.assertEqual(config.warehouse_id,
                         self.car1.distribution_warehouse_id)
        self.assertEqual(config.distribution_vehicle_id, self.car1)
        self.assertTrue(config.warehouse_id.lot_stock_id)

    # ------------------------------------------------------------------
    # Tests 5-7: assignments
    # ------------------------------------------------------------------
    def test_05_assign_salesman(self):
        self.env['fleet.vehicle.employee.assignment'].create({
            'vehicle_id': self.car1.id,
            'employee_id': self.emp_ahmed.id,
            'role': 'sales_rep',
            'company_id': self.company.id,
        })
        self.assertEqual(self.car1.current_salesman_id, self.emp_ahmed)
        self.assertIn(self.emp_ahmed, self.car1.distribution_employee_ids)

    def test_06_assign_driver(self):
        self.env['fleet.vehicle.employee.assignment'].create({
            'vehicle_id': self.car1.id,
            'employee_id': self.emp_driver.id,
            'role': 'driver',
            'company_id': self.company.id,
        })
        self.assertEqual(self.car1.current_driver_id, self.emp_driver)

    def test_07_assignment_history(self):
        assignment = self.env['fleet.vehicle.employee.assignment'].create({
            'vehicle_id': self.car1.id,
            'employee_id': self.emp_mohamed.id,
            'role': 'sales_rep',
            'company_id': self.company.id,
        })
        assignment.action_close()
        self.assertTrue(assignment.date_to)
        self.env['fleet.vehicle.employee.assignment'].create({
            'vehicle_id': self.car2.id,
            'employee_id': self.emp_mohamed.id,
            'role': 'sales_rep',
            'company_id': self.company.id,
        })
        history = self.env['fleet.vehicle.employee.assignment'].search([
            ('employee_id', '=', self.emp_mohamed.id)])
        self.assertEqual(len(history), 2)
        self.assertNotIn(self.emp_mohamed,
                         self.car1.distribution_employee_ids)
        self.assertIn(self.emp_mohamed,
                      self.car2.distribution_employee_ids)

    def test_overlapping_assignment_blocked(self):
        self.env['fleet.vehicle.employee.assignment'].create({
            'vehicle_id': self.car1.id,
            'employee_id': self.emp_mohamed.id,
            'role': 'sales_rep',
            'company_id': self.company.id,
        })
        with self.assertRaises(ValidationError):
            self.env['fleet.vehicle.employee.assignment'].create({
                'vehicle_id': self.car2.id,
                'employee_id': self.emp_mohamed.id,
                'role': 'sales_rep',
                'company_id': self.company.id,
            })

    # ------------------------------------------------------------------
    # Tests 8-9: loading (Main → Vehicle)
    # ------------------------------------------------------------------
    def test_08_load_vehicle(self):
        self.env['stock.quant']._update_available_quantity(
            self.product, self.main_wh.lot_stock_id, 1000)
        self._load(self.car1, self.product, 100)
        self.assertEqual(self._qty(self.main_wh, self.product), 900)
        self.assertEqual(
            self._qty(self.car1.distribution_warehouse_id, self.product), 100)

    def test_09_load_second_vehicle(self):
        self.env['stock.quant']._update_available_quantity(
            self.product, self.main_wh.lot_stock_id, 1000)
        self._load(self.car1, self.product, 100)
        self._load(self.car2, self.product, 150)
        self.assertEqual(self._qty(self.main_wh, self.product), 750)
        self.assertEqual(
            self._qty(self.car1.distribution_warehouse_id, self.product), 100)
        self.assertEqual(
            self._qty(self.car2.distribution_warehouse_id, self.product), 150)

    # ------------------------------------------------------------------
    # Tests 10-11: POS sales deduct from the vehicle warehouse only
    # ------------------------------------------------------------------
    def test_10_pos_sale_deducts_vehicle1(self):
        self.env['stock.quant']._update_available_quantity(
            self.product, self.main_wh.lot_stock_id, 1000)
        self._load(self.car1, self.product, 100)
        self._load(self.car2, self.product, 150)
        order = self._sell(self.car1, self.product, 25)
        import logging
        logging.getLogger('TMP_VEH').warning(
            'DBG10 state=%s pickings=%s session=%s',
            order.state, [(p.name, p.state, p.location_id.display_name,
                           p.location_dest_id.display_name)
                          for p in order.picking_ids],
            order.session_id.name)
        self.assertEqual(order.distribution_vehicle_id, self.car1)
        self.assertEqual(order.distribution_warehouse_id,
                         self.car1.distribution_warehouse_id)
        self.assertEqual(
            self._qty(self.car1.distribution_warehouse_id, self.product), 75)
        self.assertEqual(
            self._qty(self.car2.distribution_warehouse_id, self.product), 150)
        self.assertEqual(self._qty(self.main_wh, self.product), 750)

    def test_11_pos_sale_deducts_vehicle2(self):
        self.env['stock.quant']._update_available_quantity(
            self.product, self.main_wh.lot_stock_id, 1000)
        self._load(self.car1, self.product, 100)
        self._load(self.car2, self.product, 150)
        self._sell(self.car2, self.product, 40)
        self.assertEqual(
            self._qty(self.car2.distribution_warehouse_id, self.product), 110)
        self.assertEqual(
            self._qty(self.car1.distribution_warehouse_id, self.product), 100)
        self.assertEqual(self._qty(self.main_wh, self.product), 750)

    # ------------------------------------------------------------------
    # Test 12: POS return → vehicle warehouse
    # ------------------------------------------------------------------
    def test_12_pos_return_to_vehicle(self):
        self.env['stock.quant']._update_available_quantity(
            self.product, self.main_wh.lot_stock_id, 1000)
        self._load(self.car1, self.product, 100)
        order = self._sell(self.car1, self.product, 25)
        self._refund(order, self.product, 5)
        self.assertEqual(
            self._qty(self.car1.distribution_warehouse_id, self.product), 80)

    # ------------------------------------------------------------------
    # Tests 13-14: POS authorization
    # ------------------------------------------------------------------
    def test_13_ahmed_cannot_use_other_vehicle_pos(self):
        self.sales_user.group_ids |= self.vehicle_user_group
        self.env['fleet.vehicle.employee.assignment'].create({
            'vehicle_id': self.car1.id,
            'employee_id': self.emp_ahmed.id,
            'role': 'sales_rep',
            'company_id': self.company.id,
        })
        self.env.invalidate_all()
        with self.assertRaises(UserError):
            self._sell(self.car2, self.product, 1, user=self.sales_user)

    def test_14_manager_can_use_any_vehicle_pos(self):
        self.env['stock.quant']._update_available_quantity(
            self.product, self.main_wh.lot_stock_id, 100)
        self._load(self.car2, self.product, 20)
        order = self._sell(self.car2, self.product, 1)
        self.assertEqual(order.distribution_vehicle_id, self.car2)

    def test_ahmed_can_use_own_vehicle_pos(self):
        self.sales_user.group_ids |= self.vehicle_user_group
        self.env['fleet.vehicle.employee.assignment'].create({
            'vehicle_id': self.car1.id,
            'employee_id': self.emp_ahmed.id,
            'role': 'sales_rep',
            'company_id': self.company.id,
        })
        self.env['stock.quant']._update_available_quantity(
            self.product, self.main_wh.lot_stock_id, 100)
        self._load(self.car1, self.product, 10)
        self.env.invalidate_all()
        self._sell(self.car1, self.product, 1, user=self.sales_user)

    # ------------------------------------------------------------------
    # Tests 15-16: historical snapshots
    # ------------------------------------------------------------------
    def test_15_reassignment_keeps_old_orders(self):
        self.env['stock.quant']._update_available_quantity(
            self.product, self.main_wh.lot_stock_id, 1000)
        self._load(self.car1, self.product, 100)
        order = self._sell(self.car1, self.product, 5)
        self.assertEqual(order.distribution_vehicle_id, self.car1)
        self.env['fleet.vehicle.employee.assignment'].create({
            'vehicle_id': self.car2.id,
            'employee_id': self.emp_ahmed.id,
            'role': 'sales_rep',
            'company_id': self.company.id,
        })
        self.env.invalidate_all()
        self.assertEqual(order.distribution_vehicle_id, self.car1)

    def test_16_warehouse_change_keeps_old_orders(self):
        self._load(self.car1, self.product, 10)
        order = self._sell(self.car1, self.product, 1)
        old_wh = order.distribution_warehouse_id
        new_wh = self.env['stock.warehouse'].create({
            'name': 'CAR-001 New WH', 'code': 'CNW',
            'company_id': self.company.id,
        })
        self.car1.distribution_warehouse_id = new_wh
        self.assertEqual(order.distribution_warehouse_id, old_wh)

    # ------------------------------------------------------------------
    # Test 17: cross-company rejected
    # ------------------------------------------------------------------
    def test_17_cross_company_rejected(self):
        company2 = self.env['res.company'].create({'name': 'Veh Co 2'})
        wh2 = self.env['stock.warehouse'].create({
            'name': 'Co2 WH', 'code': 'C2W', 'company_id': company2.id})
        pos2 = self.env['pos.config'].with_company(company2).create({
            'name': 'Co2 POS', 'company_id': company2.id,
            'warehouse_id': wh2.id,
            'payment_method_ids': [(6, 0, [])],
        })
        # company2 needs its own payment method (a cash journal cannot be
        # shared between companies/configs).
        journal2 = self.env['account.journal'].create({
            'name': 'Co2 Cash', 'type': 'cash', 'code': 'C2CS',
            'company_id': company2.id,
        })
        pm2 = self.env['pos.payment.method'].create({
            'name': 'Co2 Cash', 'journal_id': journal2.id,
            'company_id': company2.id,
        })
        pos2.write({'payment_method_ids': [(6, 0, pm2.ids)]})
        with self.assertRaises(ValidationError):
            self.car1.distribution_warehouse_id = wh2.id
        with self.assertRaises(ValidationError):
            self.car2.distribution_main_warehouse_id = wh2.id
        with self.assertRaises(ValidationError):
            self.car2.distribution_pos_config_id = pos2.id

    # ------------------------------------------------------------------
    # Test 18: unload (Vehicle → Main)
    # ------------------------------------------------------------------
    def test_18_unload_vehicle(self):
        self.env['stock.quant']._update_available_quantity(
            self.product, self.main_wh.lot_stock_id, 1000)
        self._load(self.car1, self.product, 100)
        self._unload(self.car1, self.product, 30)
        self.assertEqual(
            self._qty(self.car1.distribution_warehouse_id, self.product), 70)
        self.assertEqual(self._qty(self.main_wh, self.product), 930)

    # ------------------------------------------------------------------
    # Tests 19-20: POS closing + accounting balance
    # ------------------------------------------------------------------
    def test_19_pos_closing_succeeds(self):
        self.env['stock.quant']._update_available_quantity(
            self.product, self.main_wh.lot_stock_id, 1000)
        self._load(self.car1, self.product, 50)
        self._sell(self.car1, self.product, 5)
        session = self.car1.distribution_pos_config_id.current_session_id
        session.action_pos_session_closing_control()
        self.assertEqual(session.state, 'closed')

    def test_20_accounting_entries_balanced(self):
        self.env['stock.quant']._update_available_quantity(
            self.product, self.main_wh.lot_stock_id, 1000)
        self._load(self.car1, self.product, 50)
        self._sell(self.car1, self.product, 5)
        session = self.car1.distribution_pos_config_id.current_session_id
        session.action_pos_session_closing_control()
        moves = self.env['account.move'].search([
            ('pos_session_ids', 'in', session.id)])
        self.assertTrue(moves)
        for move in moves:
            self.assertAlmostEqual(
                sum(move.line_ids.mapped('debit')),
                sum(move.line_ids.mapped('credit')), places=2)

    # ------------------------------------------------------------------
    # Negative stock policy
    # ------------------------------------------------------------------
    def test_negative_stock_blocked_by_default(self):
        self._load(self.car1, self.product, 10)
        with self.assertRaises(UserError):
            self._sell(self.car1, self.product, 15)

    def test_negative_stock_allowed_when_enabled(self):
        self.env['ir.config_parameter'].sudo().set_param(
            'distribution_vehicle.allow_negative_stock', 'True')
        self._load(self.car1, self.product, 10)
        self._sell(self.car1, self.product, 15)
        self.env['ir.config_parameter'].sudo().set_param(
            'distribution_vehicle.allow_negative_stock', 'False')

    # ------------------------------------------------------------------
    # End-to-end (spec full flow)
    # ------------------------------------------------------------------
    def test_e2e_full_flow(self):
        self.env['stock.quant']._update_available_quantity(
            self.product, self.main_wh.lot_stock_id, 1000)
        self._load(self.car1, self.product, 100)
        self._load(self.car2, self.product, 150)
        self.assertEqual(self._qty(self.main_wh, self.product), 750)

        order1 = self._sell(self.car1, self.product, 25)
        self.assertEqual(
            self._qty(self.car1.distribution_warehouse_id, self.product), 75)

        self._sell(self.car2, self.product, 40)
        self.assertEqual(
            self._qty(self.car2.distribution_warehouse_id, self.product), 110)

        self._refund(order1, self.product, 5)
        self.assertEqual(
            self._qty(self.car1.distribution_warehouse_id, self.product), 80)

        self._unload(self.car1, self.product, 30)
        self.assertEqual(
            self._qty(self.car1.distribution_warehouse_id, self.product), 50)
        self.assertEqual(self._qty(self.main_wh, self.product), 780)
