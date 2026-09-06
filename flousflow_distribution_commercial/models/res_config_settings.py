# -*- coding: utf-8 -*-
from odoo import fields, models


class ResConfigSettings(models.TransientModel):
    _inherit = 'res.config.settings'

    allow_unallocated_customer_collection = fields.Boolean(
        related='company_id.allow_unallocated_customer_collection',
        readonly=False, string='Allow Unallocated Customer Collection')
    allow_collection_overpayment = fields.Boolean(
        related='company_id.allow_collection_overpayment',
        readonly=False, string='Allow Collection Overpayment')
    require_collection_attachment = fields.Boolean(
        related='company_id.require_collection_attachment',
        readonly=False, string='Require Collection Attachment')
    sales_visit_requires_commercial_record = fields.Boolean(
        related='company_id.sales_visit_requires_commercial_record',
        readonly=False, string='Sale Visits Require Commercial Record')
    collection_visit_requires_collection_record = fields.Boolean(
        related='company_id.collection_visit_requires_collection_record',
        readonly=False, string='Collection Visits Require Collection Record')
    commercial_validation_mode = fields.Selection(
        related='company_id.commercial_validation_mode',
        readonly=False, string='Commercial Validation Mode')
