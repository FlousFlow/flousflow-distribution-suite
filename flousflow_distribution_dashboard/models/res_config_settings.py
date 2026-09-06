# -*- coding: utf-8 -*-
from odoo import fields, models


class ResConfigSettings(models.TransientModel):
    _inherit = 'res.config.settings'

    distribution_dashboard_default_period = fields.Selection(
        related='company_id.distribution_dashboard_default_period',
        readonly=False,
        string='Dashboard Default Period',
    )
    distribution_dashboard_minimum_visits_for_ranking = fields.Integer(
        related='company_id.distribution_dashboard_minimum_visits_for_ranking',
        readonly=False,
        string='Minimum Visits for Ranking',
    )
    distribution_dashboard_visit_delay_alert_minutes = fields.Integer(
        related='company_id.distribution_dashboard_visit_delay_alert_minutes',
        readonly=False,
        string='Visit Delay Alert (minutes)',
    )
    distribution_dashboard_route_start_delay_minutes = fields.Integer(
        related='company_id.distribution_dashboard_route_start_delay_minutes',
        readonly=False,
        string='Route Start Delay Alert (minutes)',
    )
    distribution_dashboard_low_execution_percentage = fields.Float(
        related='company_id.distribution_dashboard_low_execution_percentage',
        readonly=False,
        string='Low Route Execution Alert (%)',
    )
