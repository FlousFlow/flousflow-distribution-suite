# -*- coding: utf-8 -*-
from odoo import _, api, fields, models
from odoo.exceptions import UserError


class DistributionGpsOverrideWizard(models.TransientModel):
    _name = 'distribution.gps.override.wizard'
    _description = 'GPS Validation Override Wizard'
    _check_company_auto = True

    visit_id = fields.Many2one(
        'distribution.route.visit', string='Visit', required=True,
        check_company=True)
    operation = fields.Selection(
        selection=[('checkin', 'Check-In'), ('checkout', 'Check-Out')],
        string='Operation', required=True)
    reason = fields.Text(string='Override Reason', required=True)
    latitude = fields.Float(string='Latitude', digits=(16, 7))
    longitude = fields.Float(string='Longitude', digits=(16, 7))
    accuracy = fields.Float(string='GPS Accuracy (m)', digits=(16, 2))
    gps_timestamp = fields.Float(string='GPS Timestamp (epoch)')

    @api.model
    def default_get(self, fields_list):
        res = super().default_get(fields_list)
        ctx = self.env.context
        if 'default_visit_id' not in res and ctx.get('active_id') \
                and ctx.get('active_model') == 'distribution.route.visit':
            res['default_visit_id'] = ctx.get('active_id')
        return res

    def action_confirm(self):
        self.ensure_one()
        if not self.env.user.has_group(
                'flousflow_distribution_route_base.'
                'group_distribution_route_manager'):
            raise UserError(_("Only distribution managers may override GPS "
                              "validation."))
        visit = self.visit_id
        visit.action_gps_apply_override(
            operation=self.operation,
            reason=self.reason,
            latitude=self.latitude,
            longitude=self.longitude,
            accuracy=self.accuracy,
            gps_timestamp=self.gps_timestamp,
        )
        # The visit / completion wizard now reflects the override result.
        if self.operation == 'checkout':
            return visit.action_complete_visit_wizard()
        return {'type': 'ir.actions.act_window_close'}
