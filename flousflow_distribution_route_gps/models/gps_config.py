# -*- coding: utf-8 -*-
"""Shared GPS configuration helpers (ir.config_parameter based)."""
from odoo import api, models

PARAM_PREFIX = 'distribution_gps.'


class GpsConfig(models.AbstractModel):
    """Central typed access to the GPS configuration parameters.

    Values are global (ir.config_parameter) per the module specification.
    """
    _name = 'distribution.gps.config'
    _description = 'Distribution GPS Configuration Helper'

    @api.model
    def get_params(self):
        icp = self.env['ir.config_parameter'].sudo()

        def f(key, default):
            # Odoo 19: get_param returns False (not None) when missing.
            value = icp.get_param(PARAM_PREFIX + key)
            if value in (None, False, ''):
                return default
            try:
                return float(value)
            except (TypeError, ValueError):
                return default

        def i(key, default):
            value = icp.get_param(PARAM_PREFIX + key)
            if value in (None, False, ''):
                return default
            try:
                return int(float(value))
            except (TypeError, ValueError):
                return default

        def b(key, default):
            value = icp.get_param(PARAM_PREFIX + key)
            if value in (None, False, ''):
                return default
            return str(value).lower() in ('1', 'true', 'yes')
        return {
            'enabled': b('enabled', True),
            'geofence_mode': icp.get_param(
                PARAM_PREFIX + 'geofence_mode', 'warning'),
            'missing_customer_location_policy': icp.get_param(
                PARAM_PREFIX + 'missing_customer_location_policy', 'warn'),
            'default_geofence_radius': f('default_geofence_radius', 100.0),
            'maximum_accuracy': f('maximum_accuracy', 100.0),
            'accuracy_validation_mode': icp.get_param(
                PARAM_PREFIX + 'accuracy_validation_mode', 'warning'),
            'max_position_age_seconds': i('max_position_age_seconds', 30),
            'validate_checkout_geofence': b('validate_checkout_geofence', False),
        }
