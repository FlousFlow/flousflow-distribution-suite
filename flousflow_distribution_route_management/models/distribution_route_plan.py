# -*- coding: utf-8 -*-
from odoo import _, api, fields, models
from odoo.exceptions import UserError, ValidationError

GROUP_MANAGER = 'flousflow_distribution_route_base.group_distribution_route_manager'

# Fields a (non-manager) representative may never change after confirm.
PLAN_MASTER_FIELDS = {
    'employee_id', 'area_id', 'date', 'supervisor_id',
    'planned_start_time', 'planned_end_time', 'visit_ids', 'company_id',
}
# Fields representatives may write on their plan (via actions only).
PLAN_EXECUTION_FIELDS = {'state', 'actual_start_datetime', 'actual_end_datetime'}


class DistributionRoutePlan(models.Model):
    _name = 'distribution.route.plan'
    _description = 'Distribution Route Plan'
    _inherit = ['mail.thread', 'mail.activity.mixin']
    _order = 'date desc, id desc'
    _check_company_auto = True

    name = fields.Char(
        string='Route Reference',
        required=True,
        copy=False,
        index=True,
        default=lambda self: _('New'),
    )
    date = fields.Date(
        string='Route Date',
        required=True,
        index=True,
        default=fields.Date.context_today,
        tracking=True,
    )
    employee_id = fields.Many2one(
        'hr.employee',
        string='Employee',
        required=True,
        index=True,
        check_company=True,
        tracking=True,
        domain="[('is_distribution_employee', '=', True), "
               "('distribution_active', '=', True)]",
    )
    user_id = fields.Many2one(
        related='employee_id.user_id',
        store=True,
        string='Assigned User',
        index=True,
    )
    supervisor_id = fields.Many2one(
        'hr.employee',
        string='Supervisor',
        check_company=True,
        index=True,
        tracking=True,
    )
    area_id = fields.Many2one(
        'distribution.area',
        string='Distribution Area',
        required=True,
        index=True,
        check_company=True,
        tracking=True,
    )
    company_id = fields.Many2one(
        'res.company',
        string='Company',
        required=True,
        index=True,
        default=lambda self: self.env.company,
    )
    state = fields.Selection(
        selection=[
            ('draft', 'Draft'),
            ('confirmed', 'Confirmed'),
            ('in_progress', 'In Progress'),
            ('completed', 'Completed'),
            ('cancelled', 'Cancelled'),
        ],
        string='Status',
        default='draft',
        required=True,
        index=True,
        tracking=True,
        copy=False,
    )
    notes = fields.Text(string='Notes')
    visit_ids = fields.One2many(
        'distribution.route.visit',
        'route_id',
        string='Route Visits',
        copy=False,
    )

    # -- Counters / rates ------------------------------------------------
    visit_count = fields.Integer(compute='_compute_visit_stats', string='Total Visits')
    done_visit_count = fields.Integer(compute='_compute_visit_stats', string='Executed Visits')
    cancelled_visit_count = fields.Integer(compute='_compute_visit_stats', string='Cancelled Visits')
    remaining_visit_count = fields.Integer(compute='_compute_visit_stats', string='Remaining Visits')
    pending_visit_count = fields.Integer(compute='_compute_visit_stats', string='Pending / In Progress')
    execution_rate = fields.Float(
        compute='_compute_visit_stats',
        string='Execution Rate (%)',
        help="Executed visits / planned active visits x 100. "
             "Cancelled visits are excluded from both sides.",
    )
    success_rate = fields.Float(
        compute='_compute_visit_stats',
        string='Success Rate (%)',
        help="Successful results / executed visits x 100.",
    )
    can_complete = fields.Boolean(
        compute='_compute_visit_stats',
        string='All Visits Closed',
        help="True when every visit is in a final state (done or cancelled).",
    )

    # -- Planning / execution times ---------------------------------------
    planned_start_time = fields.Datetime(string='Planned Start Time')
    planned_end_time = fields.Datetime(string='Planned End Time')
    actual_start_datetime = fields.Datetime(
        string='Actual Start',
        readonly=True,
        copy=False,
        tracking=True,
    )
    actual_end_datetime = fields.Datetime(
        string='Actual End',
        readonly=True,
        copy=False,
        tracking=True,
    )
    duration = fields.Float(
        compute='_compute_duration',
        string='Duration (minutes)',
        help="Actual execution duration of the route, in minutes.",
    )
    cancellation_reason = fields.Text(
        string='Cancellation Reason',
        copy=False,
        readonly=True,
        tracking=True,
    )

    _planned_times_check = models.Constraint(
        'CHECK (planned_start_time IS NULL OR planned_end_time IS NULL '
        'OR planned_start_time <= planned_end_time)',
        'The planned end time must be after the planned start time.',
    )

    # ------------------------------------------------------------------
    # Compute
    # ------------------------------------------------------------------
    @api.depends('visit_ids.state', 'visit_ids.result_id.is_success')
    def _compute_visit_stats(self):
        for plan in self:
            visits = plan.visit_ids
            done = visits.filtered(lambda v: v.state == 'done')
            cancelled = visits.filtered(lambda v: v.state == 'cancelled')
            open_visits = visits.filtered(lambda v: v.state in ('pending', 'in_progress'))
            plan.visit_count = len(visits)
            plan.done_visit_count = len(done)
            plan.cancelled_visit_count = len(cancelled)
            plan.pending_visit_count = len(open_visits)
            plan.remaining_visit_count = len(open_visits)
            # Cancelled visits are excluded from both sides of the rate.
            active = len(visits) - len(cancelled)
            plan.execution_rate = (len(done) / active * 100.0) if active else 0.0
            successful = done.filtered(lambda v: v.result_id and v.result_id.is_success)
            plan.success_rate = (len(successful) / len(done) * 100.0) if done else 0.0
            plan.can_complete = bool(visits) and not open_visits

    @api.depends('actual_start_datetime', 'actual_end_datetime')
    def _compute_duration(self):
        for plan in self:
            if plan.actual_start_datetime and plan.actual_end_datetime:
                delta = plan.actual_end_datetime - plan.actual_start_datetime
                plan.duration = delta.total_seconds() / 60.0
            else:
                plan.duration = 0.0

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------
    def _is_manager(self):
        return self.env.user.has_group(GROUP_MANAGER)

    @api.onchange('employee_id')
    def _onchange_employee_id(self):
        """Propose supervisor and area from the employee configuration."""
        if self.employee_id:
            self.supervisor_id = self.employee_id.distribution_supervisor_id
            if not self.area_id and self.employee_id.distribution_area_ids:
                if len(self.employee_id.distribution_area_ids) == 1:
                    self.area_id = self.employee_id.distribution_area_ids

    # ------------------------------------------------------------------
    # CRUD
    # ------------------------------------------------------------------
    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            if not vals.get('name') or vals['name'] == _('New'):
                vals['name'] = self.env['ir.sequence'].next_by_code(
                    'distribution.route.plan') or _('New')
        plans = super().create(vals_list)
        for plan in plans:
            if plan.state != 'draft':
                raise UserError(_("A route plan must start in the Draft state."))
        return plans

    def write(self, vals):
        is_manager = self._is_manager()
        changed = set(vals)
        for plan in self:
            if is_manager:
                continue
            if plan.state in ('completed', 'cancelled'):
                raise UserError(_(
                    "Route %(route)s is %(state)s and can no longer be modified.",
                    route=plan.name,
                    state=plan.state.replace('_', ' '),
                ))
            if plan.state != 'draft' and (changed & PLAN_MASTER_FIELDS):
                raise UserError(_(
                    "Only distribution managers may modify the planning data of "
                    "route %(route)s after confirmation.",
                    route=plan.name,
                ))
            if plan.state != 'draft' and (changed - PLAN_EXECUTION_FIELDS):
                raise UserError(_(
                    "You are not allowed to modify route %(route)s after "
                    "confirmation.",
                    route=plan.name,
                ))
        return super().write(vals)

    def unlink(self):
        for plan in self:
            if plan.state != 'draft':
                raise UserError(_(
                    "Only draft route plans can be deleted. Route %(route)s is "
                    "%(state)s.",
                    route=plan.name,
                    state=plan.state.replace('_', ' '),
                ))
        return super().unlink()

    def copy(self, default=None):
        """Duplicate as a fresh draft: no execution data, visits pending."""
        self.ensure_one()
        default = dict(default or {})
        default.update({
            'state': 'draft',
            'actual_start_datetime': False,
            'actual_end_datetime': False,
            'cancellation_reason': False,
        })
        new_plan = super().copy(default)
        # Recreate visits with planning data only (execution data is reset).
        PlanningVisit = self.env['distribution.route.visit']
        for visit in self.visit_ids:
            PlanningVisit.create({
                'route_id': new_plan.id,
                'sequence': visit.sequence,
                'partner_id': visit.partner_id.id,
                'visit_type_id': visit.visit_type_id.id,
                'planned_datetime': visit.planned_datetime,
                'planned_duration': visit.planned_duration,
                'objective': visit.objective,
                'notes': visit.notes,
            })
        return new_plan

    # ------------------------------------------------------------------
    # Workflow: Confirm
    # ------------------------------------------------------------------
    def _prepare_confirm_error_context(self):
        return {'route': self.name}

    def action_confirm(self):
        self.ensure_one()
        if self.state != 'draft':
            raise UserError(_("Only draft routes can be confirmed."))
        if not self.visit_ids:
            raise UserError(_(
                "You must add at least one visit before confirming route "
                "%(route)s.",
                route=self.name,
            ))
        self._check_employee_area_consistency()
        self.visit_ids._check_visit_ready_for_confirm()
        self.write({'state': 'confirmed'})
        self.message_post(body=_("Route confirmed with %(count)s visit(s).",
                                 count=len(self.visit_ids)))
        return True

    def _check_employee_area_consistency(self):
        if (self.employee_id.distribution_area_ids
                and self.area_id not in self.employee_id.distribution_area_ids):
            raise ValidationError(_(
                "The distribution area '%(area)s' is not assigned to employee "
                "'%(employee)s'. Assign the area to the employee first or "
                "choose another area.",
                area=self.area_id.display_name,
                employee=self.employee_id.name,
            ))

    # ------------------------------------------------------------------
    # Workflow: Start / Complete / Cancel
    # ------------------------------------------------------------------
    def action_start_route(self):
        self.ensure_one()
        if self.state != 'confirmed':
            raise UserError(_(
                "Route %(route)s cannot be started from the %(state)s state. "
                "Only confirmed routes can be started.",
                route=self.name,
                state=self.state.replace('_', ' '),
            ))
        if not self._is_manager() and self.user_id != self.env.user:
            raise UserError(_("You can only start routes assigned to you."))
        self.write({
            'state': 'in_progress',
            'actual_start_datetime': fields.Datetime.now(),
        })
        self.message_post(body=_("Route started."))
        return True

    def action_complete_route(self, force=False, reason=None):
        for plan in self:
            if plan.state != 'in_progress':
                raise UserError(_(
                    "Route %(route)s cannot be completed from the %(state)s "
                    "state.",
                    route=plan.name,
                    state=plan.state.replace('_', ' '),
                ))
            open_visits = plan.visit_ids.filtered(
                lambda v: v.state in ('pending', 'in_progress'))
            if open_visits and not force:
                raise UserError(_(
                    "Route %(route)s still has %(count)s pending or in-progress "
                    "visit(s). Close them first or use Force Complete.",
                    route=plan.name,
                    count=len(open_visits),
                ))
            if open_visits and force:
                if not plan._is_manager():
                    raise UserError(_("Only distribution managers may force "
                                      "complete a route."))
                if not reason:
                    raise UserError(_("A reason is required to force complete "
                                      "a route."))
                for visit in open_visits:
                    visit.action_skip_visit(reason)
            plan.write({
                'state': 'completed',
                'actual_end_datetime': fields.Datetime.now(),
            })
            plan.message_post(body=_("Route completed."))
        return True

    def action_force_complete_route(self):
        """Button entry point: opens the force-complete wizard."""
        self.ensure_one()
        if not self._is_manager():
            raise UserError(_("Only distribution managers may force complete "
                              "a route."))
        return {
            'type': 'ir.actions.act_window',
            'name': _('Force Complete Route'),
            'res_model': 'distribution.route.force.complete.wizard',
            'view_mode': 'form',
            'target': 'new',
            'context': {'default_route_id': self.id},
        }

    def action_cancel_route(self, reason=None):
        for plan in self:
            if plan.state == 'cancelled':
                raise UserError(_("Route %(route)s is already cancelled.",
                                  route=plan.name))
            if reason is None:
                raise UserError(_("A cancellation reason is required."))
            plan.write({
                'state': 'cancelled',
                'cancellation_reason': reason,
            })
            plan.message_post(body=_("Route cancelled: %s", reason))
        return True

    def action_cancel_route_wizard(self):
        self.ensure_one()
        return {
            'type': 'ir.actions.act_window',
            'name': _('Cancel Route'),
            'res_model': 'distribution.route.cancel.wizard',
            'view_mode': 'form',
            'target': 'new',
            'context': {'default_route_id': self.id},
        }

    def action_reopen_draft(self):
        """Manager-only: bring a cancelled route back to draft for rework."""
        self.ensure_one()
        if not self._is_manager():
            raise UserError(_("Only distribution managers may reopen a "
                              "cancelled route."))
        if self.state != 'cancelled':
            raise UserError(_("Only cancelled routes can be reopened."))
        self.write({
            'state': 'draft',
            'cancellation_reason': False,
            'actual_start_datetime': False,
            'actual_end_datetime': False,
        })
        self.message_post(body=_("Route reopened in draft."))
        return True

    # ------------------------------------------------------------------
    # Smart buttons
    # ------------------------------------------------------------------
    def action_view_visits(self):
        self.ensure_one()
        return {
            'type': 'ir.actions.act_window',
            'name': _('Route Visits'),
            'res_model': 'distribution.route.visit',
            'view_mode': 'list,form,calendar,kanban',
            'domain': [('route_id', '=', self.id)],
            'context': {'default_route_id': self.id},
        }
