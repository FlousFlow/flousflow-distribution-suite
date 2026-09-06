# -*- coding: utf-8 -*-
"""Route Visits can reach the route's vehicle snapshot (spec #20) without
duplicating stored fields — non-stored related fields only."""
from odoo import fields, models


class DistributionRouteVisit(models.Model):
    _inherit = 'distribution.route.visit'

    vehicle_id = fields.Many2one(
        related='route_id.vehicle_id', string='Route Vehicle')
    vehicle_warehouse_id = fields.Many2one(
        related='route_id.vehicle_warehouse_id', string='Route Vehicle '
                                                        'Warehouse')
    vehicle_pos_config_id = fields.Many2one(
        related='route_id.vehicle_pos_config_id', string='Route Vehicle POS')
