# -*- coding: utf-8 -*-
from odoo import _, api, fields, models
from odoo.exceptions import UserError, ValidationError

GROUP_MANAGER = 'flousflow_distribution_route_base.group_distribution_route_manager'

# Planning fields: only managers may change them (and only before execution).
VISIT_MASTER_FIELDS = {
    'partner_id', 'visit_type_id', 'planned_datetime', 'planned_duration',
    'objective', 'notes', 'sequence', 'route_id', 'company_id',
    'area_id', 'employee_id',
}
# Execution fields: written through actions only.
VISIT_EXECUTION_FIELDS = {
    'state', 'actual_start_datetime', 'actual_end_datetime', 'result_id',
    'result_notes', 'employee_notes', 'failure_reason', 'skip_reason',
    'completion_datetime', 'requires_revisit', 'suggested_revisit_date',
}


class DistributionRouteVisit(models.Model):
    _name = 'distribution.route.visit'
    _description = 'Distribution Route Visit'
    _order = 'route_id, sequence, id'
    _check_company_auto = True

    route_id = fields.Many2one(
        'distribution.route.plan',
        string='Route Plan',
        required=True,
        index=True,
        ondelete='cascade',
        check_company=True,
    )
    route_state = fields.Selection(related='route_id.state', string='Route Status')
    sequence = fields.Integer(string='Sequence', default=10, index=True)
    partner_id = fields.Many2one(
        'res.partner',
        string='Customer',
        index=True,
        check_company=True,
        domain="[('company_id', 'in', [company_id, False])]",
    )
    visit_type_id = fields.Many2one(
        'distribution.visit.type',
        string='Visit Type',
        required=True,
        index=True,
        check_company=True,
    )
    area_id = fields.Many2one(
        related='route_id.area_id',
        store=True,
        string='Distribution Area',
        index=True,
    )
    employee_id = fields.Many2one(
        related='route_id.employee_id',
        store=True,
        string='Employee',
        index=True,
    )
    # Stored on this table so permission checks read a plain column instead
    # of crossing the hr.employee relation (which is restricted for non-HR
    # users in Odoo 19).
    user_id = fields.Many2one(
        related='route_id.user_id',
        store=True,
        string='Assigned User',
        index=True,
    )
    company_id = fields.Many2one(
        related='route_id.company_id',
        store=True,
        string='Company',
        index=True,
    )

    # -- Planning ---------------------------------------------------------
    planned_datetime = fields.Datetime(string='Planned Time', index=True)
    planned_duration = fields.Float(
        string='Planned Duration (minutes)',
        default=30.0,
        help="Planned duration of the visit, in minutes.",
    )

    # -- Execution --------------------------------------------------------
    actual_start_datetime = fields.Datetime(
        string='Actual Start',
        readonly=True,
        copy=False,
    )
    actual_end_datetime = fields.Datetime(
        string='Actual End',
        readonly=True,
        copy=False,
    )
    actual_duration = fields.Float(
        compute='_compute_actual_duration',
        string='Actual Duration (minutes)',
        help="Effective visit duration, in minutes.",
    )
    arrival_variance_minutes = fields.Float(
        compute='_compute_arrival_variance',
        string='Arrival Variance (minutes)',
        help="Difference between actual start and planned time, in minutes. "
             "Positive = arrived late, negative = arrived early.",
    )
    state = fields.Selection(
        selection=[
            ('pending', 'Pending'),
            ('in_progress', 'In Progress'),
            ('done', 'Done'),
            ('cancelled', 'Cancelled'),
        ],
        string='Execution State',
        default='pending',
        required=True,
        index=True,
        copy=False,
        help="Execution state of the visit. The business outcome is tracked "
             "separately by the Visit Result.",
    )

    # -- Content ----------------------------------------------------------
    objective = fields.Text(string='Objective')
    notes = fields.Text(
        string='Notes',
        help="Preparation notes entered at planning time.",
    )
    employee_notes = fields.Text(
        string='Employee Notes',
        copy=False,
        help="Notes recorded by the representative during/after the visit.",
    )

    # -- Result -----------------------------------------------------------
    result_id = fields.Many2one(
        'distribution.visit.result',
        string='Visit Result',
        index=True,
        check_company=True,
        copy=False,
    )
    result_notes = fields.Text(string='Result Notes', copy=False)
    failure_reason = fields.Text(
        string='Failure Reason',
        copy=False,
        help="Mandatory when the visit is closed with an unsuccessful result.",
    )
    skip_reason = fields.Text(
        string='Skip Reason',
        copy=False,
        help="Mandatory when the visit is skipped (cancelled).",
    )
    completion_datetime = fields.Datetime(string='Completion Time', readonly=True, copy=False)
    requires_revisit = fields.Boolean(
        string='Revisit Required',
        copy=False,
        help="Set when the outcome indicates a follow-up visit is needed.",
    )
    suggested_revisit_date = fields.Date(string='Suggested Revisit Date', copy=False)

    _visit_final_result_check = models.Constraint(
        'CHECK (state != \'done\' OR result_id IS NOT NULL)',
        'A done visit must always have a visit result.',
    )

    # ------------------------------------------------------------------
    # Compute
    # ------------------------------------------------------------------
    @api.depends('actual_start_datetime', 'actual_end_datetime')
    def _compute_actual_duration(self):
        for visit in self:
            if visit.actual_start_datetime and visit.actual_end_datetime:
                delta = visit.actual_end_datetime - visit.actual_start_datetime
                visit.actual_duration = delta.total_seconds() / 60.0
            else:
                visit.actual_duration = 0.0

    @api.depends('actual_start_datetime', 'planned_datetime')
    def _compute_arrival_variance(self):
        for visit in self:
            if visit.actual_start_datetime and visit.planned_datetime:
                delta = visit.actual_start_datetime - visit.planned_datetime
                visit.arrival_variance_minutes = delta.total_seconds() / 60.0
            else:
                visit.arrival_variance_minutes = 0.0

    def _compute_display_name(self):
        """Display as '<Customer> — <planned time>' for a readable reference."""
        for visit in self:
            name = visit.partner_id.display_name or visit.visit_type_id.name or _('Visit')
            if visit.planned_datetime:
                local_dt = fields.Datetime.context_timestamp(
                    visit.with_user(visit.user_id or self.env.user),
                    visit.planned_datetime)
                name = f"{name} — {local_dt.strftime('%Y-%m-%d %H:%M')}"
            visit.display_name = name

    # ------------------------------------------------------------------
    # Constraints
    # ------------------------------------------------------------------
    @api.constrains('visit_type_id', 'partner_id')
    def _check_required_customer(self):
        for visit in self:
            if visit.visit_type_id.require_customer and not visit.partner_id:
                raise ValidationError(_(
                    "Visit '%(type)s' requires a customer. Please set a "
                    "customer on this visit.",
                    type=visit.visit_type_id.name,
                ))

    @api.constrains('route_id', 'partner_id', 'visit_type_id', 'company_id')
    def _check_company_consistency(self):
        for visit in self:
            route = visit.route_id
            if visit.company_id != route.company_id:
                raise ValidationError(_(
                    "The visit and its route plan must belong to the same "
                    "company.",
                ))
            if visit.visit_type_id.company_id and \
                    visit.visit_type_id.company_id != visit.company_id:
                raise ValidationError(_(
                    "The visit type '%(type)s' does not belong to the company "
                    "of the route plan.",
                    type=visit.visit_type_id.name,
                ))
            if visit.partner_id and visit.partner_id.company_id and \
                    visit.partner_id.company_id != visit.company_id:
                raise ValidationError(_(
                    "The customer '%(partner)s' does not belong to the company "
                    "of the route plan.",
                    partner=visit.partner_id.name,
                ))

    @api.constrains('planned_datetime')
    def _check_planned_date_matches_route(self):
        """The planned visit time must fall on the route date (employee tz)."""
        for visit in self:
            if not visit.planned_datetime:
                continue
            route_date = visit.route_id.date
            tz_user = visit.route_id.user_id or self.env.user
            local_dt = fields.Datetime.context_timestamp(
                visit.with_user(tz_user), visit.planned_datetime)
            if local_dt.date() != route_date:
                raise ValidationError(_(
                    "The planned time of this visit (%(planned)s) does not "
                    "match the route date (%(date)s).",
                    planned=local_dt.strftime('%Y-%m-%d %H:%M'),
                    date=route_date,
                ))

    @api.constrains('state', 'failure_reason')
    def _check_failure_reason(self):
        for visit in self:
            if (visit.state == 'done'
                    and visit.result_id
                    and not visit.result_id.is_success
                    and not visit.failure_reason):
                raise ValidationError(_(
                    "A failure reason is required when closing a visit with "
                    "the unsuccessful result '%(result)s'.",
                    result=visit.result_id.name,
                ))

    @api.constrains('state', 'skip_reason')
    def _check_skip_reason(self):
        for visit in self:
            if visit.state == 'cancelled' and not visit.skip_reason:
                raise ValidationError(_(
                    "A skip reason is required when cancelling a visit.",
                ))

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------
    def _is_manager(self):
        return self.env.user.has_group(GROUP_MANAGER)

    def _is_assigned_user(self):
        self.ensure_one()
        # Read the stored related column: never cross hr.employee here.
        return self.user_id == self.env.user

    def _can_execute(self):
        self.ensure_one()
        return self._is_manager() or self._is_assigned_user()

    # ------------------------------------------------------------------
    # CRUD guards
    # ------------------------------------------------------------------
    @api.model_create_multi
    def create(self, vals_list):
        visits = super().create(vals_list)
        if not (self.env.su or visits._is_manager()):
            raise UserError(_(
                "Only distribution managers may add visits to a route plan."
            ))
        return visits

    def write(self, vals):
        is_manager = self._is_manager()
        changed = set(vals)
        # Extension modules (e.g. the GPS module) write their own audit
        # fields during sanctioned business operations; they enforce their
        # own permission checks before writing.
        gps_internal = self.env.context.get('gps_internal_write')
        for visit in self:
            if is_manager or gps_internal:
                continue
            if not visit._is_assigned_user():
                raise UserError(_("You can only modify your own visits."))
            if changed & VISIT_MASTER_FIELDS:
                raise UserError(_(
                    "Only distribution managers may modify visit planning "
                    "data."
                ))
            if changed - VISIT_EXECUTION_FIELDS:
                raise UserError(_("You are not allowed to modify this field."))
            if visit.state == 'done' and 'state' in changed and \
                    vals['state'] != 'done':
                raise UserError(_("A closed visit cannot be reopened."))
        return super().write(vals)

    # ------------------------------------------------------------------
    # Confirm-time validation (called from route plan)
    # ------------------------------------------------------------------
    def _check_visit_ready_for_confirm(self):
        for visit in self:
            if not visit.visit_type_id:
                raise ValidationError(_("Every visit requires a visit type."))
            if visit.visit_type_id.require_customer and not visit.partner_id:
                raise ValidationError(_(
                    "Visit '%(type)s' requires a customer before confirming "
                    "the route.",
                    type=visit.visit_type_id.name,
                ))
            if not visit.planned_datetime:
                raise ValidationError(_(
                    "Every visit requires a planned time before confirming "
                    "the route (visit %(seq)s).",
                    seq=visit.sequence,
                ))

    # ------------------------------------------------------------------
    # Visit execution actions (GPS-extension friendly: override & super())
    # ------------------------------------------------------------------
    def action_start_visit(self):
        """Start the visit: record the actual start datetime."""
        for visit in self:
            if not visit._can_execute():
                raise UserError(_(
                    "You can only start visits assigned to you."
                ))
            if visit.route_state != 'in_progress':
                raise UserError(_(
                    "Start the route first: visits can only be started when "
                    "the route is in progress."
                ))
            if visit.state != 'pending':
                raise UserError(_(
                    "This visit has already been started or closed."
                ))
            visit.write({
                'state': 'in_progress',
                'actual_start_datetime': fields.Datetime.now(),
            })
        return True

    def action_complete_visit_wizard(self):
        """Open the Complete Visit wizard."""
        self.ensure_one()
        if not self._can_execute():
            raise UserError(_("You can only complete visits assigned to you."))
        if self.state != 'in_progress':
            raise UserError(_("Only in-progress visits can be completed."))
        return {
            'type': 'ir.actions.act_window',
            'name': _('Complete Visit'),
            'res_model': 'distribution.visit.complete.wizard',
            'view_mode': 'form',
            'target': 'new',
            'context': {'default_visit_id': self.id},
        }

    def action_finalize_visit(self, result_id, result_notes=False,
                              employee_notes=False, failure_reason=False,
                              requires_revisit=False,
                              suggested_revisit_date=False):
        """Close the visit as done with a business result.

        Single entry point so extension modules (e.g. GPS) can override and
        enrich it with extra evidence before calling super().
        """
        for visit in self:
            if not visit._can_execute():
                raise UserError(_("You can only complete visits assigned to "
                                  "you."))
            if visit.state != 'in_progress':
                raise UserError(_("Only in-progress visits can be completed."))
            result = self.env['distribution.visit.result'].browse(result_id)
            if not result.exists():
                raise UserError(_("A visit result is required."))
            if result.requires_notes and not result_notes:
                raise UserError(_(
                    "Result notes are required for the result '%(result)s'.",
                    result=result.name,
                ))
            if not result.is_success and not failure_reason:
                raise UserError(_(
                    "A failure reason is required for the unsuccessful result "
                    "'%(result)s'.",
                    result=result.name,
                ))
            visit.write({
                'state': 'done',
                'result_id': result.id,
                'result_notes': result_notes,
                'employee_notes': employee_notes or visit.employee_notes,
                'failure_reason': failure_reason,
                'requires_revisit': requires_revisit or result.requires_revisit,
                'suggested_revisit_date': suggested_revisit_date,
                'actual_end_datetime': fields.Datetime.now(),
                'completion_datetime': fields.Datetime.now(),
            })
        return True

    def action_skip_visit_wizard(self):
        """Open the Skip Visit wizard."""
        self.ensure_one()
        if not self._can_execute():
            raise UserError(_("You can only skip visits assigned to you."))
        if self.state not in ('pending', 'in_progress'):
            raise UserError(_("Only pending or in-progress visits can be "
                              "skipped."))
        return {
            'type': 'ir.actions.act_window',
            'name': _('Skip Visit'),
            'res_model': 'distribution.visit.skip.wizard',
            'view_mode': 'form',
            'target': 'new',
            'context': {'default_visit_id': self.id},
        }

    def action_skip_visit(self, reason):
        """Skip (cancel) the visit with a mandatory reason."""
        for visit in self:
            if not visit._can_execute():
                raise UserError(_("You can only skip visits assigned to you."))
            if visit.state not in ('pending', 'in_progress'):
                raise UserError(_("Only pending or in-progress visits can be "
                                  "skipped."))
            if not reason:
                raise UserError(_("A skip reason is required."))
            visit.write({
                'state': 'cancelled',
                'skip_reason': reason,
                'actual_end_datetime': fields.Datetime.now(),
            })
        return True
