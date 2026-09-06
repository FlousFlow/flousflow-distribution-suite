# -*- coding: utf-8 -*-
from odoo import fields, models


class StockWarehouse(models.Model):
    _inherit = 'stock.warehouse'

    distribution_vehicle_ids = fields.One2many(
        'fleet.vehicle', 'distribution_warehouse_id',
        string='Distribution Vehicles')
    is_distribution_vehicle_warehouse = fields.Boolean(
        compute='_compute_is_distribution_vehicle_warehouse',
        string='Vehicle Warehouse')

    def _compute_is_distribution_vehicle_warehouse(self):
        for warehouse in self:
            warehouse.is_distribution_vehicle_warehouse = bool(
                warehouse.distribution_vehicle_ids.filtered(
                    lambda v: v.is_distribution_vehicle))
