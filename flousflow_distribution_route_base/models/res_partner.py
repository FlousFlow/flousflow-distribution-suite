from odoo import _, api, fields, models
from odoo.exceptions import ValidationError


class ResPartner(models.Model):
    _inherit = 'res.partner'

    distribution_area_id = fields.Many2one(
        'distribution.area',
        string='Distribution Area',
        index='btree_not_null',
        check_company=True,
        copy=False,
        help="Distribution area of this contact.",
    )

    def _check_required_distribution_area_setting(self):
        """Enforce the 'Require Area on Customer' company setting when set.

        Only applies when the customer_rank field exists (provided by the
        sale stack), so the module stays fully functional standalone.
        """
        if 'customer_rank' not in self._fields:
            return
        missing = self.filtered(
            lambda p: p.company_id
            and p.company_id.distribution_require_area_on_customer
            and p.customer_rank > 0
            and not p.distribution_area_id
        )
        if missing:
            raise ValidationError(_(
                "A distribution area is required on customers "
                "(see Distribution settings). Please set the distribution "
                "area on: %(partners)s",
                partners=", ".join(missing.mapped('display_name')[:5]),
            ))

    @api.model_create_multi
    def create(self, vals_list):
        partners = super().create(vals_list)
        partners._check_required_distribution_area_setting()
        return partners

    def write(self, vals):
        res = super().write(vals)
        if 'distribution_area_id' in vals or 'customer_rank' in vals:
            self._check_required_distribution_area_setting()
        return res

    @api.model
    def default_get(self, fields_list):
        """Propose the company default distribution area on new records."""
        res = super().default_get(fields_list)
        if 'distribution_area_id' in fields_list and not res.get('distribution_area_id'):
            area = self.env.company.distribution_default_area_id
            if area and area.company_id in self.env.companies:
                res['distribution_area_id'] = area.id
        return res
