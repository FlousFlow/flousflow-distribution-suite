# -*- coding: utf-8 -*-
from odoo import _, api, fields, models
from odoo.exceptions import UserError

from . import gps_math


class ResPartner(models.Model):
    _inherit = 'res.partner'

    # -- Customer GPS location ------------------------------------------
    distribution_latitude = fields.Float(
        string='Latitude', digits=(16, 7), copy=False,
        help="Customer latitude in decimal degrees (WGS84).",
    )
    distribution_longitude = fields.Float(
        string='Longitude', digits=(16, 7), copy=False,
        help="Customer longitude in decimal degrees (WGS84).",
    )
    # Internal flag: distinguishes "coordinates never set" from a genuine
    # (0, 0) coordinate, which is a valid point on Earth.
    distribution_location_set = fields.Boolean(default=False, copy=False)
    distribution_location_accuracy = fields.Float(
        string='Location Accuracy (m)', digits=(16, 2), copy=False,
        help="GPS accuracy of the stored location, in meters.",
    )
    distribution_location_date = fields.Datetime(
        string='Location Last Updated', readonly=True, copy=False)
    distribution_location_user_id = fields.Many2one(
        'res.users', string='Location Captured By',
        readonly=True, copy=False)
    distribution_location_source = fields.Selection(
        selection=[
            ('manual', 'Manual'),
            ('device_gps', 'Device GPS'),
            ('imported', 'Imported'),
            ('other', 'Other'),
        ],
        string='Location Source', copy=False,
        help="How the stored location was captured.",
    )
    distribution_geofence_radius = fields.Float(
        string='Geofence Radius (m)', digits=(16, 2), copy=False,
        help="Allowed distance from this customer for geofence validation, "
             "in meters. Leave empty to use the area or global default.",
    )
    has_distribution_location = fields.Boolean(
        compute='_compute_has_distribution_location',
        string='Has GPS Location',
        help="True when valid coordinates are stored for this customer.",
    )

    _distribution_latitude_check = models.Constraint(
        'CHECK (distribution_latitude IS NULL OR '
        '(distribution_latitude >= -90 AND distribution_latitude <= 90))',
        'Latitude must be between -90 and 90 degrees.',
    )
    _distribution_longitude_check = models.Constraint(
        'CHECK (distribution_longitude IS NULL OR '
        '(distribution_longitude >= -180 AND distribution_longitude <= 180))',
        'Longitude must be between -180 and 180 degrees.',
    )
    _distribution_accuracy_check = models.Constraint(
        'CHECK (distribution_location_accuracy IS NULL OR '
        'distribution_location_accuracy >= 0)',
        'GPS accuracy cannot be negative.',
    )
    # 0 is allowed and means "inherit from area / global default", matching
    # _get_effective_geofence_radius() fallback logic. Only negatives are
    # invalid — a Float field on a form is written as 0.0 when left empty.
    _distribution_geofence_radius_check = models.Constraint(
        'CHECK (distribution_geofence_radius IS NULL OR '
        'distribution_geofence_radius >= 0)',
        'The geofence radius must be greater than zero.',
    )

    @api.depends('distribution_location_set',
                 'distribution_latitude', 'distribution_longitude')
    def _compute_has_distribution_location(self):
        for partner in self:
            partner.has_distribution_location = bool(
                partner.distribution_location_set
                and gps_math.is_valid_latitude(partner.distribution_latitude)
                and gps_math.is_valid_longitude(partner.distribution_longitude)
            )

    def _sync_location_set_flag(self, vals):
        """Maintain distribution_location_set from explicit lat/lon writes.

        Any explicit write of both coordinates marks the location as set,
        even if the values are 0/0 (a valid point on Earth). Writing False
        to either coordinate clears the flag.
        """
        lat_in = 'distribution_latitude' in vals
        lon_in = 'distribution_longitude' in vals
        if not (lat_in or lon_in):
            return
        lat = vals.get('distribution_latitude', self.distribution_latitude)
        lon = vals.get('distribution_longitude', self.distribution_longitude)
        if lat is False or lon is False:
            vals['distribution_location_set'] = False
        elif lat_in and lon_in:
            vals['distribution_location_set'] = True

    def _clear_location_metadata(self, vals):
        if vals.get('distribution_location_set') is False:
            vals.setdefault('distribution_location_accuracy', 0.0)
            vals.setdefault('distribution_location_date', False)
            vals.setdefault('distribution_location_user_id', False)
            vals.setdefault('distribution_location_source', False)

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            self._sync_location_set_flag(vals)
            self._clear_location_metadata(vals)
            self._stamp_manual_location(vals)
        return super().create(vals_list)

    def write(self, vals):
        for partner in self:
            partner._sync_location_set_flag(vals)
        self._clear_location_metadata(vals)
        self._stamp_manual_location(vals)
        return super().write(vals)

    def _stamp_manual_location(self, vals):
        """Coordinates entered by hand (not via the GPS capture flow) are
        always stamped as source='manual' with author and time."""
        coords_written = ('distribution_latitude' in vals
                          or 'distribution_longitude' in vals)
        if not coords_written or 'distribution_location_source' in vals:
            return
        if self.env.context.get('gps_device_capture'):
            return
        if vals.get('distribution_latitude') is False \
                or vals.get('distribution_longitude') is False:
            return
        vals['distribution_location_source'] = 'manual'
        vals['distribution_location_date'] = fields.Datetime.now()
        vals['distribution_location_user_id'] = self.env.user.id

    # ------------------------------------------------------------------
    # Capture / helpers
    # ------------------------------------------------------------------
    def action_capture_gps_location(self):
        """Open the browser GPS capture client action."""
        self.ensure_one()
        return {
            'type': 'ir.actions.client',
            'tag': 'distribution_gps.capture_location',
            'params': {'partner_id': self.id},
        }

    def gps_save_customer_location(self, latitude, longitude, accuracy=0.0,
                                   gps_timestamp=None, source='device_gps'):
        """Save a captured location (called from the GPS client action)."""
        self.ensure_one()
        if not gps_math.is_valid_latitude(latitude) or \
                not gps_math.is_valid_longitude(longitude):
            raise UserError(_(
                "Invalid coordinates received. Latitude must be between "
                "-90 and 90 and longitude between -180 and 180."))
        if not gps_math.is_valid_accuracy(accuracy):
            raise UserError(_("Invalid GPS accuracy received."))
        # sudo: distribution representatives capture the customer location
        # from their device; they have no direct res.partner write access.
        # The operation itself is gated by the capture button (distribution
        # groups) and fully audited below.
        self.sudo().with_context(gps_device_capture=True).write({
            'distribution_latitude': float(latitude),
            'distribution_longitude': float(longitude),
            'distribution_location_accuracy': float(accuracy or 0.0),
            'distribution_location_date': fields.Datetime.now(),
            'distribution_location_user_id': self.env.user.id,
            'distribution_location_source': source,
        })
        # Audit: customer location captures are recorded like visit GPS
        # events (sudo: the event log is business-logic-only).
        self.env['distribution.visit.gps.event'].sudo().create({
            'partner_id': self.id,
            'event_type': 'customer_location_capture',
            'latitude': float(latitude),
            'longitude': float(longitude),
            'accuracy': float(accuracy or 0.0),
            'user_id': self.env.user.id,
            'server_datetime': fields.Datetime.now(),
            'gps_timestamp': float(gps_timestamp) if gps_timestamp else False,
        })
        return True

    def action_open_location(self):
        """Open the stored coordinates on a public map (OpenStreetMap)."""
        self.ensure_one()
        if not self.has_distribution_location:
            raise UserError(_("This customer has no stored GPS location."))
        lat = self.distribution_latitude
        lon = self.distribution_longitude
        url = (
            "https://www.openstreetmap.org/?mlat=%(lat)s&mlon=%(lon)s"
            "#map=17/%(lat)s/%(lon)s" % {'lat': lat, 'lon': lon}
        )
        return {
            'type': 'ir.actions.act_url',
            'url': url,
            'target': 'new',
        }
