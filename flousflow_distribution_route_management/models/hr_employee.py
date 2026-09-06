# -*- coding: utf-8 -*-
from odoo import _, api, fields, models


class HrEmployee(models.Model):
    _inherit = 'hr.employee'

    distribution_route_count = fields.Integer(
        compute='_compute_distribution_counts',
        string='Route Plans',
    )
    distribution_visit_count = fields.Integer(
        compute='_compute_distribution_counts',
        string='Distribution Visits',
    )

    def _compute_distribution_counts(self):
        Plan = self.env['distribution.route.plan']
        Visit = self.env['distribution.route.visit']
        route_counts = dict(
            Plan._read_group(
                domain=[('employee_id', 'in', self.ids)],
                groupby=['employee_id'],
                aggregates=['__count'],
            )
        )
        visit_counts = dict(
            Visit._read_group(
                domain=[('employee_id', 'in', self.ids)],
                groupby=['employee_id'],
                aggregates=['__count'],
            )
        )
        for employee in self:
            employee.distribution_route_count = route_counts.get(employee, 0)
            employee.distribution_visit_count = visit_counts.get(employee, 0)

    def action_view_distribution_routes(self):
        self.ensure_one()
        return {
            'type': 'ir.actions.act_window',
            'name': _('Route Plans'),
            'res_model': 'distribution.route.plan',
            'view_mode': 'list,form,kanban,calendar',
            'domain': [('employee_id', '=', self.id)],
            'context': {'default_employee_id': self.id},
        }

    def action_view_distribution_visits(self):
        self.ensure_one()
        return {
            'type': 'ir.actions.act_window',
            'name': _('Distribution Visits'),
            'res_model': 'distribution.route.visit',
            'view_mode': 'list,form,calendar,kanban',
            'domain': [('employee_id', '=', self.id)],
            'context': {'default_employee_id': self.id},
        }
