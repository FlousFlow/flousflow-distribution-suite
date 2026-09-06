# -*- coding: utf-8 -*-
"""Route Plan ↔ Vehicle Integration.

Resolves the representative's active vehicle assignment (employee + route
date) and freezes a HISTORICAL SNAPSHOT (vehicle, vehicle warehouse, vehicle
POS) on the route at confirm time. Later assignment or configuration changes
never alter confirmed routes.
"""
from odoo import _, api, fields, models
from odoo.exceptions import UserError

GROUP_ROUTE_MANAGER = (
    'flousflow_distribution_route_base.group_distribution_route_manager')

# Snapshot fields: frozen after confirm (managers may still adjust them
# while the route is merely 'confirmed', nobody once it started).
VEHICLE_SNAPSHOT_FIELDS = (
    'vehicle_assignment_id',
    'vehicle_id',
    'vehicle_warehouse_id',
    'vehicle_pos_config_id',
)


class DistributionRoutePlan(models.Model):
    _inherit = 'distribution.route.plan'

    # -- Vehicle snapshot fields (plain stored m2o, NOT related) ----------
    vehicle_assignment_id = fields.Many2one(
        'fleet.vehicle.employee.assignment',
        string='Vehicle Assignment',
        index=True, tracking=True, copy=False, check_company=True,
        domain="[('employee_id', '=', employee_id), "
               "('company_id', '=', company_id)]",
        help="The vehicle assignment this route was planned against. "
             "Resolved automatically from the employee and the route date.")
    vehicle_id = fields.Many2one(
        'fleet.vehicle',
        string='Route Vehicle',
        index=True, tracking=True, copy=False, check_company=True,
        domain="[('is_distribution_vehicle', '=', True), "
               "('company_id', '=', company_id)]",
        help="Vehicle the representative operates during this route. "
             "Snapshotted at confirm and kept for history.")
    vehicle_warehouse_id = fields.Many2one(
        'stock.warehouse',
        string='Vehicle Warehouse',
        index=True, copy=False, check_company=True,
        help="Dedicated warehouse of the route vehicle (snapshot).")
    vehicle_pos_config_id = fields.Many2one(
        'pos.config',
        string='Vehicle POS',
        index=True, copy=False, check_company=True,
        help="POS configuration of the route vehicle (snapshot).")

    # -- Resolution warnings (UI only) ------------------------------------
    multiple_vehicle_assignments = fields.Boolean(
        compute='_compute_vehicle_resolution',
        string='Multiple Vehicle Assignments')
    no_vehicle_assignment = fields.Boolean(
        compute='_compute_vehicle_resolution',
        string='No Vehicle Assignment')

    # ------------------------------------------------------------------
    # Compute
    # ------------------------------------------------------------------
    @api.depends('employee_id', 'date', 'company_id')
    def _compute_vehicle_resolution(self):
        for plan in self:
            if not plan.employee_id or not plan.date:
                plan.multiple_vehicle_assignments = False
                plan.no_vehicle_assignment = False
                continue
            assignments = plan._get_active_vehicle_assignment()
            plan.multiple_vehicle_assignments = len(assignments) > 1
            plan.no_vehicle_assignment = len(assignments) == 0

    # ------------------------------------------------------------------
    # Helpers — resolution (spec #6/#7) & future-module hooks (spec #21)
    # ------------------------------------------------------------------
    def _get_active_vehicle_assignment(self, employee_id=None, date=None):
        """Valid vehicle assignments for (employee, date, company).

        Validity: assignment covers the route date, the vehicle is an
        active distribution vehicle, and the assignment belongs to the
        route company.
        """
        self.ensure_one()
        employee_id = employee_id or self.employee_id.id
        date = date or self.date
        if not employee_id or not date:
            return self.env['fleet.vehicle.employee.assignment']
        return self.env['fleet.vehicle.employee.assignment'].with_company(
            self.company_id).search([
                ('employee_id', '=', employee_id),
                ('company_id', '=', self.company_id.id),
                ('date_from', '<=', date),
                ('date_to', '=', False),
                ('vehicle_id.is_distribution_vehicle', '=', True),
                ('vehicle_id.distribution_active', '=', True),
            ]) + self.env['fleet.vehicle.employee.assignment'].with_company(
                self.company_id).search([
                    ('employee_id', '=', employee_id),
                    ('company_id', '=', self.company_id.id),
                    ('date_from', '<=', date),
                    ('date_to', '!=', False),
                    ('date_to', '>=', date),
                    ('vehicle_id.is_distribution_vehicle', '=', True),
                    ('vehicle_id.distribution_active', '=', True),
                ])

    def _apply_vehicle_assignment(self, assignment):
        """Fill the snapshot fields from a chosen assignment."""
        self.ensure_one()
        vehicle = assignment.vehicle_id
        return self.write({
            'vehicle_assignment_id': assignment.id,
            'vehicle_id': vehicle.id,
            'vehicle_warehouse_id': vehicle.distribution_warehouse_id.id,
            'vehicle_pos_config_id': vehicle.distribution_pos_config_id.id,
        })

    def _resolve_vehicle_assignment(self, raise_on_ambiguity=False):
        """Auto-resolve assignment + vehicle + warehouse + POS.

        * Exactly one valid assignment  -> fill all snapshot fields.
        * Several valid assignments     -> clear the fields and, when
          ``raise_on_ambiguity``, raise a clear error asking the manager
          to choose (never pick one randomly).
        * No valid assignment           -> clear the fields.
        """
        for plan in self:
            if plan.state != 'draft':
                continue
            assignments = plan._get_active_vehicle_assignment()
            if len(assignments) == 1:
                plan._apply_vehicle_assignment(assignments)
            else:
                plan.write({f: False for f in VEHICLE_SNAPSHOT_FIELDS})
                if raise_on_ambiguity and len(assignments) > 1:
                    raise UserError(_(
                        "Employee '%(employee)s' has %(count)s valid vehicle "
                        "assignments on %(date)s. Choose the assignment in "
                        "the 'Vehicle & Distribution' section before "
                        "confirming the route.",
                        employee=plan.employee_id.sudo().name,
                        count=len(assignments),
                        date=plan.date,
                    ))
        return True

    # -- Future sales/collections hooks (spec #21) -------------------------
    def _get_route_vehicle(self):
        """Snapshot vehicle of this route (empty recordset if none)."""
        self.ensure_one()
        return self.vehicle_id

    def _get_route_vehicle_warehouse(self):
        """Snapshot vehicle warehouse of this route."""
        self.ensure_one()
        return self.vehicle_warehouse_id

    def _get_route_pos_config(self):
        """Snapshot vehicle POS of this route."""
        self.ensure_one()
        return self.vehicle_pos_config_id

    def _is_route_vehicle_manager(self):
        return self.env.su or self.env.user.has_group(GROUP_ROUTE_MANAGER)

    # ------------------------------------------------------------------
    # Onchange UX
    # ------------------------------------------------------------------
    @api.onchange('employee_id')
    def _onchange_employee_id_resolve_vehicle(self):
        self._resolve_vehicle_assignment()

    @api.onchange('date')
    def _onchange_date_resolve_vehicle(self):
        if self.state == 'draft':
            self._resolve_vehicle_assignment()

    @api.onchange('vehicle_assignment_id')
    def _onchange_vehicle_assignment_id(self):
        if self.vehicle_assignment_id:
            self._apply_vehicle_assignment(self.vehicle_assignment_id)
        elif self.state == 'draft':
            self.write({f: False for f in VEHICLE_SNAPSHOT_FIELDS})

    # ------------------------------------------------------------------
    # CRUD
    # ------------------------------------------------------------------
    @api.model_create_multi
    def create(self, vals_list):
        plans = super().create(vals_list)
        for plan, vals in zip(plans, vals_list):
            explicit = any(f in vals for f in VEHICLE_SNAPSHOT_FIELDS)
            if plan.state == 'draft' and not explicit:
                # Silent best-effort resolution; ambiguity/no-assignment is
                # surfaced in the UI and enforced again at confirm.
                plan._resolve_vehicle_assignment()
            elif plan.vehicle_assignment_id and not plan.vehicle_id:
                plan._apply_vehicle_assignment(plan.vehicle_assignment_id)
        return plans

    def write(self, vals):
        changed_snapshot = [f for f in VEHICLE_SNAPSHOT_FIELDS if f in vals]
        if changed_snapshot:
            for plan in self:
                if plan.state == 'draft':
                    continue
                if plan.state != 'confirmed' or not plan._is_route_vehicle_manager():
                    if plan.state == 'confirmed':
                        raise UserError(_(
                            "Only distribution managers may adjust the "
                            "vehicle data of confirmed route %(route)s.",
                            route=plan.name))
                    raise UserError(_(
                        "Route %(route)s is %(state)s: its vehicle, "
                        "warehouse and POS are a historical snapshot and "
                        "can no longer be changed.",
                        route=plan.name,
                        state=plan.state.replace('_', ' ')))
        res = super().write(vals)
        # A manually chosen assignment carries its vehicle snapshot with it.
        if 'vehicle_assignment_id' in vals and 'vehicle_id' not in vals:
            for plan in self:
                if plan.state == 'draft' and plan.vehicle_assignment_id \
                        and not plan.vehicle_id:
                    plan._apply_vehicle_assignment(plan.vehicle_assignment_id)
        # Draft: when the employee or the date changes, the previously
        # resolved snapshot no longer applies — re-resolve.
        if 'state' not in vals and ('employee_id' in vals or 'date' in vals):
            for plan in self:
                if plan.state == 'draft' and not any(
                        f in vals for f in VEHICLE_SNAPSHOT_FIELDS):
                    plan._resolve_vehicle_assignment()
        return res

    def copy(self, default=None):
        """Duplicated routes are fresh drafts: the old snapshot is never
        copied; the assignment is resolved again from employee + new date
        (spec #28)."""
        default = dict(default or {})
        default.update({f: False for f in VEHICLE_SNAPSHOT_FIELDS})
        new_plan = super().copy(default)
        new_plan._resolve_vehicle_assignment()
        return new_plan

    # ------------------------------------------------------------------
    # Workflow overrides
    # ------------------------------------------------------------------
    def action_confirm(self):
        self.ensure_one()
        self._check_vehicle_for_confirm()
        res = super().action_confirm()
        # Freeze the snapshot explicitly (values were resolved/validated
        # just before; this write is the audit trail).
        if self.vehicle_id:
            self.message_post(body=_(
                "Vehicle snapshot: %(vehicle)s | Warehouse: %(warehouse)s | "
                "POS: %(pos)s",
                vehicle=self.vehicle_id.name,
                warehouse=self.vehicle_warehouse_id.name or '—',
                pos=self.vehicle_pos_config_id.name or '—'))
        return res

    def _check_vehicle_for_confirm(self):
        """Validation at confirm (spec #11) + snapshot freeze (spec #12)."""
        self.ensure_one()
        require_vehicle = self.company_id.distribution_require_vehicle_on_route
        require_pos = self.company_id.distribution_require_vehicle_pos_on_route

        if not self.vehicle_id:
            if self.vehicle_assignment_id:
                # The manager picked an assignment manually — apply it.
                self._apply_vehicle_assignment(self.vehicle_assignment_id)
            assignments = self._get_active_vehicle_assignment()
            if len(assignments) == 1:
                self._apply_vehicle_assignment(assignments)
            elif len(assignments) > 1:
                raise UserError(_(
                    "Employee '%(employee)s' has %(count)s valid vehicle "
                    "assignments on %(date)s. Choose the assignment in the "
                    "'Vehicle & Distribution' section before confirming.",
                    employee=self.employee_id.sudo().name,
                    count=len(assignments), date=self.date))
            elif require_vehicle:
                raise UserError(_(
                    "No active vehicle assignment found for '%(employee)s' "
                    "on %(date)s. Assign the employee to a distribution "
                    "vehicle first, or disable 'Require Vehicle on Route' "
                    "in the distribution settings.",
                    employee=self.employee_id.sudo().name, date=self.date))
            elif not require_vehicle:
                return  # route without vehicle explicitly allowed

        if self.vehicle_id:
            vehicle = self.vehicle_id
            if not vehicle.is_distribution_vehicle:
                raise UserError(_(
                    "Vehicle '%(vehicle)s' is not a distribution vehicle.",
                    vehicle=vehicle.name))
            if not vehicle.distribution_active:
                raise UserError(_(
                    "Vehicle '%(vehicle)s' is not distribution active.",
                    vehicle=vehicle.name))
            if not vehicle.distribution_warehouse_id:
                raise UserError(_(
                    "Vehicle '%(vehicle)s' has no dedicated warehouse. "
                    "Configure it before confirming the route.",
                    vehicle=vehicle.name))
            if require_pos and not vehicle.distribution_pos_config_id:
                raise UserError(_(
                    "Vehicle '%(vehicle)s' has no POS configuration. "
                    "Configure it before confirming the route.",
                    vehicle=vehicle.name))
            # Sync the snapshot with the vehicle's current configuration,
            # then freeze.
            self.write({
                'vehicle_warehouse_id':
                    vehicle.distribution_warehouse_id.id,
                'vehicle_pos_config_id':
                    vehicle.distribution_pos_config_id.id,
            })
            if self.vehicle_assignment_id:
                self._validate_assignment_snapshot()
            # Company consistency: vehicle/warehouse/POS vs route company.
            for field_name in ('vehicle_id', 'vehicle_warehouse_id',
                               'vehicle_pos_config_id'):
                record = self[field_name]
                if record and record.company_id != self.company_id:
                    raise UserError(_(
                        "'%(record)s' does not belong to the route company "
                        "'%(company)s'.",
                        record=record.display_name,
                        company=self.company_id.name))

    def _validate_assignment_snapshot(self):
        """The assignment on the route must match the route and vehicle."""
        self.ensure_one()
        assignment = self.vehicle_assignment_id
        if assignment.vehicle_id != self.vehicle_id:
            raise UserError(_(
                "The vehicle assignment does not match the route vehicle."))
        if assignment.employee_id != self.employee_id:
            raise UserError(_(
                "The vehicle assignment does not belong to the route "
                "employee."))
        if assignment.date_from > self.date or (
                assignment.date_to and assignment.date_to < self.date):
            raise UserError(_(
                "The vehicle assignment does not cover the route date "
                "%(date)s.", date=self.date))
        if assignment.company_id != self.company_id:
            raise UserError(_(
                "The vehicle assignment does not belong to the route "
                "company."))

    def action_start_route(self):
        self.ensure_one()
        self._check_vehicle_for_start()
        return super().action_start_route()

    def _check_vehicle_for_start(self):
        """Re-validate current operability at start (spec #14) and block
        concurrent employee/vehicle routes (spec #24/#25).

        NOTE: the snapshot is NOT re-resolved. If the assignment was closed
        between confirm and start the route keeps its historical vehicle.
        """
        self.ensure_one()
        if self.vehicle_id:
            vehicle = self.vehicle_id
            if not vehicle.distribution_active:
                raise UserError(_(
                    "Vehicle '%(vehicle)s' is not distribution active "
                    "anymore. The route cannot start.",
                    vehicle=vehicle.name))
            if not vehicle.distribution_warehouse_id:
                raise UserError(_(
                    "Vehicle '%(vehicle)s' lost its dedicated warehouse. "
                    "The route cannot start.", vehicle=vehicle.name))
            if (self.company_id.distribution_require_vehicle_pos_on_route
                    and not vehicle.distribution_pos_config_id):
                raise UserError(_(
                    "Vehicle '%(vehicle)s' has no POS configuration. "
                    "The route cannot start.", vehicle=vehicle.name))
            employee_conflict = self.search([
                ('id', '!=', self.id),
                ('employee_id', '=', self.employee_id.id),
                ('state', '=', 'in_progress'),
                ('company_id', '=', self.company_id.id),
            ], limit=1)
            if employee_conflict:
                raise UserError(_(
                    "Employee '%(employee)s' already has route "
                    "'%(conflict)s' in progress. One route in progress per "
                    "employee is allowed.",
                    employee=self.employee_id.sudo().name,
                    conflict=employee_conflict.name))
            vehicle_conflict = self.search([
                ('id', '!=', self.id),
                ('vehicle_id', '=', self.vehicle_id.id),
                ('state', '=', 'in_progress'),
            ], limit=1)
            if vehicle_conflict:
                raise UserError(_(
                    "Vehicle '%(vehicle)s' is already operating route "
                    "'%(conflict)s' in progress. A vehicle cannot run two "
                    "routes at the same time.",
                    vehicle=self.vehicle_id.name,
                    conflict=vehicle_conflict.name))

    # ------------------------------------------------------------------
    # Smart buttons (spec #19)
    # ------------------------------------------------------------------
    def action_view_route_vehicle_stock(self):
        self.ensure_one()
        if not self.vehicle_warehouse_id:
            raise UserError(_("This route has no vehicle / vehicle "
                              "warehouse."))
        warehouse = self.vehicle_warehouse_id
        return {
            'type': 'ir.actions.act_window',
            'name': _('Vehicle Stock (%s)', warehouse.name),
            'res_model': 'stock.quant',
            'view_mode': 'list,form',
            'domain': [
                ('location_id', 'in',
                 warehouse.lot_stock_id.child_internal_location_ids.ids +
                 [warehouse.lot_stock_id.id]),
                ('quantity', '!=', 0),
            ],
            'context': {
                'search_default_internal_loc': 1,
                'group_by': ['product_id', 'location_id', 'lot_id'],
            },
        }

    def action_view_route_pos_orders(self):
        """POS orders of the route vehicle (historical snapshot), limited
        to the route date. POS orders are NOT linked to the route record —
        the query goes through the order's own vehicle snapshot."""
        self.ensure_one()
        if not self.vehicle_id:
            raise UserError(_("This route has no vehicle."))
        date_start = fields.Datetime.to_datetime(
            fields.Date.to_date(self.date))
        date_end = date_start.replace(hour=23, minute=59, second=59)
        return {
            'type': 'ir.actions.act_window',
            'name': _('Route POS Orders (%s)', self.vehicle_id.name),
            'res_model': 'pos.order',
            'view_mode': 'list,form',
            'domain': [
                ('distribution_vehicle_id', '=', self.vehicle_id.id),
                ('date_order', '>=', fields.Datetime.to_string(date_start)),
                ('date_order', '<=', fields.Datetime.to_string(date_end)),
            ],
            'context': {},
        }
