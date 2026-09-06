# -*- coding: utf-8 -*-
from odoo import _, api, fields, models
from odoo.exceptions import UserError, ValidationError

from . import gps_math

GROUP_MANAGER = 'flousflow_distribution_route_base.group_distribution_route_manager'

# Fields written only by the GPS business logic.
VISIT_GPS_FIELDS = {
    'checkin_latitude', 'checkin_longitude', 'checkin_accuracy',
    'checkin_datetime', 'checkin_distance', 'checkin_geofence_status',
    'checkout_latitude', 'checkout_longitude', 'checkout_accuracy',
    'checkout_datetime', 'checkout_distance', 'checkout_geofence_status',
    'customer_latitude_snapshot', 'customer_longitude_snapshot',
    'customer_geofence_radius_snapshot',
    'override_user_id', 'override_datetime', 'override_reason',
    'override_operation',
}

GEOFENCE_MESSAGES = {
    'checkin': _(
        "You are %(distance).0f m away from the customer location, while "
        "the allowed radius is %(radius).0f m. Check-in is not allowed."),
    'checkout': _(
        "You are %(distance).0f m away from the customer location, while "
        "the allowed radius is %(radius).0f m. Check-out is not allowed."),
}


class DistributionRouteVisit(models.Model):
    _inherit = 'distribution.route.visit'

    def _valid_field_parameter(self, field, name):
        return name in ('aggregate',) or \
            super()._valid_field_parameter(field, name)

    # -- Check-In GPS ------------------------------------------------------
    checkin_latitude = fields.Float(
        string='Check-In Latitude', digits=(16, 7), readonly=True, copy=False)
    checkin_longitude = fields.Float(
        string='Check-In Longitude', digits=(16, 7), readonly=True, copy=False)
    checkin_accuracy = fields.Float(
        string='Check-In GPS Accuracy (m)', digits=(16, 2), readonly=True,
        copy=False)
    checkin_datetime = fields.Datetime(
        string='Check-In Time', readonly=True, copy=False)
    checkin_distance = fields.Float(
        string='Check-In Distance (m)', digits=(16, 2), readonly=True,
        copy=False, aggregate='avg')
    checkin_geofence_status = fields.Selection(
        selection=[
            ('inside', 'Inside'),
            ('outside', 'Outside'),
            ('unknown', 'Unknown'),
        ],
        string='Check-In Geofence Status', readonly=True, copy=False,
        default=False)

    # -- Check-Out GPS -----------------------------------------------------
    checkout_latitude = fields.Float(
        string='Check-Out Latitude', digits=(16, 7), readonly=True, copy=False)
    checkout_longitude = fields.Float(
        string='Check-Out Longitude', digits=(16, 7), readonly=True, copy=False)
    checkout_accuracy = fields.Float(
        string='Check-Out GPS Accuracy (m)', digits=(16, 2), readonly=True,
        copy=False)
    checkout_datetime = fields.Datetime(
        string='Check-Out Time', readonly=True, copy=False)
    checkout_distance = fields.Float(
        string='Check-Out Distance (m)', digits=(16, 2), readonly=True,
        copy=False, aggregate='avg')
    checkout_geofence_status = fields.Selection(
        selection=[
            ('inside', 'Inside'),
            ('outside', 'Outside'),
            ('unknown', 'Unknown'),
        ],
        string='Check-Out Geofence Status', readonly=True, copy=False,
        default=False)

    # -- Customer location snapshot (frozen at check-in) --------------------
    customer_latitude_snapshot = fields.Float(
        string='Customer Latitude (Snapshot)', digits=(16, 7), readonly=True,
        copy=False,
        help="Customer coordinates frozen at check-in time, so later "
             "customer location edits never change historical visits.")
    customer_longitude_snapshot = fields.Float(
        string='Customer Longitude (Snapshot)', digits=(16, 7),
        readonly=True, copy=False)
    customer_geofence_radius_snapshot = fields.Float(
        string='Customer Geofence Radius (Snapshot)', digits=(16, 2),
        readonly=True, copy=False)

    # -- Manager override ----------------------------------------------------
    override_user_id = fields.Many2one(
        'res.users', string='Override By', readonly=True, copy=False)
    override_datetime = fields.Datetime(
        string='Override Time', readonly=True, copy=False)
    override_reason = fields.Text(string='Override Reason', readonly=True,
                                  copy=False)
    override_operation = fields.Selection(
        selection=[('checkin', 'Check-In'), ('checkout', 'Check-Out')],
        string='Override Operation', readonly=True, copy=False)

    # -- Indicators ----------------------------------------------------------
    gps_checkin_valid = fields.Boolean(
        compute='_compute_gps_validity', string='Check-In GPS Valid')
    gps_checkout_valid = fields.Boolean(
        compute='_compute_gps_validity', string='Check-Out GPS Valid')
    gps_has_override = fields.Boolean(
        compute='_compute_gps_validity', string='Has Manager Override',
        search='_search_gps_has_override')
    gps_checkin_low_accuracy = fields.Boolean(
        compute='_compute_gps_low_accuracy',
        string='Check-In Low Accuracy',
        search='_search_gps_checkin_low_accuracy',
        help="True when the check-in GPS accuracy is worse than the "
             "configured maximum.")

    gps_event_ids = fields.One2many(
        'distribution.visit.gps.event', 'visit_id', string='GPS Events')
    gps_event_count = fields.Integer(
        compute='_compute_gps_event_count', string='GPS Events')

    # Constraints ------------------------------------------------------------
    _checkin_latitude_check = models.Constraint(
        'CHECK (checkin_latitude IS NULL OR '
        '(checkin_latitude >= -90 AND checkin_latitude <= 90))',
        'Check-in latitude must be between -90 and 90 degrees.',
    )
    _checkin_longitude_check = models.Constraint(
        'CHECK (checkin_longitude IS NULL OR '
        '(checkin_longitude >= -180 AND checkin_longitude <= 180))',
        'Check-in longitude must be between -180 and 180 degrees.',
    )
    _checkout_latitude_check = models.Constraint(
        'CHECK (checkout_latitude IS NULL OR '
        '(checkout_latitude >= -90 AND checkout_latitude <= 90))',
        'Check-out latitude must be between -90 and 90 degrees.',
    )
    _checkout_longitude_check = models.Constraint(
        'CHECK (checkout_longitude IS NULL OR '
        '(checkout_longitude >= -180 AND checkout_longitude <= 180))',
        'Check-out longitude must be between -180 and 180 degrees.',
    )
    _checkout_after_checkin_check = models.Constraint(
        'CHECK (checkin_datetime IS NULL OR checkout_datetime IS NULL OR '
        'checkout_datetime >= checkin_datetime)',
        'Check-out time cannot be before check-in time.',
    )

    # Computes ---------------------------------------------------------------
    @api.depends('checkin_latitude', 'checkin_geofence_status',
                 'override_operation', 'checkout_latitude',
                 'checkout_geofence_status')
    def _compute_gps_validity(self):
        for visit in self:
            checkin_done = visit.checkin_datetime or visit.checkin_latitude
            checkout_done = visit.checkout_datetime or visit.checkout_latitude
            visit.gps_checkin_valid = bool(
                (checkin_done and visit.checkin_geofence_status == 'inside')
                or visit.override_operation == 'checkin')
            visit.gps_checkout_valid = bool(
                (checkout_done and visit.checkout_geofence_status == 'inside')
                or visit.override_operation == 'checkout')
            visit.gps_has_override = bool(visit.override_user_id)

    @api.depends('gps_event_ids')
    def _compute_gps_event_count(self):
        for visit in self:
            visit.gps_event_count = len(visit.gps_event_ids)

    @api.depends('checkin_accuracy')
    def _compute_gps_low_accuracy(self):
        config = self.env['distribution.gps.config'].get_params()
        for visit in self:
            visit.gps_checkin_low_accuracy = bool(
                visit.checkin_accuracy
                and visit.checkin_accuracy > config['maximum_accuracy'])

    @api.model
    def _search_gps_checkin_low_accuracy(self, operator, value):
        config = self.env['distribution.gps.config'].get_params()
        positive = (operator == '=' and value) or (operator == '!=' and not value)
        if positive:
            return [('checkin_accuracy', '>', config['maximum_accuracy'])]
        return ['|', ('checkin_accuracy', '<=', config['maximum_accuracy']),
                ('checkin_accuracy', '=', False)]

    @api.model
    def _search_gps_has_override(self, operator, value):
        positive = (operator == '=' and value) or (operator == '!=' and not value)
        if positive:
            return [('override_user_id', '!=', False)]
        return [('override_user_id', '=', False)]

    # Guards -----------------------------------------------------------------
    def write(self, vals):
        changed_gps = set(vals) & VISIT_GPS_FIELDS
        if changed_gps and not self.env.su \
                and not self.env.context.get('gps_internal_write'):
            raise UserError(_(
                "GPS data is recorded automatically during check-in / "
                "check-out and cannot be edited manually."))
        return super().write(vals)

    # ------------------------------------------------------------------
    # GPS math & helpers (server-side authority — never trust the client)
    # ------------------------------------------------------------------
    def _calculate_distance_meters(self, lat1, lon1, lat2, lon2):
        """Haversine great-circle distance between two points, in meters."""
        return gps_math.haversine_distance_meters(lat1, lon1, lat2, lon2)

    def _get_effective_geofence_radius(self):
        """Geofence radius priority: Partner > Area > Global default."""
        self.ensure_one()
        config = self.env['distribution.gps.config'].get_params()
        if self.partner_id and self.partner_id.distribution_geofence_radius:
            return self.partner_id.distribution_geofence_radius
        if self.area_id and self.area_id.default_geofence_radius:
            return self.area_id.default_geofence_radius
        return config['default_geofence_radius']

    def _validate_gps_input(self, latitude, longitude, accuracy):
        if not gps_math.is_valid_latitude(latitude) or \
                not gps_math.is_valid_longitude(longitude):
            raise UserError(_(
                "Invalid coordinates received. Latitude must be between "
                "-90 and 90 and longitude between -180 and 180."))
        if not gps_math.is_valid_accuracy(accuracy):
            raise UserError(_("Invalid GPS accuracy received."))

    def _validate_position_age(self, gps_timestamp):
        """True when the device position is fresh enough. gps_timestamp is
        the device epoch time in milliseconds."""
        config = self.env['distribution.gps.config'].get_params()
        if not gps_timestamp:
            return True
        try:
            device_dt = gps_math.epoch_ms_to_datetime(float(gps_timestamp))
        except (ValueError, TypeError, OSError, OverflowError):
            return True
        age = (fields.Datetime.now() - device_dt).total_seconds()
        return abs(age) <= config['max_position_age_seconds']

    def _accuracy_block(self, accuracy):
        """True when the position accuracy must block the operation."""
        config = self.env['distribution.gps.config'].get_params()
        return (config['accuracy_validation_mode'] == 'strict'
                and accuracy > config['maximum_accuracy'])

    def _accuracy_warning(self, accuracy):
        config = self.env['distribution.gps.config'].get_params()
        return (config['accuracy_validation_mode'] == 'warning'
                and accuracy > config['maximum_accuracy'])

    def _log_gps_event(self, **vals):
        """Create an immutable GPS audit event (sudo: audit log is written
        only by business logic — no user group has create access)."""
        vals.setdefault('user_id', self.env.user.id)
        vals.setdefault('server_datetime', fields.Datetime.now())
        if self and 'visit_id' not in vals:
            vals['visit_id'] = self.id
        if 'radius' in vals:
            vals['geofence_radius'] = vals.pop('radius')
        return self.env['distribution.visit.gps.event'].sudo().create(vals)

    def _prepare_gps_event_vals(self, event_type, latitude=False,
                                longitude=False, accuracy=False,
                                gps_timestamp=False, distance=False,
                                radius=False, status=False, message=False):
        self.ensure_one()
        return {
            'visit_id': self.id,
            'partner_id': self.partner_id.id,
            'event_type': event_type,
            'latitude': latitude,
            'longitude': longitude,
            'accuracy': accuracy,
            'gps_timestamp': gps_timestamp,
            'event_datetime': gps_math.epoch_ms_to_datetime(
                float(gps_timestamp)) if gps_timestamp else False,
            'customer_latitude': self.customer_latitude_snapshot,
            'customer_longitude': self.customer_longitude_snapshot,
            'distance': distance,
            'geofence_radius': radius,
            'geofence_status': status,
            'message': message,
        }

    # ------------------------------------------------------------------
    # Client-action entry points (triggered from the visit form buttons)
    # ------------------------------------------------------------------
    def action_start_visit_gps(self):
        """Replace the plain Start Visit: ask the browser for GPS first."""
        self.ensure_one()
        if not self._can_execute():
            raise UserError(_("You can only start visits assigned to you."))
        if self.state != 'pending':
            raise UserError(_("This visit has already been started or "
                              "closed."))
        if self.route_state != 'in_progress':
            raise UserError(_("Start the route first: visits can only be "
                              "started when the route is in progress."))
        if not self.visit_type_id.require_gps_checkin:
            # Visit type does not need GPS: plain start.
            self.action_start_visit()
            return True
        config = self.env['distribution.gps.config'].get_params()
        if not config['enabled']:
            # GPS validation globally disabled: plain start.
            self.action_start_visit()
            return True
        return {
            'type': 'ir.actions.client',
            'tag': 'distribution_gps.visit_action',
            'params': {'visit_id': self.id, 'operation': 'checkin'},
        }

    def action_complete_visit_gps(self):
        """Capture check-out GPS, then open the completion wizard."""
        self.ensure_one()
        if not self._can_execute():
            raise UserError(_("You can only complete visits assigned to "
                              "you."))
        if self.state != 'in_progress':
            raise UserError(_("Only in-progress visits can be completed."))
        if not self.visit_type_id.require_gps_checkout:
            return self.action_complete_visit_wizard()
        config = self.env['distribution.gps.config'].get_params()
        if not config['enabled']:
            return self.action_complete_visit_wizard()
        return {
            'type': 'ir.actions.client',
            'tag': 'distribution_gps.visit_action',
            'params': {'visit_id': self.id, 'operation': 'checkout'},
        }

    # ------------------------------------------------------------------
    # GPS submission (called by the client action after browser capture)
    # ------------------------------------------------------------------
    def gps_submit_checkin(self, latitude, longitude, accuracy,
                           gps_timestamp=None, override=False,
                           override_reason=None):
        """Validate GPS server-side, then start the visit.

        Never raises for business rejections: returns a status dict so the
        frontend can show a clean message / manager override wizard.
        """
        self.ensure_one()
        config = self.env['distribution.gps.config'].get_params()
        self._validate_gps_input(latitude, longitude, accuracy)
        event_base = {
            'latitude': latitude, 'longitude': longitude,
            'accuracy': accuracy, 'gps_timestamp': gps_timestamp,
        }

        if not config['enabled'] or not self.visit_type_id.require_gps_checkin:
            self.action_start_visit()
            return {'status': 'started', 'refresh_action': self._get_refresh_action()}

        # -- Position freshness -------------------------------------------
        # (skipped on manager override: the manager takes responsibility
        # for the age of the coordinates; both timestamps stay audited)
        if not override and not self._validate_position_age(gps_timestamp):
            self._log_gps_event(**dict(event_base, event_type='gps_error',
                                       message='stale_position'))
            raise UserError(_(
                "The GPS position is too old. Please retry to capture a "
                "fresh location."))

        # -- Accuracy --------------------------------------------------------
        if self._accuracy_block(accuracy):
            self._log_gps_event(**dict(
                event_base, event_type='gps_error', message='low_accuracy'))
            return {'status': 'blocked', 'reason': 'low_accuracy',
                    'override_allowed': self._is_manager(),
                    'message': _(
                        "The current location accuracy (%.0f m) is not good "
                        "enough. Try again in an open area with precise "
                        "location enabled.") % accuracy}

        customer = self.partner_id
        has_customer_loc = bool(customer and customer.has_distribution_location)

        # -- Missing customer location --------------------------------------
        if not has_customer_loc:
            policy = config['missing_customer_location_policy']
            status = 'unknown'
            distance = 0.0
            radius = self._get_effective_geofence_radius()
            if policy == 'block':
                self._log_gps_event(**dict(
                    event_base, event_type='gps_error',
                    message='missing_customer_location'))
                return {'status': 'blocked', 'reason': 'missing_customer_location',
                        'override_allowed': self._is_manager(),
                        'override_action': self._get_override_action(
                            'checkin', latitude, longitude, accuracy,
                            gps_timestamp),
                        'refresh_action': self._get_refresh_action(),
                        'message': _(
                            "This customer has no stored GPS location, and "
                            "the system blocks check-in without one.")}
            warning = policy == 'warn'
        else:
            distance = self._calculate_distance_meters(
                latitude, longitude,
                customer.distribution_latitude,
                customer.distribution_longitude)
            radius = self._get_effective_geofence_radius()
            status = 'inside' if distance <= radius else 'outside'
            warning = (status == 'outside'
                       and config['geofence_mode'] == 'warning')

        # -- Geofence ---------------------------------------------------------
        mode = config['geofence_mode']
        if (status == 'outside' and mode == 'strict'
                and not override and has_customer_loc):
            self._log_gps_event(**dict(event_base, event_type='checkin_rejected',
                                       distance=distance, radius=radius,
                                       geofence_status=status,
                                       message='outside_geofence'))
            return {'status': 'blocked', 'reason': 'outside_geofence',
                    'override_allowed': self._is_manager(),
                    'override_action': self._get_override_action(
                        'checkin', latitude, longitude, accuracy,
                        gps_timestamp),
                    'refresh_action': self._get_refresh_action(),
                    'message': GEOFENCE_MESSAGES['checkin'] % {
                        'distance': distance, 'radius': radius}}

        # -- Accuracy warning (non blocking) -----------------------------------
        if self._accuracy_warning(accuracy):
            self._log_gps_event(**dict(
                event_base, event_type='gps_error', message='low_accuracy_warning'))

        # -- Record check-in + start the visit (single transaction) ------------
        snapshot = {}
        if has_customer_loc:
            snapshot = {
                'customer_latitude_snapshot': customer.distribution_latitude,
                'customer_longitude_snapshot': customer.distribution_longitude,
            }
        self.with_context(gps_internal_write=True).write(dict({
            'checkin_latitude': latitude,
            'checkin_longitude': longitude,
            'checkin_accuracy': accuracy,
            'checkin_datetime': fields.Datetime.now(),
            'checkin_distance': distance if has_customer_loc else 0.0,
            'checkin_geofence_status': status,
            'customer_geofence_radius_snapshot': radius,
        }, **snapshot))
        self.action_start_visit()
        self._log_gps_event(**dict(event_base, event_type='checkin',
                                   distance=distance if has_customer_loc else 0.0,
                                   radius=radius, geofence_status=status,
                                   message='outside_geofence_warning' if warning
                                   and status == 'outside' else False))
        return {'status': 'started', 'checkin_distance': distance,
                'geofence_status': status,
                'refresh_action': self._get_refresh_action(),
                'warning': warning and status == 'outside'}

    def gps_submit_checkout(self, latitude, longitude, accuracy,
                            gps_timestamp=None, override=False):
        """Validate GPS server-side, record the check-out, then return the
        completion wizard action."""
        self.ensure_one()
        config = self.env['distribution.gps.config'].get_params()
        self._validate_gps_input(latitude, longitude, accuracy)
        event_base = {
            'latitude': latitude, 'longitude': longitude,
            'accuracy': accuracy, 'gps_timestamp': gps_timestamp,
        }

        if not self.visit_type_id.require_gps_checkout:
            return {'status': 'done',
                    'next_action': self.action_complete_visit_wizard()}

        if not override and not self._validate_position_age(gps_timestamp):
            self._log_gps_event(**dict(event_base, event_type='gps_error',
                                       message='stale_position'))
            raise UserError(_(
                "The GPS position is too old. Please retry to capture a "
                "fresh location."))

        if self._accuracy_block(accuracy):
            self._log_gps_event(**dict(event_base, event_type='gps_error',
                                       message='low_accuracy'))
            return {'status': 'blocked', 'reason': 'low_accuracy',
                    'override_allowed': self._is_manager(),
                    'override_action': self._get_override_action(
                        'checkout', latitude, longitude, accuracy,
                        gps_timestamp),                    'refresh_action': self._get_refresh_action(),                    'message': _(
                        "The current location accuracy (%.0f m) is not good "
                        "enough. Try again in an open area with precise "
                        "location enabled.") % accuracy}

        customer = self.partner_id
        has_customer_loc = bool(customer and customer.has_distribution_location)
        validate_geofence = config['validate_checkout_geofence']
        distance = 0.0
        radius = self._get_effective_geofence_radius()
        status = 'unknown'
        if has_customer_loc:
            distance = self._calculate_distance_meters(
                latitude, longitude,
                customer.distribution_latitude,
                customer.distribution_longitude)
            status = 'inside' if distance <= radius else 'outside'

        if (validate_geofence and has_customer_loc and status == 'outside'
                and config['geofence_mode'] == 'strict' and not override):
            self._log_gps_event(**dict(event_base, event_type='checkout_rejected',
                                       distance=distance, radius=radius,
                                       geofence_status=status,
                                       message='outside_geofence'))
            return {'status': 'blocked', 'reason': 'outside_geofence',
                    'override_allowed': self._is_manager(),
                    'override_action': self._get_override_action(
                        'checkout', latitude, longitude, accuracy,
                        gps_timestamp),
                    'message': GEOFENCE_MESSAGES['checkout'] % {
                        'distance': distance, 'radius': radius}}

        self.with_context(gps_internal_write=True).write({
            'checkout_latitude': latitude,
            'checkout_longitude': longitude,
            'checkout_accuracy': accuracy,
            'checkout_datetime': fields.Datetime.now(),
            'checkout_distance': distance if has_customer_loc else 0.0,
            'checkout_geofence_status': status,
        })
        self._log_gps_event(**dict(event_base, event_type='checkout',
                                   distance=distance if has_customer_loc else 0.0,
                                   radius=radius, geofence_status=status))
        return {'status': 'done',
                'next_action': self.action_complete_visit_wizard()}

    def _get_refresh_action(self):
        """Re-open the visit form so the UI reflects the new state."""
        self.ensure_one()
        return {
            'type': 'ir.actions.act_window',
            'res_model': 'distribution.route.visit',
            'res_id': self.id,
            'views': [(False, 'form')],
            'target': 'current',
        }

    def _get_override_action(self, operation, latitude, longitude, accuracy,
                             gps_timestamp):
        """Open the manager override wizard pre-filled with the blocked
        attempt coordinates."""
        self.ensure_one()
        return {
            'type': 'ir.actions.act_window',
            'name': _('GPS Override'),
            'res_model': 'distribution.gps.override.wizard',
            'view_mode': 'form',
            'views': [(False, 'form')],
            'target': 'new',
            'context': {
                'default_visit_id': self.id,
                'default_operation': operation,
                'default_latitude': latitude,
                'default_longitude': longitude,
                'default_accuracy': accuracy,
                'default_gps_timestamp': gps_timestamp or 0,
            },
        }

    # ------------------------------------------------------------------
    # Manager override (strict mode)
    # ------------------------------------------------------------------
    def action_gps_apply_override(self, operation, reason, latitude,
                                  longitude, accuracy, gps_timestamp=None):
        """Manager override: record the override on the visit, then apply
        the requested GPS operation without geofence blocking."""
        for visit in self:
            if not visit._is_manager():
                raise UserError(_("Only distribution managers may override "
                                  "GPS validation."))
            if not reason:
                raise UserError(_("An override reason is required."))
            if operation == 'checkin':
                visit.with_context(gps_internal_write=True).write({
                    'override_user_id': self.env.user.id,
                    'override_datetime': fields.Datetime.now(),
                    'override_reason': reason,
                    'override_operation': 'checkin',
                })
                visit._log_gps_event(
                    event_type='manager_override', latitude=latitude,
                    longitude=longitude, accuracy=accuracy,
                    gps_timestamp=gps_timestamp,
                    message='override_checkin: %s' % reason)
                visit.gps_submit_checkin(latitude, longitude, accuracy,
                                         gps_timestamp=gps_timestamp,
                                         override=True)
            elif operation == 'checkout':
                visit.with_context(gps_internal_write=True).write({
                    'override_user_id': self.env.user.id,
                    'override_datetime': fields.Datetime.now(),
                    'override_reason': reason,
                    'override_operation': 'checkout',
                })
                visit._log_gps_event(
                    event_type='manager_override', latitude=latitude,
                    longitude=longitude, accuracy=accuracy,
                    gps_timestamp=gps_timestamp,
                    message='override_checkout: %s' % reason)
                visit.gps_submit_checkout(latitude, longitude, accuracy,
                                          gps_timestamp=gps_timestamp,
                                          override=True)
            else:
                raise UserError(_("Unknown override operation."))
        return True

    def action_view_gps_events(self):
        self.ensure_one()
        return {
            'type': 'ir.actions.act_window',
            'name': _('GPS Events'),
            'res_model': 'distribution.visit.gps.event',
            'view_mode': 'list,form',
            'domain': [('visit_id', '=', self.id)],
            'context': {'default_visit_id': self.id},
        }

    # GPS error logging from the frontend (browser could not get a fix) ----
    def gps_log_frontend_error(self, message):
        """Record a gps_error event reported by the frontend."""
        self.ensure_one()
        self._log_gps_event(event_type='gps_error',
                            message=(message or 'gps_error')[:200])
        return True
