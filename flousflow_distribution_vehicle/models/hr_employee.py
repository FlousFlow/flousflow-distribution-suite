# -*- coding: utf-8 -*-
from odoo import api, fields, models


class HrEmployee(models.Model):
    _inherit = 'hr.employee'

    current_distribution_vehicle_id = fields.Many2one(
        'fleet.vehicle', compute='_compute_current_distribution_vehicle',
        string='Current Distribution Vehicle', store=True, index=True,
        help="Vehicle on which this employee currently has an open "
             "assignment.")
    distribution_assignment_ids = fields.One2many(
        'fleet.vehicle.employee.assignment', 'employee_id',
        string='Distribution Vehicle History')

    @api.depends('distribution_assignment_ids.date_to',
                 'distribution_assignment_ids.vehicle_id')
    def _compute_current_distribution_vehicle(self):
        for employee in self:
            open_assignments = employee.distribution_assignment_ids.filtered(
                lambda a: not a.date_to)
            employee.current_distribution_vehicle_id = (
                open_assignments[:1].vehicle_id)
