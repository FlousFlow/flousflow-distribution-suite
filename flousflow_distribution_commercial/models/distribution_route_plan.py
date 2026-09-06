# -*- coding: utf-8 -*-
"""Commercial metrics on the Route Plan — aggregated from the visits'
commercial links (spec #8/#59). Visits per route are few (~20), so direct
aggregation over the o2m stays linear — no N+1 against the database."""
from odoo import fields, models


class DistributionRoutePlan(models.Model):
    _inherit = 'distribution.route.plan'

    quotation_count = fields.Integer(
        compute='_compute_commercial', string='Quotations')
    sale_order_count = fields.Integer(
        compute='_compute_commercial', string='Sale Orders')
    pos_order_count = fields.Integer(
        compute='_compute_commercial', string='POS Orders')
    collection_count = fields.Integer(
        compute='_compute_commercial', string='Collections')

    quotation_amount = fields.Monetary(
        compute='_compute_commercial', string='Quotation Amount',
        currency_field='company_currency_id')
    sale_order_amount = fields.Monetary(
        compute='_compute_commercial', string='Confirmed Sales Amount',
        currency_field='company_currency_id')
    pos_sales_amount = fields.Monetary(
        compute='_compute_commercial', string='POS Sales Amount',
        currency_field='company_currency_id')
    submitted_collection_amount = fields.Monetary(
        compute='_compute_commercial', string='Submitted Collections',
        currency_field='company_currency_id')
    validated_collection_amount = fields.Monetary(
        compute='_compute_commercial', string='Validated Collections',
        currency_field='company_currency_id')

    company_currency_id = fields.Many2one(
        related='company_id.currency_id', string='Company Currency')

    def _compute_commercial(self):
        for plan in self:
            quotations = plan.visit_ids.sale_order_ids.filtered(
                lambda s: s.state in ('draft', 'sent'))
            confirmed = plan.visit_ids.sale_order_ids.filtered(
                lambda s: s.state == 'sale')
            pos_orders = plan.visit_ids.pos_order_ids.filtered(
                lambda o: o.state != 'cancel')
            collections = plan.visit_ids.collection_ids
            plan.quotation_count = len(quotations)
            plan.sale_order_count = len(
                plan.visit_ids.sale_order_ids.filtered(
                    lambda s: s.state == 'sale'))
            plan.pos_order_count = len(pos_orders)
            plan.collection_count = len(collections)
            plan.quotation_amount = sum(quotations.mapped('amount_total'))
            plan.sale_order_amount = sum(confirmed.mapped('amount_total'))
            plan.pos_sales_amount = sum(pos_orders.mapped('amount_total'))
            plan.submitted_collection_amount = sum(
                collections.filtered(
                    lambda c: c.state == 'submitted').mapped('amount'))
            plan.validated_collection_amount = sum(
                collections.filtered(
                    lambda c: c.state == 'validated').mapped('amount'))
