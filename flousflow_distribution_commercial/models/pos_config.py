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

    def _load_pos_data_fields(self, config):
        fields = super()._load_pos_data_fields(config)
        fields += ['distribution_visit_context_raw']
        return fields

    def open_ui(self):
        """Opening the POS normally (not from a visit) clears any stale
        visit context. The visit action passes a keep flag."""
        if not self.env.context.get('keep_distribution_visit'):
            self.filtered('distribution_visit_context_raw').write(
                {'distribution_visit_context_raw': 0})
        return super().open_ui()
