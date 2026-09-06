# -*- coding: utf-8 -*-
"""Assignment: Routes smart button (spec #29)."""
from odoo import _, api, fields, models


class FleetVehicleEmployeeAssignment(models.Model):
    _inherit = 'fleet.vehicle.employee.assignment'

    distribution_route_ids = fields.One2many(
        'distribution.route.plan', 'vehicle_assignment_id',
        string='Route Plans using this Assignment')
    distribution_route_count = fields.Integer(
        compute='_compute_distribution_route_count',
        string='Route Plans')

    @api.depends('distribution_route_ids')
    def _compute_distribution_route_count(self):
        for assignment in self:
            assignment.distribution_route_count = len(
                assignment.distribution_route_ids)

    def action_view_distribution_routes(self):
        self.ensure_one()
        return {
            'type': 'ir.actions.act_window',
            'name': _('Routes using this Assignment'),
            'res_model': 'distribution.route.plan',
            'view_mode': 'list,form,kanban,calendar',
            'domain': [('vehicle_assignment_id', '=', self.id)],
            'context': {'default_vehicle_assignment_id': self.id},
        }
