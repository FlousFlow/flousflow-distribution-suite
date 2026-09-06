# -*- coding: utf-8 -*-
"""POS Order ↔ Distribution Visit integration.

The visit sets a context on the vehicle POS config (integer raw id); the
POS frontend carries it on every new order (patch in
static/src/js/pos_visit_patch.js) and the metadata rides the order
payload — so it survives OFFLINE order creation and sync (spec #22).
The backend then links the order explicitly: route and employee are
derived from the visit — never guessed from customer or timestamp
(spec #15/#21)."""
from odoo import api, fields, models


class PosOrder(models.Model):
    _inherit = 'pos.order'

    distribution_route_id = fields.Many2one(
        'distribution.route.plan', string='Distribution Route',
        index=True, readonly=True, copy=False,
        help="Route the visit belonged to (historical snapshot).")
    distribution_visit_id = fields.Many2one(
        'distribution.route.visit', string='Distribution Visit',
        index=True, readonly=True, copy=False,
        help="Visit this POS order was created from (explicit link).")
    distribution_employee_id = fields.Many2one(
        'hr.employee', string='Distribution Employee', index=True,
        readonly=True, copy=False)

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            visit_id = vals.get('distribution_visit_id')
            if not visit_id:
                continue
            visit = self.env['distribution.route.visit'].browse(visit_id)
            vals['distribution_route_id'] = visit.route_id.id
            vals['distribution_employee_id'] = visit.employee_id.id
            # Customer consistency (#20): a different customer means the
            # visit link is dropped — the order still syncs normally.
            if vals.get('partner_id') and \
                    vals['partner_id'] != visit.partner_id.id:
                vals.update({
                    'distribution_visit_id': False,
                    'distribution_route_id': False,
                    'distribution_employee_id': False,
                })
        return super().create(vals_list)
