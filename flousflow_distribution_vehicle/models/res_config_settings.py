# -*- coding: utf-8 -*-
from odoo import fields, models


class ResConfigSettings(models.TransientModel):
    _inherit = 'res.config.settings'

    distribution_allow_vehicle_negative_stock = fields.Boolean(
        string='Allow Vehicle Negative Stock',
        config_parameter='distribution_vehicle.allow_negative_stock',
        help="Allow POS sales exceeding the vehicle warehouse quantity. "
             "Disabled by default: selling more than the vehicle holds is "
             "blocked until the vehicle is loaded.",
    )
