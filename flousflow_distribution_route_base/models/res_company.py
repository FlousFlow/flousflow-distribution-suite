from odoo import fields, models


class ResCompany(models.Model):
    _inherit = 'res.company'

    distribution_default_area_id = fields.Many2one(
        'distribution.area',
        string='Default Distribution Area',
        check_company=True,
        help="Distribution area proposed by default on new customer records.",
    )
    distribution_allow_multi_area_employee = fields.Boolean(
        string='Allow Multiple Areas per Employee',
        default=True,
        help="Allow an employee to operate in more than one distribution area.",
    )
    distribution_require_area_on_customer = fields.Boolean(
        string='Require Area on Customer',
        help="Block saving customers without a distribution area.",
    )
    distribution_require_area_on_distribution_employee = fields.Boolean(
        string='Require Areas on Distribution Employees',
        help="Block saving distribution employees without at least one area.",
    )
