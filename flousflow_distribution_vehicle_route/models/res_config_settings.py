# -*- coding: utf-8 -*-
from odoo import fields, models


class ResConfigSettings(models.TransientModel):
    _inherit = 'res.config.settings'

    distribution_require_vehicle_on_route = fields.Boolean(
        related='company_id.distribution_require_vehicle_on_route',
        readonly=False,
        string='Require Vehicle on Route',
    )
    distribution_require_vehicle_pos_on_route = fields.Boolean(
        related='company_id.distribution_require_vehicle_pos_on_route',
        readonly=False,
        string='Require Vehicle POS on Route',
    )
