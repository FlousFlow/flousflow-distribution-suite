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

    #: In a plain install none of the stock Odoo POS extension modules
    #: override ``_load_pos_data_fields`` for ``pos.config``, so the mixin
    #: default (``[]``) would leave the frontend with almost no data and
    #: crash (e.g. ``TypeError: Cannot read properties of undefined
    #: (reading 'currency_id')``, ``config.raw.trusted_config_ids is not
    #: iterable``). ``pos.config`` is a single record, so loading **all**
    #: fields is cheap and future-proof: any field the POS frontend reads
    #: (currency_id, trusted_config_ids, ...) is always present, whatever
    #: optional POS modules are installed.
    def _load_pos_data_fields(self, config):
        fields = super()._load_pos_data_fields(config)
        fields += [f for f in self._fields if f not in fields]
        return fields

    def open_ui(self):
        """Opening the POS normally (not from a visit) clears any stale
        visit context. The visit action passes a keep flag."""
        if not self.env.context.get('keep_distribution_visit'):
            self.filtered('distribution_visit_context_raw').write(
                {'distribution_visit_context_raw': 0})
        return super().open_ui()
