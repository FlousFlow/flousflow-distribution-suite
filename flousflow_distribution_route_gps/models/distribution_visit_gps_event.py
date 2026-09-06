# -*- coding: utf-8 -*-
from odoo import _, api, fields, models
from odoo.exceptions import UserError


class DistributionVisitGpsEvent(models.Model):
    """Immutable GPS audit log.

    Records are created only from business logic (via sudo, because no
    user group has create/write/unlink access) and can never be edited
    or deleted through the UI — not even by managers.
    """
    _name = 'distribution.visit.gps.event'
    _description = 'Distribution Visit GPS Event'
    _order = 'id desc'
    _rec_name = 'display_name_'

    visit_id = fields.Many2one(
        'distribution.route.visit', string='Visit',
        index=True, ondelete='cascade',
        help="Empty for customer-location capture events.",
    )
    route_id = fields.Many2one(
        related='visit_id.route_id', store=True, string='Route Plan',
        index=True)
    employee_id = fields.Many2one(
        related='visit_id.employee_id', store=True, string='Employee',
        index=True)
    partner_id = fields.Many2one(
        'res.partner', string='Customer', index=True,
        help="Customer of the visit, or the partner whose location was "
             "captured for customer_location_capture events.")
    user_id = fields.Many2one(
        'res.users', string='User', index=True, default=lambda self: self.env.user)
    company_id = fields.Many2one(
        related='visit_id.company_id', store=True, string='Company',
        index=True)
    event_type = fields.Selection(
        selection=[
            ('customer_location_capture', 'Customer Location Capture'),
            ('checkin', 'Check-In'),
            ('checkout', 'Check-Out'),
            ('checkin_rejected', 'Check-In Rejected'),
            ('checkout_rejected', 'Check-Out Rejected'),
            ('gps_error', 'GPS Error'),
            ('manager_override', 'Manager Override'),
        ],
        string='Event Type', required=True, index=True)
    latitude = fields.Float(string='Latitude', digits=(16, 7))
    longitude = fields.Float(string='Longitude', digits=(16, 7))
    accuracy = fields.Float(string='GPS Accuracy (m)', digits=(16, 2))
    customer_latitude = fields.Float(
        string='Customer Latitude', digits=(16, 7))
    customer_longitude = fields.Float(
        string='Customer Longitude', digits=(16, 7))
    distance = fields.Float(string='Distance (m)', digits=(16, 2))
    geofence_radius = fields.Float(
        string='Geofence Radius (m)', digits=(16, 2))
    geofence_status = fields.Selection(
        selection=[
            ('inside', 'Inside'),
            ('outside', 'Outside'),
            ('unknown', 'Unknown'),
        ],
        string='Geofence Status')
    event_datetime = fields.Datetime(
        string='Event Time (Device)', readonly=True,
        help="Timestamp reported by the device GPS, in UTC.")
    server_datetime = fields.Datetime(
        string='Server Time', readonly=True, default=fields.Datetime.now,
        required=True)
    gps_timestamp = fields.Float(
        string='GPS Timestamp (epoch)', readonly=True,
        help="Raw device GPS timestamp (Unix epoch milliseconds).")
    message = fields.Text(string='Message', readonly=True)

    display_name_ = fields.Char(compute='_compute_display_name_')

    _latitude_check = models.Constraint(
        'CHECK (latitude IS NULL OR (latitude >= -90 AND latitude <= 90))',
        'Latitude must be between -90 and 90 degrees.',
    )
    _longitude_check = models.Constraint(
        'CHECK (longitude IS NULL OR (longitude >= -180 AND longitude <= 180))',
        'Longitude must be between -180 and 180 degrees.',
    )

    @api.depends('event_type', 'server_datetime')
    def _compute_display_name_(self):
        for event in self:
            event.display_name_ = "%s — %s" % (
                dict(self._fields['event_type'].selection).get(
                    event.event_type, event.event_type),
                event.server_datetime or '',
            )

    # ------------------------------------------------------------------
    # Immutability: the event log is write-once.
    # ------------------------------------------------------------------
    @api.model_create_multi
    def create(self, vals_list):
        """Audit records are created only from business logic."""
        return super().create(vals_list)

    def write(self, vals):
        if not self.env.su:
            raise UserError(_(
                "GPS events are an immutable audit log and cannot be "
                "modified."))
        return super().write(vals)

    def unlink(self):
        if not self.env.su:
            raise UserError(_(
                "GPS events are an immutable audit log and cannot be "
                "deleted."))
        return super().unlink()
