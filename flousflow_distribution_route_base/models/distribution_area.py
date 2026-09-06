from odoo import _, api, fields, models
from odoo.exceptions import ValidationError


class DistributionArea(models.Model):
    _name = 'distribution.area'
    _description = 'Distribution Area'
    _order = 'sequence, name, id'
    _check_company_auto = True

    name = fields.Char(string='Name', required=True, index=True)
    code = fields.Char(string='Code', index=True, help="Optional short unique code for this area.")
    active = fields.Boolean(string='Active', default=True)
    parent_id = fields.Many2one(
        'distribution.area',
        string='Parent Area',
        index=True,
        check_company=True,
        ondelete='restrict',
    )
    child_ids = fields.One2many(
        'distribution.area',
        'parent_id',
        string='Child Areas',
        check_company=True,
    )
    manager_id = fields.Many2one(
        'res.users',
        string='Area Manager',
        check_company=True,
    )
    employee_ids = fields.Many2many(
        'hr.employee',
        'distribution_area_hr_employee_rel',
        'area_id',
        'employee_id',
        string='Employees',
        check_company=True,
    )
    company_id = fields.Many2one(
        'res.company',
        string='Company',
        required=True,
        default=lambda self: self.env.company,
        index=True,
    )
    sequence = fields.Integer(string='Sequence', default=10)
    description = fields.Text(string='Description')
    color = fields.Integer(string='Color Index', default=0)

    _code_company_uniq = models.Constraint(
        'unique (code, company_id)',
        'The area code must be unique per company!',
    )

    @api.constrains('parent_id')
    def _check_parent_hierarchy(self):
        """Prevent self-parenting and circular hierarchies (A -> B -> C -> A)."""
        for area in self:
            if not area._check_recursion():
                raise ValidationError(_(
                    "You cannot create a recursive hierarchy of distribution areas.\n"
                    "The area '%(area)s' cannot be its own parent or an ancestor of itself.",
                    area=area.display_name,
                ))

    @api.constrains('employee_ids')
    def _check_employee_company(self):
        for area in self:
            mismatched = area.employee_ids.filtered(
                lambda e: e.company_id != area.company_id
            )
            if mismatched:
                raise ValidationError(_(
                    "The employee '%(employee)s' does not belong to the company of the "
                    "distribution area '%(area)s'.",
                    employee=mismatched[0].name,
                    area=area.display_name,
                ))
