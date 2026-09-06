# -*- coding: utf-8 -*-
from odoo import fields, models


class DistributionVisitType(models.Model):
    _inherit = 'distribution.visit.type'

    require_gps_checkin = fields.Boolean(
        string='Require GPS Check-In', default=True,
        help="Capture and validate GPS on visit check-in. Disable for "
             "visit types that do not happen at the customer location "
             "(e.g. internal tasks).",
    )
    require_gps_checkout = fields.Boolean(
        string='Require GPS Check-Out', default=False,
        help="Capture and validate GPS on visit check-out.",
    )
