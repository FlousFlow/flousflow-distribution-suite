# -*- coding: utf-8 -*-
from odoo import fields, models


class DistributionVisitType(models.Model):
    _inherit = 'distribution.visit.type'

    commercial_action_type = fields.Selection(
        selection=[
            ('none', 'None'),
            ('sale', 'Sale'),
            ('pos_sale', 'POS Sale'),
            ('collection', 'Collection'),
            ('sale_and_collection', 'Sale and Collection'),
        ],
        string='Commercial Action', default='none',
        help="Commercial activity expected during this kind of visit. "
             "Used by the commercial validation policy (disabled / warning "
             "/ strict). An unsuccessful business result always completes "
             "the visit without a commercial record.")
