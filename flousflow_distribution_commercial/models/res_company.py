# -*- coding: utf-8 -*-
"""Company commercial settings + employee collections button."""
from odoo import fields, models


class ResCompany(models.Model):
    _inherit = 'res.company'

    allow_unallocated_customer_collection = fields.Boolean(
        string='Allow Unallocated Customer Collection', default=True,
        help="Allow customer collections without selecting specific "
             "invoices. The payment remains available customer credit "
             "per standard Odoo accounting.")
    allow_collection_overpayment = fields.Boolean(
        string='Allow Collection Overpayment', default=False,
        help="Allow collections larger than the outstanding balance of "
             "the selected invoices. The excess remains customer credit.")
    require_collection_attachment = fields.Boolean(
        string='Require Collection Attachment', default=False,
        help="Require at least one attachment (receipt, transfer proof) "
             "before a collection can be submitted.")
    sales_visit_requires_commercial_record = fields.Boolean(
        string='Sale Visits Require Commercial Record', default=False)
    collection_visit_requires_collection_record = fields.Boolean(
        string='Collection Visits Require Collection Record', default=False)
    commercial_validation_mode = fields.Selection(
        selection=[
            ('disabled', 'Disabled'),
            ('warning', 'Warning'),
            ('strict', 'Strict'),
        ],
        string='Commercial Validation Mode', default='disabled',
        help="Controls visit completion when the visit type expects a "
             "commercial action: disabled = no check, warning = log a "
             "note and complete, strict = block completion. An "
             "unsuccessful business result (customer refused) always "
             "completes.")
