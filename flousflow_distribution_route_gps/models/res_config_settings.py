# -*- coding: utf-8 -*-
from odoo import fields, models


class ResConfigSettings(models.TransientModel):
    _inherit = 'res.config.settings'

    distribution_gps_enabled = fields.Boolean(
        string='Enable GPS Validation',
        config_parameter='distribution_gps.enabled',
        help="When disabled, the route management module keeps working "
             "exactly as before the GPS module was installed.",
    )
    distribution_default_geofence_radius = fields.Float(
        string='Default Geofence Radius (m)',
        config_parameter='distribution_gps.default_geofence_radius',
        help="Used when neither the customer nor the area defines a radius.",
    )
    distribution_geofence_mode = fields.Selection(
        selection=[
            ('disabled', 'Disabled'),
            ('warning', 'Warning Only'),
            ('strict', 'Strict Validation'),
        ],
        string='Geofence Validation Mode',
        config_parameter='distribution_gps.geofence_mode',
        help="Warning: allow visits outside the geofence but record it. "
             "Strict: block check-in outside the geofence (manager "
             "override possible with a reason).",
    )
    distribution_missing_customer_location_policy = fields.Selection(
        selection=[
            ('allow', 'Allow'),
            ('warn', 'Allow With Warning'),
            ('block', 'Block'),
        ],
        string='Missing Customer Location Policy',
        config_parameter='distribution_gps.missing_customer_location_policy',
        help="What to do when the customer has no stored GPS location.",
    )
    gps_maximum_accuracy = fields.Float(
        string='Maximum GPS Accuracy (m)',
        config_parameter='distribution_gps.maximum_accuracy',
        help="Positions less accurate than this value (in meters) are "
             "handled according to the GPS Accuracy Validation Mode.",
    )
    gps_accuracy_validation_mode = fields.Selection(
        selection=[
            ('disabled', 'Disabled'),
            ('warning', 'Warning Only'),
            ('strict', 'Strict Validation'),
        ],
        string='GPS Accuracy Validation Mode',
        config_parameter='distribution_gps.accuracy_validation_mode',
    )
    gps_max_position_age_seconds = fields.Integer(
        string='Maximum GPS Position Age (seconds)',
        config_parameter='distribution_gps.max_position_age_seconds',
        help="Positions older than this are rejected and must be "
             "re-captured.",
    )
    validate_checkout_geofence = fields.Boolean(
        string='Validate Check-Out Geofence',
        config_parameter='distribution_gps.validate_checkout_geofence',
        help="Apply geofence rules on check-out too. Disabled by default "
             "because representatives may finish the visit after moving "
             "away from the customer.",
    )
