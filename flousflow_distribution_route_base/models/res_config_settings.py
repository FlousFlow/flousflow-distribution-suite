from odoo import fields, models


class ResConfigSettings(models.TransientModel):
    _inherit = 'res.config.settings'

    distribution_default_area_id = fields.Many2one(
        related='company_id.distribution_default_area_id',
        readonly=False,
        string='Default Distribution Area',
    )
    allow_multi_area_employee = fields.Boolean(
        related='company_id.distribution_allow_multi_area_employee',
        readonly=False,
        string='Allow Multiple Areas per Employee',
    )
    require_distribution_area_on_customer = fields.Boolean(
        related='company_id.distribution_require_area_on_customer',
        readonly=False,
        string='Require Area on Customer',
    )
    require_distribution_area_on_distribution_employee = fields.Boolean(
        related='company_id.distribution_require_area_on_distribution_employee',
        readonly=False,
        string='Require Areas on Distribution Employees',
    )

