# -*- coding: utf-8 -*-
"""Partner location sync — bridges flousflow_partner_location (Google Maps
link + device capture widget) with the distribution geofence fields, so a
location captured once feeds both systems:
  * partner_latitude/longitude (location link widget)  →  distribution_* fields
  * device GPS capture (route_gps client action)       →  partner_latitude/longitude
Also enables the Google-Maps-link widget on the Distribution GPS page so the
salesman can capture location from a pasted WhatsApp/Maps link."""
from odoo import api, fields, models


class ResPartner(models.Model):
    _inherit = 'res.partner'

    def _location_sync_both_present(self, vals):
        """Did this write touch one of the two location systems?"""
        return bool({'distribution_latitude', 'distribution_longitude'} & set(vals)
                    or {'partner_latitude', 'partner_longitude'} & set(vals))

    @api.model_create_multi
    def create(self, vals_list):
        partners = super().create(vals_list)
        partners._sync_both_location_systems(vals_list)
        return partners

    def write(self, vals):
        res = super().write(vals)
        self._sync_both_location_systems(vals)
        return res

    def _sync_both_location_systems(self, vals_list=None):
        """Keep the two location systems aligned:
        - A device GPS capture (route_gps) mirrors into partner_latitude/
          partner_longitude so the 'Customer Location' page + map buttons work.
        - A Google-Maps link extract mirrors into distribution_* so the
          geofence validates against it.
        Skips empty values and prevents recursion via context flag."""
        if self.env.context.get('location_sync_running'):
            return
        for partner, vals in zip(self, vals_list or [{}] * len(self)):
            sync_vals = {}
            if 'partner_latitude' in vals and 'partner_longitude' in vals:
                if vals.get('partner_latitude') and vals.get('partner_longitude'):
                    sync_vals['distribution_latitude'] = vals['partner_latitude']
                    sync_vals['distribution_longitude'] = vals['partner_longitude']
            if 'distribution_latitude' in vals and 'distribution_longitude' in vals:
                if vals.get('distribution_latitude') and vals.get('distribution_longitude'):
                    sync_vals['partner_latitude'] = vals['distribution_latitude']
                    sync_vals['partner_longitude'] = vals['distribution_longitude']
            if not sync_vals:
                continue
            # Mirror as system: capture flows are already permission-gated by
            # their buttons (device capture / link extract) and fully audited
            # in distribution.visit.gps.event. A plain mirror write must not
            # require extra partner rights from the field salesman.
            partner.sudo().with_context(
                location_sync_running=True).write(sync_vals)


class ResPartnerLocationLink(models.Model):
    """Extend the Google-Maps link flow to also feed the distribution
    geofence fields (single source of truth for the geofence)."""
    _inherit = 'res.partner'

    def action_extract_location(self):
        res = super().action_extract_location()
        # copy the extracted coordinates into the distribution geofence fields
        if self.partner_latitude and self.partner_longitude:
            self.write({
                'distribution_latitude': self.partner_latitude,
                'distribution_longitude': self.partner_longitude,
                'distribution_location_source': 'imported',
            })
        return res

    def gps_save_customer_location(self, latitude, longitude, accuracy=0.0,
                                   gps_timestamp=None, source='device_gps'):
        """Device GPS capture also mirrors into the standard partner
        location fields so the 'Customer Location' page stays current."""
        res = super().gps_save_customer_location(
            latitude, longitude, accuracy=accuracy,
            gps_timestamp=gps_timestamp, source=source)
        if self.partner_latitude != float(latitude) or \
                self.partner_longitude != float(longitude):
            self.sudo().with_context(location_sync_running=True).write({
                'partner_latitude': float(latitude),
                'partner_longitude': float(longitude),
            })
        return res
