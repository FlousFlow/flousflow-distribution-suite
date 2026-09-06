# -*- coding: utf-8 -*-
from odoo import _, api, fields, models
from odoo.exceptions import UserError


class PosConfig(models.Model):
    _inherit = 'pos.config'

    distribution_vehicle_id = fields.Many2one(
        'fleet.vehicle', string='Distribution Vehicle',
        index=True, check_company=True, ondelete='restrict', copy=False,
        domain="[('is_distribution_vehicle', '=', True), "
               "('distribution_active', '=', True)]",
        help="Vehicle this POS belongs to. Sales deduct from the vehicle "
             "warehouse and the POS order keeps a historical vehicle "
             "snapshot.")

    @api.constrains('distribution_vehicle_id', 'company_id')
    def _check_distribution_vehicle_company(self):
        for config in self:
            if config.distribution_vehicle_id and \
                    config.distribution_vehicle_id.company_id != \
                    config.company_id:
                raise UserError(_(
                    "The distribution vehicle '%(vehicle)s' does not belong "
                    "to the company of POS '%(pos)s'.",
                    vehicle=config.distribution_vehicle_id.name,
                    pos=config.name))
