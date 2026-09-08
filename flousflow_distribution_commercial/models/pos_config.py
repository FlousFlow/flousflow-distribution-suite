# -*- coding: utf-8 -*-
"""Vehicle POS config carries the active visit context (raw id) so the
POS frontend copies it onto every new order. Set by the visit's
"Start POS Sale" action; cleared whenever the POS is opened normally."""
from odoo import api, fields, models


class PosConfig(models.Model):
    _inherit = 'pos.config'

    distribution_visit_context_raw = fields.Integer(
        string='Distribution Visit Context', default=0, copy=False,
        help="Technical: id of the visit whose commercial context is "
             "injected into new POS orders. Set by the visit action, "
             "cleared on normal POS open.")

    #: Fields the POS frontend requires on ``pos.config`` regardless of
    #: which optional Odoo modules are installed. In a plain install none
    #: of the stock Odoo POS extension modules override
    #: ``_load_pos_data_fields`` for ``pos.config``, so the mixin default
    #: (``[]``) would leave the frontend with almost no data and crash
    #: (e.g. ``TypeError: Cannot read properties of undefined (reading
    #: 'currency_id')``). We guarantee the full essential field set here.
    POS_CONFIG_ESSENTIAL_FIELDS = [
        'id', 'name', 'company_id', 'currency_id', 'journal_id',
        'invoice_journal_id', 'pricelist_id', 'use_pricelist',
        'available_pricelist_ids', 'picking_type_id', 'warehouse_id',
        'payment_method_ids', 'limit_categories', 'iface_available_categ_ids',
        'module_pos_restaurant', 'module_pos_hr', 'module_pos_discount',
        'module_pos_preparation_display', 'is_header_or_footer',
        'receipt_header', 'receipt_footer', 'iface_tax_included',
        'iface_print_auto', 'iface_print_skip_screen', 'iface_tipproduct',
        'tip_product_id', 'fiscal_position_ids', 'default_fiscal_position_id',
        'default_bill_ids', 'cash_rounding', 'rounding_method',
        'amount_authorized_diff', 'use_presets', 'default_preset_id',
        'available_preset_ids', 'uuid', 'last_data_change',
        'other_devices', 'is_posbox', 'barcode_nomenclature_id',
        'group_pos_manager_id', 'group_pos_user_id', 'current_user_id',
        'has_active_session', 'pos_session_username', 'pos_session_state',
        'pos_session_duration', 'use_fast_payment',
        'fast_payment_method_ids', 'distribution_visit_context_raw',
    ]

    def _load_pos_data_fields(self, config):
        fields = super()._load_pos_data_fields(config)
        for f in self.POS_CONFIG_ESSENTIAL_FIELDS:
            if f not in fields:
                fields.append(f)
        return fields

    def open_ui(self):
        """Opening the POS normally (not from a visit) clears any stale
        visit context. The visit action passes a keep flag."""
        if not self.env.context.get('keep_distribution_visit'):
            self.filtered('distribution_visit_context_raw').write(
                {'distribution_visit_context_raw': 0})
        return super().open_ui()
