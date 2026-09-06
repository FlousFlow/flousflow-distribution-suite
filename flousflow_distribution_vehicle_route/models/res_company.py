# -*- coding: utf-8 -*-
from odoo import fields, models


class ResCompany(models.Model):
    _inherit = 'res.company'

    distribution_require_vehicle_on_route = fields.Boolean(
        string='Require Vehicle on Route',
        default=True,
        help="Route plans cannot be confirmed unless the employee has an "
             "active vehicle assignment (resolved vehicle becomes the "
             "route snapshot).")
    distribution_require_vehicle_pos_on_route = fields.Boolean(
        string='Require Vehicle POS on Route',
        default=True,
        help="Route vehicles must have a POS configuration before the "
             "route can be confirmed or started.")
