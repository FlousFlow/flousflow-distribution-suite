# -*- coding: utf-8 -*-
"""Employee: current-route helper (spec #23) — computed on demand, never
stored in a global variable."""
from odoo import fields, models


class HrEmployee(models.Model):
    _inherit = 'hr.employee'

    distribution_route_ids = fields.One2many(
        'distribution.route.plan', 'employee_id', string='Route Plans')

    def _get_current_distribution_route(self):
        """The employee's route in progress today (empty recordset when
        none). Deliberately computed from employee + date + state at call
        time; never cached globally (spec #23)."""
        self.ensure_one()
        return self.env['distribution.route.plan'].search([
            ('employee_id', '=', self.id),
            ('state', '=', 'in_progress'),
            ('company_id', 'in', self.env.companies.ids),
        ], limit=1)
