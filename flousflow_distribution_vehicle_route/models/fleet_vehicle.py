# -*- coding: utf-8 -*-
"""Vehicle: Routes smart button (spec #18)."""
from odoo import _, api, fields, models


class FleetVehicle(models.Model):
    _inherit = 'fleet.vehicle'

    distribution_route_ids = fields.One2many(
        'distribution.route.plan', 'vehicle_id',
        string='Distribution Routes')
    distribution_route_count = fields.Integer(
        compute='_compute_distribution_route_count',
        string='Route Plans')

    @api.depends('distribution_route_ids')
    def _compute_distribution_route_count(self):
        for vehicle in self:
            vehicle.distribution_route_count = len(vehicle.distribution_route_ids)

    def action_view_distribution_routes(self):
        self.ensure_one()
        return {
            'type': 'ir.actions.act_window',
            'name': _('Route Plans'),
            'res_model': 'distribution.route.plan',
            'view_mode': 'list,form,kanban,calendar',
            'domain': [('vehicle_id', '=', self.id)],
            'context': {
                'default_vehicle_id': self.id,
                'search_default_filter_my_routes': 0,
            },
        }
