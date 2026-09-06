# -*- coding: utf-8 -*-
"""Distribution smart buttons on the customer record (spec #60)."""
from odoo import fields, models


class ResPartner(models.Model):
    _inherit = 'res.partner'

    distribution_collection_count = fields.Integer(
        compute='_compute_distribution_commercial',
        string='Distribution Collections')
    distribution_route_sale_count = fields.Integer(
        compute='_compute_distribution_commercial',
        string='Distribution Sales')

    def _compute_distribution_commercial(self):
        for partner in self:
            partner.distribution_collection_count = self.env[
                'distribution.visit.collection'].search_count(
                    [('partner_id', 'in', partner.ids)])
            partner.distribution_route_sale_count = self.env['sale.order'] \
                .search_count([('distribution_visit_id.partner_id', 'in',
                                partner.ids)])

    def action_view_distribution_collections(self):
        self.ensure_one()
        return {
            'type': 'ir.actions.act_window',
            'name': _('Distribution Collections'),
            'res_model': 'distribution.visit.collection',
            'view_mode': 'list,form,pivot',
            'domain': [('partner_id', 'in', self.ids)],
            'context': {},
        }

    def action_view_distribution_sales(self):
        self.ensure_one()
        return {
            'type': 'ir.actions.act_window',
            'name': _('Distribution Sales'),
            'res_model': 'sale.order',
            'view_mode': 'list,form',
            'domain': [('distribution_visit_id.partner_id', 'in', self.ids)],
            'context': {},
        }
