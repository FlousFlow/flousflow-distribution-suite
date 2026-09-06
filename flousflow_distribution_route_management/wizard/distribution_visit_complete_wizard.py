# -*- coding: utf-8 -*-
from odoo import _, api, fields, models
from odoo.exceptions import UserError


class DistributionVisitCompleteWizard(models.TransientModel):
    _name = 'distribution.visit.complete.wizard'
    _description = 'Complete Visit Wizard'
    _check_company_auto = True

    company_id = fields.Many2one(
        'res.company',
        string='Company',
        default=lambda self: self.env.company,
        required=True,
    )
    visit_id = fields.Many2one(
        'distribution.route.visit',
        string='Visit',
        required=True,
        check_company=True,
    )
    result_id = fields.Many2one(
        'distribution.visit.result',
        string='Visit Result',
        required=True,
        check_company=True,
        domain="[('company_id', 'in', [company_id, False]), "
               "('active', '=', True)]",
    )
    result_is_success = fields.Boolean(related='result_id.is_success')
    result_requires_notes = fields.Boolean(related='result_id.requires_notes')
    result_notes = fields.Text(string='Result Notes')
    employee_notes = fields.Text(
        string='Employee Notes',
        help="Optional notes about how the visit went.",
    )
    failure_reason = fields.Text(
        string='Failure Reason',
        help="Required for unsuccessful results.",
    )
    requires_revisit = fields.Boolean(string='Revisit Required')
    suggested_revisit_date = fields.Date(string='Suggested Revisit Date')

    @api.onchange('result_id')
    def _onchange_result_id(self):
        if self.result_id:
            self.requires_revisit = self.result_id.requires_revisit
        else:
            self.requires_revisit = False

    @api.constrains('requires_revisit', 'suggested_revisit_date')
    def _check_revisit_date(self):
        for wizard in self:
            if wizard.requires_revisit and not wizard.suggested_revisit_date:
                raise UserError(_(
                    "A suggested revisit date is required when a revisit is "
                    "needed."
                ))

    def action_confirm(self):
        self.ensure_one()
        self._check_revisit_date()
        self.visit_id.action_finalize_visit(
            result_id=self.result_id.id,
            result_notes=self.result_notes,
            employee_notes=self.employee_notes,
            failure_reason=self.failure_reason,
            requires_revisit=self.requires_revisit,
            suggested_revisit_date=self.suggested_revisit_date,
        )
        return {'type': 'ir.actions.act_window_close'}


class DistributionVisitSkipWizard(models.TransientModel):
    _name = 'distribution.visit.skip.wizard'
    _description = 'Skip Visit Wizard'
    _check_company_auto = True

    visit_id = fields.Many2one(
        'distribution.route.visit',
        string='Visit',
        required=True,
        check_company=True,
    )
    skip_reason = fields.Text(string='Skip Reason', required=True)

    def action_confirm(self):
        self.ensure_one()
        self.visit_id.action_skip_visit(self.skip_reason)
        return {'type': 'ir.actions.act_window_close'}


class DistributionRouteCancelWizard(models.TransientModel):
    _name = 'distribution.route.cancel.wizard'
    _description = 'Cancel Route Wizard'
    _check_company_auto = True

    route_id = fields.Many2one(
        'distribution.route.plan',
        string='Route Plan',
        required=True,
        check_company=True,
    )
    cancellation_reason = fields.Text(string='Cancellation Reason', required=True)

    def action_confirm(self):
        self.ensure_one()
        self.route_id.action_cancel_route(reason=self.cancellation_reason)
        return {'type': 'ir.actions.act_window_close'}


class DistributionRouteForceCompleteWizard(models.TransientModel):
    _name = 'distribution.route.force.complete.wizard'
    _description = 'Force Complete Route Wizard'
    _check_company_auto = True

    route_id = fields.Many2one(
        'distribution.route.plan',
        string='Route Plan',
        required=True,
        check_company=True,
    )
    reason = fields.Text(string='Reason', required=True)
    pending_visit_count = fields.Integer(
        related='route_id.pending_visit_count',
        string='Open Visits',
    )

    def action_confirm(self):
        self.ensure_one()
        self.route_id.action_complete_route(force=True, reason=self.reason)
        return {'type': 'ir.actions.act_window_close'}
