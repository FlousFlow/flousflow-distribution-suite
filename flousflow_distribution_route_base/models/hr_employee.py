# -*- coding: utf-8 -*-
from odoo import _, api, fields, models
from odoo.exceptions import ValidationError


class HrEmployeePublic(models.Model):
    """Mirror distribution fields on the public employee profile so that
    non-HR users (e.g. distribution representatives and managers) can read
    them. Without this, these fields are treated as private and raise an
    AccessError when read by non-HR users (Odoo 19 behaviour).

    They are declared as non-stored related fields on purpose: the
    hr.employee.public SQL view is rebuilt when the hr module loads, which
    on a fresh install happens BEFORE this module's hr_employee columns
    exist. Related fields keep the private-fields check happy without
    adding columns to the view.
    """
    _inherit = 'hr.employee.public'

    is_distribution_employee = fields.Boolean(
        related='employee_id.is_distribution_employee',
        string='Distribution Employee',
        readonly=True,
    )
    distribution_area_ids = fields.Many2many(
        related='employee_id.distribution_area_ids',
        string='Distribution Areas',
        readonly=True,
    )
    distribution_supervisor_id = fields.Many2one(
        related='employee_id.distribution_supervisor_id',
        string='Distribution Supervisor',
        readonly=True,
    )
    distribution_active = fields.Boolean(
        related='employee_id.distribution_active',
        string='Distribution Active',
        readonly=True,
    )


class HrEmployee(models.Model):
    _inherit = 'hr.employee'

    is_distribution_employee = fields.Boolean(
        string='Distribution Employee',
        help="This employee works in distribution (e.g. sales representative).",
    )
    distribution_area_ids = fields.Many2many(
        'distribution.area',
        'distribution_area_hr_employee_rel',
        'employee_id',
        'area_id',
        string='Distribution Areas',
        check_company=True,
        copy=False,
        help="Distribution areas in which this employee may operate.",
    )
    distribution_supervisor_id = fields.Many2one(
        'hr.employee',
        string='Distribution Supervisor',
        check_company=True,
        copy=False,
        domain="[('id', '!=', id)]",
    )
    distribution_active = fields.Boolean(
        string='Distribution Active',
        default=True,
        help="Whether this employee is currently active in distribution operations.",
    )

    @api.constrains('distribution_area_ids')
    def _check_distribution_area_company(self):
        for employee in self:
            mismatched = employee.distribution_area_ids.filtered(
                lambda a: a.company_id != employee.company_id
            )
            if mismatched:
                raise ValidationError(_(
                    "The distribution area '%(area)s' does not belong to the company of "
                    "the employee '%(employee)s'.",
                    area=mismatched[0].display_name,
                    employee=employee.name,
                ))

    @api.constrains('is_distribution_employee', 'distribution_area_ids')
    def _check_distribution_settings(self):
        """Enforce the 'allow_multi_area_employee' and
        'require_area_on_distribution_employee' company settings."""
        for employee in self:
            company = employee.company_id
            if not company:
                continue
            if (
                not company.distribution_allow_multi_area_employee
                and len(employee.distribution_area_ids) > 1
            ):
                raise ValidationError(_(
                    "Only one distribution area is allowed per employee "
                    "(see Distribution settings)."
                ))
            if (
                company.distribution_require_area_on_distribution_employee
                and employee.is_distribution_employee
                and not employee.distribution_area_ids
            ):
                raise ValidationError(_(
                    "At least one distribution area is required for the "
                    "distribution employee '%(employee)s' (see Distribution settings).",
                    employee=employee.name,
                ))
