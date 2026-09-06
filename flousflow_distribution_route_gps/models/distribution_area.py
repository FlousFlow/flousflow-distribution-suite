# -*- coding: utf-8 -*-
from odoo import fields, models


class DistributionArea(models.Model):
    _inherit = 'distribution.area'

    default_geofence_radius = fields.Float(
        string='Default Geofence Radius (m)', digits=(16, 2),
        help="Default allowed distance from customers in this area, in "
             "meters. Used when the customer has no specific radius. "
             "Leave empty to use the global default.",
    )
