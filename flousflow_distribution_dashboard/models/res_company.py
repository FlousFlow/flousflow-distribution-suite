# -*- coding: utf-8 -*-
from odoo import fields, models


class ResCompany(models.Model):
    _inherit = 'res.company'

    distribution_dashboard_default_period = fields.Selection(
        selection=[
            ('today', 'Today'),
            ('yesterday', 'Yesterday'),
            ('this_week', 'This Week'),
            ('last_week', 'Last Week'),
            ('this_month', 'This Month'),
            ('last_month', 'Last Month'),
        ],
        string='Dashboard Default Period',
        default='today',
        help="Period selected when the distribution dashboard opens.")
    distribution_dashboard_minimum_visits_for_ranking = fields.Integer(
        string='Minimum Visits for Ranking',
        default=10,
        help="Employees with fewer executed visits than this are excluded "
             "from rankings (a 1/1 = 100% must not beat a 95/100 = 95%).")
    distribution_dashboard_visit_delay_alert_minutes = fields.Integer(
        string='Visit Delay Alert (minutes)',
        default=30,
        help="A visit not executed whose planned time is older than this "
             "appears in Needs Attention.")
    distribution_dashboard_route_start_delay_minutes = fields.Integer(
        string='Route Start Delay Alert (minutes)',
        default=15,
        help="A route not started whose planned start is older than this "
             "appears in Needs Attention.")
    distribution_dashboard_low_execution_percentage = fields.Float(
        string='Low Route Execution Alert (%)',
        default=50.0,
        help="Routes below this execution rate appear in Needs Attention. "
             "In-progress routes are only flagged after 15:00 so a morning "
             "route is never an alert.")
