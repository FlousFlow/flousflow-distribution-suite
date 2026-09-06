# -*- coding: utf-8 -*-
from odoo import _, api, fields, models
from odoo.exceptions import UserError, ValidationError

GROUP_VEHICLE_MANAGER = 'flousflow_distribution_vehicle.group_distribution_vehicle_manager'


class FleetVehicle(models.Model):
    _inherit = 'fleet.vehicle'
    _check_company_auto = True

    # -- Distribution flags & configuration --------------------------------
    is_distribution_vehicle = fields.Boolean(
        string='Distribution Vehicle',
        help="This vehicle is used in distribution operations and gets a "
             "dedicated warehouse and POS.",
    )
    distribution_active = fields.Boolean(
        string='Distribution Active', default=False, tracking=True,
        help="Inactive vehicles keep their warehouse/POS and history but "
             "are excluded from operations and availability checks.")
    distribution_warehouse_id = fields.Many2one(
        'stock.warehouse', string='Vehicle Warehouse',
        index=True, tracking=True, copy=False,
        check_company=True, ondelete='restrict',
        domain="[('company_id', '=', company_id)]",
        help="Dedicated warehouse for this vehicle. All vehicle sales "
             "deduct from it. 1:1 with the vehicle.")
    distribution_main_warehouse_id = fields.Many2one(
        'stock.warehouse', string='Main Loading Warehouse',
        check_company=True, ondelete='restrict',
        domain="[('company_id', '=', company_id)]",
        help="Warehouse from which the vehicle is loaded (e.g. Cairo Main).")
    distribution_pos_config_id = fields.Many2one(
        'pos.config', string='Vehicle POS',
        index=True, tracking=True, copy=False,
        check_company=True, ondelete='restrict',
        domain="[('company_id', '=', company_id)]",
        help="POS configuration bound to the vehicle warehouse.")
    distribution_employee_assignment_ids = fields.One2many(
        'fleet.vehicle.employee.assignment', 'vehicle_id',
        string='Employee Assignments')
    distribution_employee_ids = fields.Many2many(
        'hr.employee', compute='_compute_distribution_employees',
        string='Current Employees', store=True,
        help="Employees with an open assignment on this vehicle.")
    current_salesman_id = fields.Many2one(
        'hr.employee', compute='_compute_current_employees',
        string='Current Salesman')
    current_driver_id = fields.Many2one(
        'hr.employee', compute='_compute_current_employees',
        string='Current Driver')

    distribution_status = fields.Selection(
        selection=[
            ('not_configured', 'Not Configured'),
            ('ready', 'Ready'),
            ('inactive', 'Inactive'),
        ],
        compute='_compute_distribution_status', string='Distribution Status')
    user_has_vehicle_manager = fields.Boolean(
        compute='_compute_user_has_vehicle_manager')

    def _compute_user_has_vehicle_manager(self):
        for vehicle in self:
            vehicle.user_has_vehicle_manager = self.env.user.has_group(
                GROUP_VEHICLE_MANAGER)

    _distribution_warehouse_check = models.Constraint(
        'CHECK (distribution_warehouse_id IS NULL OR '
        'distribution_warehouse_id != distribution_main_warehouse_id)',
        'The vehicle warehouse and the main loading warehouse must be '
        'different.',
    )

    # ------------------------------------------------------------------
    @api.depends('distribution_employee_assignment_ids.employee_id',
                 'distribution_employee_assignment_ids.date_to',
                 'distribution_employee_assignment_ids.role')
    def _compute_distribution_employees(self):
        for vehicle in self:
            employees = vehicle.distribution_employee_assignment_ids.filtered(
                lambda a: not a.date_to).mapped('employee_id')
            vehicle.distribution_employee_ids = employees

    @api.depends('distribution_employee_assignment_ids.role',
                 'distribution_employee_assignment_ids.date_to')
    def _compute_current_employees(self):
        for vehicle in self:
            open_assignments = vehicle.distribution_employee_assignment_ids \
                .filtered(lambda a: not a.date_to)
            vehicle.current_salesman_id = (
                open_assignments.filtered(
                    lambda a: a.role == 'sales_rep')[:1].employee_id)
            vehicle.current_driver_id = (
                open_assignments.filtered(
                    lambda a: a.role == 'driver')[:1].employee_id)

    @api.depends('is_distribution_vehicle', 'distribution_active',
                 'distribution_warehouse_id', 'distribution_pos_config_id')
    def _compute_distribution_status(self):
        for vehicle in self:
            if not vehicle.is_distribution_vehicle:
                vehicle.distribution_status = False
            elif not vehicle.distribution_active:
                vehicle.distribution_status = 'inactive'
            elif (vehicle.distribution_warehouse_id
                    and vehicle.distribution_pos_config_id):
                vehicle.distribution_status = 'ready'
            else:
                vehicle.distribution_status = 'not_configured'

    # ------------------------------------------------------------------
    # Constraints
    # ------------------------------------------------------------------
    @api.constrains('distribution_warehouse_id', 'distribution_active',
                    'is_distribution_vehicle')
    def _check_warehouse_unique(self):
        for vehicle in self.filtered(
                lambda v: v.is_distribution_vehicle
                and v.distribution_active and v.distribution_warehouse_id):
            other = self.env['fleet.vehicle'].search_count([
                ('id', '!=', vehicle.id),
                ('is_distribution_vehicle', '=', True),
                ('distribution_active', '=', True),
                ('distribution_warehouse_id', '=',
                 vehicle.distribution_warehouse_id.id),
            ])
            if other:
                raise ValidationError(_(
                    "The warehouse '%(warehouse)s' is already used by "
                    "another active distribution vehicle. Each active "
                    "vehicle needs its own dedicated warehouse.",
                    warehouse=vehicle.distribution_warehouse_id.display_name))

    @api.constrains('distribution_pos_config_id', 'distribution_active',
                    'is_distribution_vehicle')
    def _check_pos_unique(self):
        for vehicle in self.filtered(
                lambda v: v.is_distribution_vehicle
                and v.distribution_active and v.distribution_pos_config_id):
            other = self.env['fleet.vehicle'].search_count([
                ('id', '!=', vehicle.id),
                ('is_distribution_vehicle', '=', True),
                ('distribution_active', '=', True),
                ('distribution_pos_config_id', '=',
                 vehicle.distribution_pos_config_id.id),
            ])
            if other:
                raise ValidationError(_(
                    "The POS configuration '%(pos)s' is already used by "
                    "another active distribution vehicle.",
                    pos=vehicle.distribution_pos_config_id.name))

    @api.constrains('distribution_warehouse_id', 'distribution_main_warehouse_id',
                    'distribution_pos_config_id', 'company_id',
                    'is_distribution_vehicle')
    def _check_distribution_company(self):
        for vehicle in self.filtered('is_distribution_vehicle'):
            company = vehicle.company_id
            for field_name in ('distribution_warehouse_id',
                               'distribution_main_warehouse_id',
                               'distribution_pos_config_id'):
                record = vehicle[field_name]
                if record and record.company_id != company:
                    raise ValidationError(_(
                        "Cross-company relation is not allowed: "
                        "'%(record)s' does not belong to the company of "
                        "vehicle '%(vehicle)s'.",
                        record=record.display_name,
                        vehicle=vehicle.display_name))

    # ------------------------------------------------------------------
    # Guards
    # ------------------------------------------------------------------
    def write(self, vals):
        if 'distribution_warehouse_id' in vals:
            for vehicle in self:
                if vehicle.distribution_active and \
                        not self._is_vehicle_manager():
                    raise UserError(_(
                        "Only distribution vehicle managers may change the "
                        "vehicle warehouse."))
        if 'distribution_active' in vals:
            for vehicle in self:
                if vehicle.distribution_active and \
                        not self._is_vehicle_manager():
                    raise UserError(_(
                        "Only distribution vehicle managers may activate or "
                        "deactivate distribution vehicles."))
        return super().write(vals)

    @api.ondelete(at_uninstall=False)
    def _unlink_except_distribution_history(self):
        for vehicle in self:
            if vehicle.is_distribution_vehicle and (
                    vehicle.distribution_warehouse_id
                    or vehicle.distribution_employee_assignment_ids):
                raise UserError(_(
                    "Vehicle '%(vehicle)s' has distribution history "
                    "(warehouse / assignments). Archive it instead of "
                    "deleting it.", vehicle=vehicle.display_name))

    def _is_vehicle_manager(self):
        return self.env.su or self.env.user.has_group(GROUP_VEHICLE_MANAGER)

    # ------------------------------------------------------------------
    # Actions
    # ------------------------------------------------------------------
    def action_configure_distribution(self):
        self.ensure_one()
        return {
            'type': 'ir.actions.act_window',
            'name': _('Configure Distribution Vehicle'),
            'res_model': 'distribution.vehicle.configure.wizard',
            'view_mode': 'form',
            'views': [(False, 'form')],
            'target': 'new',
            'context': {
                'default_vehicle_id': self.id,
                'default_company_id': self.company_id.id,
            },
        }

    def action_view_distribution_warehouse(self):
        self.ensure_one()
        if not self.distribution_warehouse_id:
            raise UserError(_("This vehicle has no dedicated warehouse yet."))
        return {
            'type': 'ir.actions.act_window',
            'name': _('Vehicle Warehouse'),
            'res_model': 'stock.warehouse',
            'res_id': self.distribution_warehouse_id.id,
            'views': [(False, 'form')],
            'target': 'current',
        }

    def action_view_vehicle_stock(self):
        self.ensure_one()
        if not self.distribution_warehouse_id:
            raise UserError(_("This vehicle has no dedicated warehouse yet."))
        return {
            'type': 'ir.actions.act_window',
            'name': _('Vehicle Stock'),
            'res_model': 'stock.quant',
            'view_mode': 'list,form',
            'domain': [
                ('location_id', 'in',
                 self.distribution_warehouse_id.lot_stock_id.child_internal_location_ids.ids +
                 [self.distribution_warehouse_id.lot_stock_id.id]),
                ('quantity', '!=', 0),
            ],
            'context': {
                'search_default_internal_loc': 1,
                'group_by': ['product_id', 'location_id', 'lot_id'],
            },
        }

    def action_view_vehicle_pos(self):
        self.ensure_one()
        if not self.distribution_pos_config_id:
            raise UserError(_("This vehicle has no POS configuration yet."))
        return {
            'type': 'ir.actions.act_window',
            'name': _('Vehicle POS'),
            'res_model': 'pos.config',
            'res_id': self.distribution_pos_config_id.id,
            'views': [(False, 'form')],
            'target': 'current',
        }

    def action_view_vehicle_transfers(self):
        self.ensure_one()
        if not self.distribution_warehouse_id:
            raise UserError(_("This vehicle has no dedicated warehouse yet."))
        return {
            'type': 'ir.actions.act_window',
            'name': _('Vehicle Transfers'),
            'res_model': 'stock.picking',
            'view_mode': 'list,form',
            'domain': ['|',
                       ('location_dest_id', 'child_of',
                        [self.distribution_warehouse_id.view_location_id.id]),
                       ('location_id', 'child_of',
                        [self.distribution_warehouse_id.view_location_id.id])],
            'context': {'search_default_todo': 1},
        }

    def action_view_vehicle_employees(self):
        self.ensure_one()
        return {
            'type': 'ir.actions.act_window',
            'name': _('Employee Assignments'),
            'res_model': 'fleet.vehicle.employee.assignment',
            'view_mode': 'list,form',
            'domain': [('vehicle_id', '=', self.id)],
            'context': {'default_vehicle_id': self.id},
        }

    def action_load_vehicle(self):
        self.ensure_one()
        if not self.distribution_warehouse_id:
            raise UserError(_("Configure a vehicle warehouse first."))
        return {
            'type': 'ir.actions.act_window',
            'name': _('Load Vehicle'),
            'res_model': 'distribution.vehicle.transfer.wizard',
            'view_mode': 'form',
            'views': [(False, 'form')],
            'target': 'new',
            'context': {
                'default_vehicle_id': self.id,
                'default_direction': 'load',
                'default_source_warehouse_id':
                    self.distribution_main_warehouse_id.id,
            },
        }

    def action_unload_vehicle(self):
        self.ensure_one()
        if not self.distribution_warehouse_id:
            raise UserError(_("Configure a vehicle warehouse first."))
        return {
            'type': 'ir.actions.act_window',
            'name': _('Unload Vehicle'),
            'res_model': 'distribution.vehicle.transfer.wizard',
            'view_mode': 'form',
            'views': [(False, 'form')],
            'target': 'new',
            'context': {
                'default_vehicle_id': self.id,
                'default_direction': 'unload',
            },
        }
