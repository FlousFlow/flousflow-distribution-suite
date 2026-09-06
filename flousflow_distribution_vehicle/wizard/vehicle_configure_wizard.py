# -*- coding: utf-8 -*-
"""Configure Distribution Vehicle wizard: dedicated warehouse + POS +
employee assignments, with create-or-reuse options."""
from odoo import _, api, fields, models
from odoo.exceptions import UserError


class DistributionVehicleConfigureWizard(models.TransientModel):
    _name = 'distribution.vehicle.configure.wizard'
    _description = 'Configure Distribution Vehicle Wizard'
    _check_company_auto = True

    vehicle_id = fields.Many2one(
        'fleet.vehicle', string='Vehicle', required=True, check_company=True)
    company_id = fields.Many2one('res.company', string='Company',
                                 required=True)
    main_warehouse_id = fields.Many2one(
        'stock.warehouse', string='Main Loading Warehouse',
        required=True, check_company=True,
        domain="[('company_id', '=', company_id)]",
        help="Warehouse from which this vehicle will be loaded.")
    activate = fields.Boolean(
        string='Activate Distribution', default=True,
        help="Mark the vehicle as an active distribution vehicle.")

    # -- Warehouse ---------------------------------------------------------
    warehouse_mode = fields.Selection(
        selection=[
            ('create_new', 'Create New Vehicle Warehouse'),
            ('use_existing', 'Use Existing Warehouse'),
        ],
        string='Warehouse', required=True, default='create_new')
    new_warehouse_name = fields.Char(
        string='Warehouse Name',
        help="Leave empty to auto-generate from the vehicle.")
    existing_warehouse_id = fields.Many2one(
        'stock.warehouse', string='Warehouse', check_company=True,
        domain="[('company_id', '=', company_id)]")

    # -- POS -----------------------------------------------------------------
    pos_mode = fields.Selection(
        selection=[
            ('create_new', 'Create New POS'),
            ('use_existing', 'Use Existing POS'),
            ('none', 'No POS Now'),
        ],
        string='POS Configuration', required=True, default='create_new')
    new_pos_name = fields.Char(
        string='POS Name', help="Leave empty to auto-generate.")
    existing_pos_config_id = fields.Many2one(
        'pos.config', string='POS Configuration', check_company=True,
        domain="[('company_id', '=', company_id)]")

    # -- Employees -------------------------------------------------------------
    assignment_ids = fields.One2many(
        'distribution.vehicle.assignment.line', 'wizard_id',
        string='Employee Assignments')

    # ------------------------------------------------------------------
    @api.onchange('vehicle_id')
    def _onchange_vehicle_id(self):
        if self.vehicle_id:
            self.company_id = self.vehicle_id.company_id
            self.main_warehouse_id = (
                self.vehicle_id.distribution_main_warehouse_id)
            self.activate = self.vehicle_id.distribution_active

    def _generate_warehouse_name(self):
        self.ensure_one()
        base = self.vehicle_id.name or _('Vehicle')
        name = "%s Warehouse" % base
        candidate, suffix = name, 1
        while self.env['stock.warehouse'].search_count(
                [('name', '=', candidate),
                 ('company_id', '=', self.company_id.id)]):
            suffix += 1
            candidate = "%s %d" % (name, suffix)
        return candidate

    def _generate_warehouse_code(self):
        self.ensure_one()
        base = (self.vehicle_id.license_plate or self.vehicle_id.name
                or 'VHC').upper()
        code = ''.join(ch for ch in base if ch.isalnum())[:6] or 'VHC'
        candidate, suffix = code, 1
        while self.env['stock.warehouse'].search_count(
                [('code', '=', candidate),
                 ('company_id', '=', self.company_id.id)]):
            suffix += 1
            candidate = "%s%02d" % (code[:4], suffix)
        return candidate

    def _generate_pos_name(self, warehouse):
        self.ensure_one()
        name = "POS %s" % warehouse.code
        candidate, suffix = name, 1
        while self.env['pos.config'].search_count(
                [('name', '=', candidate),
                 ('company_id', '=', self.company_id.id)]):
            suffix += 1
            candidate = "%s %d" % (name, suffix)
        return candidate

    def _create_cash_payment_method(self, pos_name):
        self.ensure_one()
        journal = self.env['account.journal'].create({
            'name': _('%(pos)s Cash', pos=pos_name),
            'type': 'cash',
            'code': self._generate_journal_code(),
            'company_id': self.company_id.id,
        })
        receivable = self.env['account.account'].search([
            ('account_type', '=', 'asset_receivable')], limit=1)
        return self.env['pos.payment.method'].create({
            'name': _('%(pos)s Cash', pos=pos_name),
            'journal_id': journal.id,
            'receivable_account_id': receivable.id,
            'company_id': self.company_id.id,
        })

    def _generate_journal_code(self):
        self.ensure_one()
        seq = self.env['account.journal'].search_count([]) + 1
        code = 'D%03d' % seq
        while self.env['account.journal'].search_count([('code', '=', code)]):
            seq += 1
            code = 'D%03d' % seq
        return code

    def _resolve_invoice_journal(self):
        journal = self.env['account.journal'].search([
            ('type', '=', 'sale'),
            ('company_id', '=', self.company_id.id),
        ], limit=1)
        if not journal:
            raise UserError(_(
                "No sales journal found for company '%(company)s'. "
                "Configure accounting first.",
                company=self.company_id.name))
        return journal

    # ------------------------------------------------------------------
    def action_confirm(self):
        self.ensure_one()
        vehicle = self.vehicle_id
        if not vehicle.is_distribution_vehicle:
            vehicle.is_distribution_vehicle = True

        # -- Warehouse ---------------------------------------------------------
        if self.warehouse_mode == 'create_new':
            warehouse = self.env['stock.warehouse'].create({
                'name': self.new_warehouse_name
                or self._generate_warehouse_name(),
                'code': self._generate_warehouse_code(),
                'company_id': self.company_id.id,
            })
        else:
            if not self.existing_warehouse_id:
                raise UserError(_("Select an existing warehouse."))
            warehouse = self.existing_warehouse_id
        vehicle.distribution_warehouse_id = warehouse

        # -- POS -----------------------------------------------------------------
        if self.pos_mode == 'create_new':
            pos_name = self.new_pos_name or self._generate_pos_name(warehouse)
            cash_pm = self._create_cash_payment_method(pos_name)
            pos_config = self.env['pos.config'].create({
                'name': pos_name,
                'warehouse_id': warehouse.id,
                'invoice_journal_id': self._resolve_invoice_journal().id,
                'payment_method_ids': [(6, 0, cash_pm.ids)],
            })
        elif self.pos_mode == 'use_existing':
            if not self.existing_pos_config_id:
                raise UserError(_("Select an existing POS configuration."))
            pos_config = self.existing_pos_config_id
            pos_config.warehouse_id = warehouse.id
        else:
            pos_config = self.env['pos.config']
        if pos_config:
            pos_config.distribution_vehicle_id = vehicle
            vehicle.distribution_pos_config_id = pos_config.id

        # -- Main warehouse & activation --------------------------------------
        vehicle.distribution_main_warehouse_id = self.main_warehouse_id
        if self.activate:
            vehicle.distribution_active = True

        # -- Employees -----------------------------------------------------------
        for line in self.assignment_ids:
            self.env['fleet.vehicle.employee.assignment'].create({
                'vehicle_id': vehicle.id,
                'employee_id': line.employee_id.id,
                'role': line.role,
                'date_from': line.date_from,
                'company_id': self.company_id.id,
                'notes': line.notes,
            })

        return {
            'type': 'ir.actions.act_window',
            'res_model': 'fleet.vehicle',
            'res_id': vehicle.id,
            'views': [(False, 'form')],
            'target': 'current',
        }


class DistributionVehicleAssignmentLine(models.TransientModel):
    _name = 'distribution.vehicle.assignment.line'
    _description = 'Distribution Vehicle Assignment Line (wizard)'

    wizard_id = fields.Many2one(
        'distribution.vehicle.configure.wizard', ondelete='cascade')
    employee_id = fields.Many2one(
        'hr.employee', string='Employee', required=True,
        domain="[('company_id', '=', parent.company_id)]")
    role = fields.Selection(
        selection=[
            ('driver', 'Driver'),
            ('sales_rep', 'Sales Representative'),
            ('helper', 'Helper'),
            ('supervisor', 'Supervisor'),
            ('other', 'Other'),
        ],
        string='Role', required=True, default='sales_rep')
    date_from = fields.Date(string='From', required=True,
                            default=fields.Date.context_today)
    notes = fields.Text(string='Notes')
