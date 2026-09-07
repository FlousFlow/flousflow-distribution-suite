from odoo import fields
from odoo.fields import Command
from odoo.tests import tagged

from odoo.addons.point_of_sale.tests.common import TestPoSCommon


@tagged('post_install', '-at_install')
class TestPosWarehouseFlow(TestPoSCommon):
    """End-to-end warehouse routing: sales deduct from the assigned warehouse,
    returns go back to it and other warehouses stay untouched."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.env.user.group_ids |= cls.env.ref('point_of_sale.group_pos_manager')

        # Two warehouses with their own stock locations.
        cls.cairo = cls.env['stock.warehouse'].create({
            'name': 'Cairo', 'code': 'CAI', 'company_id': cls.env.company.id,
        })
        cls.giza = cls.env['stock.warehouse'].create({
            'name': 'Giza', 'code': 'GIZ', 'company_id': cls.env.company.id,
        })

        # Storable product with real-time valuation (COGS capable).
        cls.product = cls.create_product(
            'POS WH Product', cls.categ_anglo, 100.0, standard_price=60.0)
        cls.service = cls.env['product.product'].create({
            'name': 'POS WH Service',
            'type': 'service',
            'taxes_id': [],
            'list_price': 50.0,
        })
        cls.lot_product = cls.env['product.product'].create({
            'name': 'POS WH Lot Product',
            'type': 'consu',
            'is_storable': True,
            'categ_id': cls.categ_anglo.id,
            'tracking': 'lot',
            'taxes_id': [],
            'list_price': 100.0,
            'standard_price': 60.0,
        })

        cls.cash_cairo = cls._create_cash_pm('Cairo Cash')
        cls.cash_giza = cls._create_cash_pm('Giza Cash')

        cls.cairo_config = cls.env['pos.config'].create({
            'name': 'Cairo POS',
            'warehouse_id': cls.cairo.id,
            'invoice_journal_id': cls.invoice_journal.id,
            'payment_method_ids': [(6, 0, cls.cash_cairo.ids)],
        })
        cls.giza_config = cls.env['pos.config'].create({
            'name': 'Giza POS',
            'warehouse_id': cls.giza.id,
            'invoice_journal_id': cls.invoice_journal.id,
            'payment_method_ids': [(6, 0, cls.cash_giza.ids)],
        })

    @classmethod
    def _create_cash_pm(cls, name):
        """A dedicated cash payment method per POS config (a cash journal
        cannot be shared between two POS configurations)."""
        cls._cash_pm_seq = getattr(cls, '_cash_pm_seq', 0) + 1
        journal = cls.env['account.journal'].create({
            'name': name,
            'type': 'cash',
            'code': 'C%03d' % cls._cash_pm_seq,
            'company_id': cls.env.company.id,
        })
        return cls.env['pos.payment.method'].create({
            'name': name,
            'journal_id': journal.id,
            'receivable_account_id': cls.pos_receivable_cash.id,
            'company_id': cls.env.company.id,
        })

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------
    def _set_inventory(self, warehouse, product, qty, lot=False):
        self.env['stock.quant']._update_available_quantity(
            product, warehouse.lot_stock_id, qty,
            lot_id=lot if lot else False,
        )

    def _get_quantity(self, warehouse, product, lot=False):
        domain = [
            ('product_id', '=', product.id),
            ('location_id', '=', warehouse.lot_stock_id.id),
        ]
        if lot:
            domain.append(('lot_id', '=', lot.id))
        quants = self.env['stock.quant'].search(domain)
        return sum(quants.mapped('quantity'))

    def create_backend_pos_order(self, data):
        """Create a paid POS order for a given config (adapted from
        point_of_sale CommonPosTest; TestPoSCommon does not provide it)."""
        pos_config = data.get('pos_config', self.cairo_config)
        order_data = data.get('order_data', {})
        line_product_ids = [line_data['product_id'] for line_data in data.get('line_data', [])]
        product_by_id = {p.id: p for p in self.env['product.product'].browse(line_product_ids)}

        if not pos_config.current_session_id:
            pos_config.open_ui()

        order = self.env['pos.order'].create({
            'amount_total': 0,
            'amount_paid': 0,
            'amount_tax': 0,
            'amount_return': 0,
            'date_order': fields.Datetime.to_string(fields.Datetime.now()),
            'company_id': self.env.company.id,
            'session_id': pos_config.current_session_id.id,
            'lines': [
                Command.create({
                    'price_unit': product_by_id[line_data['product_id']].lst_price,
                    'price_subtotal': product_by_id[line_data['product_id']].lst_price,
                    'tax_ids': [(6, 0, product_by_id[line_data['product_id']].taxes_id.ids)],
                    'price_subtotal_incl': 0,
                    **line_data,
                }) for line_data in data.get('line_data', [])
            ],
            **order_data,
        })

        order.lines._onchange_amount_line_all()
        order._compute_prices()

        if data.get('payment_data'):
            payment_context = {"active_ids": order.ids, "active_id": order.id}
            for payment in data['payment_data']:
                make_payment = {'payment_method_id': payment['payment_method_id']}
                if payment.get('amount'):
                    make_payment['amount'] = payment['amount']
                order_payment = self.env['pos.make.payment'].with_context(**payment_context).create(make_payment)
                order_payment.with_context(**payment_context).check()

        return order

    def _make_refund(self, order, qty=False, payment_method=None):
        """Create a refund order for ``order`` (optionally partial) and pay it."""
        refund = self.env['pos.order'].browse(order.refund()['res_id'])
        if qty is not False:
            refund.lines.write({'qty': -abs(qty)})
            refund._compute_prices()
        payment_method = payment_method or self.cash_cairo
        payment_context = {"active_ids": refund.ids, "active_id": refund.id}
        refund_payment = self.env['pos.make.payment'].with_context(**payment_context).create({
            'amount': refund.amount_total,
            'payment_method_id': payment_method.id,
        })
        refund_payment.with_context(**payment_context).check()
        return refund

    # ------------------------------------------------------------------
    # Tests
    # ------------------------------------------------------------------
    def test_01_sale_deducts_from_assigned_warehouse_only(self):
        self._set_inventory(self.cairo, self.product, 10)
        self._set_inventory(self.giza, self.product, 20)

        order = self.create_backend_pos_order({
            'pos_config': self.cairo_config,
            'line_data': [{'product_id': self.product.id, 'qty': 3}],
            'payment_data': [{'payment_method_id': self.cash_cairo.id, 'amount': 300.0}],
        })

        self.assertEqual(self._get_quantity(self.cairo, self.product), 7)
        self.assertEqual(self._get_quantity(self.giza, self.product), 20)

        self.assertEqual(len(order.picking_ids), 1)
        picking = order.picking_ids
        self.assertEqual(picking.picking_type_id, self.cairo.pos_type_id)
        self.assertEqual(picking.location_id, self.cairo.lot_stock_id)
        self.assertEqual(picking.location_dest_id.usage, 'customer')

    def test_02_other_pos_deducts_from_its_own_warehouse(self):
        self._set_inventory(self.cairo, self.product, 10)
        self._set_inventory(self.giza, self.product, 20)

        self.create_backend_pos_order({
            'pos_config': self.giza_config,
            'line_data': [{'product_id': self.product.id, 'qty': 5}],
            'payment_data': [{'payment_method_id': self.cash_giza.id, 'amount': 500.0}],
        })

        self.assertEqual(self._get_quantity(self.cairo, self.product), 10)
        self.assertEqual(self._get_quantity(self.giza, self.product), 15)

    def test_03_partial_return_goes_back_to_same_warehouse(self):
        self._set_inventory(self.cairo, self.product, 10)
        self._set_inventory(self.giza, self.product, 20)

        order = self.create_backend_pos_order({
            'pos_config': self.cairo_config,
            'line_data': [{'product_id': self.product.id, 'qty': 3}],
            'payment_data': [{'payment_method_id': self.cash_cairo.id, 'amount': 300.0}],
        })
        self.assertEqual(self._get_quantity(self.cairo, self.product), 7)

        self._make_refund(order, qty=1)
        self.assertEqual(self._get_quantity(self.cairo, self.product), 8)
        self.assertEqual(self._get_quantity(self.giza, self.product), 20)

    def test_04_full_return_multi_product(self):
        self._set_inventory(self.cairo, self.product, 10)
        self._set_inventory(self.giza, self.product, 20)

        order = self.create_backend_pos_order({
            'pos_config': self.cairo_config,
            'line_data': [
                {'product_id': self.product.id, 'qty': 2},
                {'product_id': self.product.id, 'qty': 1},
            ],
            'payment_data': [{'payment_method_id': self.cash_cairo.id, 'amount': 300.0}],
        })
        self.assertEqual(self._get_quantity(self.cairo, self.product), 7)

        self._make_refund(order)
        self.assertEqual(self._get_quantity(self.cairo, self.product), 10)
        self.assertEqual(self._get_quantity(self.giza, self.product), 20)

    def test_05_two_pos_share_one_warehouse(self):
        cash_pm_2 = self._create_cash_pm('Cairo Cash 2')
        cairo_config_2 = self.env['pos.config'].create({
            'name': 'Cairo POS 2',
            'warehouse_id': self.cairo.id,
            'invoice_journal_id': self.invoice_journal.id,
            'payment_method_ids': [(6, 0, cash_pm_2.ids)],
        })
        self.assertEqual(cairo_config_2.picking_type_id, self.cairo.pos_type_id)

        self._set_inventory(self.cairo, self.product, 10)
        self._set_inventory(self.giza, self.product, 20)

        self.create_backend_pos_order({
            'pos_config': self.cairo_config,
            'line_data': [{'product_id': self.product.id, 'qty': 2}],
            'payment_data': [{'payment_method_id': self.cash_cairo.id, 'amount': 200.0}],
        })
        self.create_backend_pos_order({
            'pos_config': cairo_config_2,
            'line_data': [{'product_id': self.product.id, 'qty': 3}],
            'payment_data': [{'payment_method_id': cash_pm_2.id, 'amount': 300.0}],
        })

        self.assertEqual(self._get_quantity(self.cairo, self.product), 5)
        self.assertEqual(self._get_quantity(self.giza, self.product), 20)

    def test_06_service_product_creates_no_picking(self):
        self._set_inventory(self.cairo, self.product, 10)
        order = self.create_backend_pos_order({
            'pos_config': self.cairo_config,
            'line_data': [{'product_id': self.service.id, 'qty': 1}],
            'payment_data': [{'payment_method_id': self.cash_cairo.id, 'amount': 50.0}],
        })
        self.assertFalse(order.picking_ids)

    def test_07_lot_product_sold_from_assigned_warehouse(self):
        lot = self.env['stock.lot'].create({
            'name': 'CAI-LOT-001',
            'product_id': self.lot_product.id,
            'company_id': self.env.company.id,
        })
        self._set_inventory(self.cairo, self.lot_product, 10, lot=lot)

        order = self.create_backend_pos_order({
            'pos_config': self.cairo_config,
            'line_data': [{
                'product_id': self.lot_product.id,
                'qty': 2,
                'pack_lot_ids': [(0, 0, {
                    'lot_name': lot.name,
                    'product_id': self.lot_product.id,
                })],
            }],
            'payment_data': [{'payment_method_id': self.cash_cairo.id, 'amount': 200.0}],
        })

        self.assertEqual(self._get_quantity(self.cairo, self.lot_product, lot=lot), 8)
        self.assertTrue(order.picking_ids)
        self.assertEqual(order.picking_ids.location_id, self.cairo.lot_stock_id)

    def test_08_picking_type_is_warehouse_specific(self):
        self._set_inventory(self.cairo, self.product, 10)
        self._set_inventory(self.giza, self.product, 10)

        cairo_order = self.create_backend_pos_order({
            'pos_config': self.cairo_config,
            'line_data': [{'product_id': self.product.id, 'qty': 1}],
            'payment_data': [{'payment_method_id': self.cash_cairo.id, 'amount': 100.0}],
        })
        giza_order = self.create_backend_pos_order({
            'pos_config': self.giza_config,
            'line_data': [{'product_id': self.product.id, 'qty': 1}],
            'payment_data': [{'payment_method_id': self.cash_giza.id, 'amount': 100.0}],
        })

        self.assertEqual(cairo_order.picking_ids.picking_type_id, self.cairo.pos_type_id)
        self.assertEqual(giza_order.picking_ids.picking_type_id, self.giza.pos_type_id)
        self.assertNotEqual(
            cairo_order.picking_ids.picking_type_id, giza_order.picking_ids.picking_type_id)
