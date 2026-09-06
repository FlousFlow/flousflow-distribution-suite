# -*- coding: utf-8 -*-
"""Collections recorded by the employee — smart button data (spec #61)."""
from odoo import fields, models


class HrEmployee(models.Model):
    _inherit = 'hr.employee'

    distribution_collection_count = fields.Integer(
        compute='_compute_distribution_collection_count',
        string='Collections')

    def _compute_distribution_collection_count(self):
        for employee in self:
            employee.distribution_collection_count = self.env[
                'distribution.visit.collection'].search_count(
                    [('employee_id', '=', employee.id)])

    def action_view_distribution_collections(self):
        self.ensure_one()
        return {
            'type': 'ir.actions.act_window',
            'name': _('Distribution Collections'),
            'res_model': 'distribution.visit.collection',
            'view_mode': 'list,form,pivot',
            'domain': [('employee_id', '=', self.id)],
            'context': {},
        }
