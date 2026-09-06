# -*- coding: utf-8 -*-
from odoo import _, api, fields, models
from odoo.exceptions import ValidationError


class FleetVehicleEmployeeAssignment(models.Model):
    _name = 'fleet.vehicle.employee.assignment'
    _description = 'Fleet Vehicle Employee Assignment'
    _order = 'date_from desc, id desc'
    _rec_name = 'employee_id'
    _check_company_auto = True

    vehicle_id = fields.Many2one(
        'fleet.vehicle', string='Vehicle', required=True, index=True,
        check_company=True, ondelete='cascade',
        domain="[('is_distribution_vehicle', '=', True)]")
    employee_id = fields.Many2one(
        'hr.employee', string='Employee', required=True, index=True,
        check_company=True, ondelete='restrict')
    role = fields.Selection(
        selection=[
            ('driver', 'Driver'),
            ('sales_rep', 'Sales Representative'),
            ('helper', 'Helper'),
            ('supervisor', 'Supervisor'),
            ('other', 'Other'),
        ],
        string='Role', required=True, default='sales_rep', index=True)
    date_from = fields.Date(string='From', required=True,
                            default=fields.Date.context_today)
    date_to = fields.Date(string='To',
                          help="Empty = current assignment.")
    company_id = fields.Many2one(
        'res.company', string='Company', required=True,
        default=lambda self: self.env.company, index=True)
    notes = fields.Text(string='Notes')

    @api.depends('date_to')
    def _compute_display_name(self):
        for assignment in self:
            assignment.display_name = _(
                "%(employee)s — %(vehicle)s (%(role)s)",
                employee=assignment.employee_id.name or '',
                vehicle=assignment.vehicle_id.name or '',
                role=assignment.role or '',
            )

    _date_to_check = models.Constraint(
        'CHECK (date_to IS NULL OR date_to >= date_from)',
        'The assignment end date cannot be before its start date.',
    )

    # ------------------------------------------------------------------
    @api.constrains('employee_id', 'date_from', 'date_to', 'vehicle_id')
    def _check_overlapping_assignments(self):
        """An employee can hold only one open assignment across active
        distribution vehicles (close the previous one first)."""
        for assignment in self.filtered(lambda a: not a.date_to):
            others = self.env['fleet.vehicle.employee.assignment'].search([
                ('id', '!=', assignment.id),
                ('employee_id', '=', assignment.employee_id.id),
                ('date_to', '=', False),
                ('vehicle_id.is_distribution_vehicle', '=', True),
                ('vehicle_id.distribution_active', '=', True),
            ])
            conflicting = others.filtered(
                lambda a: a.vehicle_id != assignment.vehicle_id)
            if conflicting:
                raise ValidationError(_(
                    "Employee '%(employee)s' already has an open assignment "
                    "on vehicle '%(vehicle)s'. Close that assignment first "
                    "before assigning them to '%(new_vehicle)s'.",
                    employee=assignment.employee_id.name,
                    vehicle=conflicting[0].vehicle_id.name,
                    new_vehicle=assignment.vehicle_id.name))

    @api.constrains('vehicle_id', 'employee_id', 'company_id')
    def _check_assignment_company(self):
        for assignment in self:
            if assignment.vehicle_id.company_id != assignment.company_id:
                raise ValidationError(_(
                    "The assignment company must match the vehicle "
                    "company."))
            employee_company = assignment.employee_id.company_id
            if employee_company and employee_company != assignment.company_id:
                raise ValidationError(_(
                    "The employee '%(employee)s' does not belong to the "
                    "company of vehicle '%(vehicle)s'.",
                    employee=assignment.employee_id.name,
                    vehicle=assignment.vehicle_id.name))

    def action_close(self):
        """Close the current assignment as of today."""
        for assignment in self.filtered(lambda a: not a.date_to):
            assignment.date_to = fields.Date.context_today(assignment)
        return True
