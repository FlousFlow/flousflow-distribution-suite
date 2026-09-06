# -*- coding: utf-8 -*-
from odoo import _, api, fields, models


class ResPartner(models.Model):
    _inherit = 'res.partner'

    distribution_visit_count = fields.Integer(
        compute='_compute_distribution_visit_count',
        string='Distribution Visits',
    )

    def _compute_distribution_visit_count(self):
        Visit = self.env['distribution.route.visit']
        counts = dict(
            Visit._read_group(
                domain=[('partner_id', 'in', self.ids)],
                groupby=['partner_id'],
                aggregates=['__count'],
            )
        )
        for partner in self:
            partner.distribution_visit_count = counts.get(partner, 0)

    def action_view_distribution_visits(self):
        self.ensure_one()
        return {
            'type': 'ir.actions.act_window',
            'name': _('Distribution Visits'),
            'res_model': 'distribution.route.visit',
            'view_mode': 'list,form,calendar,kanban',
            'domain': [('partner_id', '=', self.id)],
            'context': {'default_partner_id': self.id},
        }
