from odoo.exceptions import UserError, ValidationError
from odoo.tests import tagged

from odoo.addons.point_of_sale.tests.common import TestPoSCommon


@tagged('post_install', '-at_install')
class TestPosWarehouseConfig(TestPoSCommon):
    """Configuration-level behaviour of the POS Warehouse assignment."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.env.user.group_ids |= cls.env.ref('point_of_sale.group_pos_manager')
        cls.cairo = cls.env['stock.warehouse'].create({
            'name': 'Cairo', 'code': 'CAI', 'company_id': cls.env.company.id,
        })
        cls.giza = cls.env['stock.warehouse'].create({
            'name': 'Giza', 'code': 'GIZ', 'company_id': cls.env.company.id,
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

    def _get_pos_config(self, **kwargs):
        cash_pm = self._create_cash_pm('WH Config Cash')
        vals = {
            'name': 'POS Warehouse Test',
            'invoice_journal_id': self.invoice_journal.id,
            'payment_method_ids': [(6, 0, cash_pm.ids)],
        }
        vals.update(kwargs)
        return self.env['pos.config'].create(vals)

    # ------------------------------------------------------------------
    # Warehouse drives the operation type
    # ------------------------------------------------------------------
    def test_warehouse_drives_picking_type_and_source(self):
        config = self._get_pos_config(warehouse_id=self.cairo.id)
        self.assertEqual(config.warehouse_id, self.cairo)
        self.assertEqual(config.picking_type_id, self.cairo.pos_type_id)
        self.assertEqual(config.picking_type_id.code, 'outgoing')
        self.assertEqual(
            config.picking_type_id.default_location_src_id, self.cairo.lot_stock_id)
        self.assertEqual(config.warehouse_source_location_id, self.cairo.lot_stock_id)
        self.assertEqual(config.picking_type_id.default_location_dest_id.usage, 'customer')

    def test_warehouse_change_updates_picking_type(self):
        config = self._get_pos_config(warehouse_id=self.cairo.id)
        config.write({'warehouse_id': self.giza.id})
        self.assertEqual(config.warehouse_id, self.giza)
        self.assertEqual(config.picking_type_id, self.giza.pos_type_id)
        self.assertEqual(config.warehouse_source_location_id, self.giza.lot_stock_id)

    def test_multi_pos_share_same_warehouse(self):
        config_1 = self._get_pos_config(warehouse_id=self.cairo.id, name='Cairo POS 1')
        config_2 = self._get_pos_config(warehouse_id=self.cairo.id, name='Cairo POS 2')
        self.assertEqual(config_1.picking_type_id, config_2.picking_type_id)
        self.assertEqual(config_1.picking_type_id, self.cairo.pos_type_id)

    # ------------------------------------------------------------------
    # Company validation
    # ------------------------------------------------------------------
    def test_company_mismatch_blocked(self):
        other_company = self.env['res.company'].create({'name': 'Other Company'})
        other_warehouse = self.env['stock.warehouse'].create({
            'name': 'Other WH', 'code': 'OTH', 'company_id': other_company.id,
        })
        with self.assertRaises(ValidationError):
            self._get_pos_config(warehouse_id=other_warehouse.id)

    # ------------------------------------------------------------------
    # Session consistency
    # ------------------------------------------------------------------
    def test_warehouse_change_blocked_while_session_open(self):
        config = self._get_pos_config(warehouse_id=self.cairo.id)
        session = self.env['pos.session'].create({'config_id': config.id})
        self.assertNotEqual(session.state, 'closed')
        with self.assertRaises(UserError):
            config.write({'warehouse_id': self.giza.id})

    def test_picking_type_change_blocked_while_session_open(self):
        config = self._get_pos_config(warehouse_id=self.cairo.id)
        self.env['pos.session'].create({'config_id': config.id})
        with self.assertRaises(UserError):
            config.write({'picking_type_id': self.giza.pos_type_id.id})
