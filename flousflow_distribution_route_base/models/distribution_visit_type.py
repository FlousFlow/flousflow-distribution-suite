from odoo import fields, models


class DistributionVisitType(models.Model):
    _name = 'distribution.visit.type'
    _description = 'Distribution Visit Type'
    _order = 'sequence, name, id'

    name = fields.Char(string='Name', required=True, index=True)
    code = fields.Char(string='Code', required=True, index=True)
    active = fields.Boolean(string='Active', default=True)
    sequence = fields.Integer(string='Sequence', default=10)
    company_id = fields.Many2one(
        'res.company',
        string='Company',
        required=True,
        default=lambda self: self.env.company,
        index=True,
    )
    description = fields.Text(string='Description')
    color = fields.Integer(string='Color Index', default=0)
    require_customer = fields.Boolean(
        string='Require Customer',
        default=True,
        help="Visits of this type must be linked to a customer.",
    )
    require_notes = fields.Boolean(
        string='Require Notes',
        help="Notes are mandatory when completing a visit of this type.",
    )
    allow_completion_without_customer = fields.Boolean(
        string='Allow Completion Without Customer',
        help="Allow completing this type of visit even if no customer is linked.",
    )
    icon = fields.Char(
        string='Icon',
        help="FontAwesome icon class, e.g. 'fa-money'. For display purposes only.",
    )

    _code_company_uniq = models.Constraint(
        'unique (code, company_id)',
        'The visit type code must be unique per company!',
    )
