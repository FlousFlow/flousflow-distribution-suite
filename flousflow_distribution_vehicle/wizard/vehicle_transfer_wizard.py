# -*- coding: utf-8 -*-
"""Load / Unload Vehicle wizard.

Creates a standard internal transfer between the main warehouse stock
location and the vehicle warehouse stock location (never direct quant
manipulation). The user only sees "Main Warehouse -> CAR-001".
"""
from odoo import _, api, fields, models
from odoo.exceptions import UserError


class DistributionVehicleTransferWizard(models.TransientModel):
    _name = 'distribution.vehicle.transfer.wizard'
    _description = 'Load / Unload Vehicle Wizard'
    _check_company_auto = True

    vehicle_id = fields.Many2one(
        'fleet.vehicle', string='Vehicle', required=True, check_company=True)
    company_id = fields.Many2one(
        'res.company', string='Company',
        related='vehicle_id.company_id')
    direction = fields.Selection(
        selection=[('load', 'Load'), ('unload', 'Unload')],
        required=True, default='load')
    source_warehouse_id = fields.Many2one(
        'stock.warehouse', string='Source Warehouse', check_company=True,
        domain="[('company_id', '=', company_id)]",
        help="Load: the main loading warehouse. "
             "Unload: the receiving warehouse (defaults to the main).")
    scheduled_date = fields.Datetime(
        string='Scheduled Date', default=fields.Datetime.now)
    responsible_employee_id = fields.Many2one(
        'hr.employee', string='Responsible Employee', check_company=True)
    notes = fields.Text(string='Notes')
    auto_validate = fields.Boolean(
        string='Validate Immediately',
        help="Validate the transfer right away instead of leaving it "
             "ready for the warehouse team.")
    line_ids = fields.One2many(
        'distribution.vehicle.transfer.line', 'wizard_id',
        string='Products', copy=True)

    # ------------------------------------------------------------------
    @api.onchange('vehicle_id')
    def _onchange_vehicle_id(self):
        if self.vehicle_id:
            if self.direction == 'load':
                self.source_warehouse_id = (
                    self.vehicle_id.distribution_main_warehouse_id)
            else:
                self.source_warehouse_id = (
                    self.vehicle_id.distribution_main_warehouse_id)

    def _get_locations(self):
        self.ensure_one()
        vehicle_wh = self.vehicle_id.distribution_warehouse_id
        if not vehicle_wh:
            raise UserError(_("Configure a vehicle warehouse first."))
        source_wh = self.source_warehouse_id
        if self.direction == 'load':
            src_loc = source_wh.lot_stock_id
            dest_loc = vehicle_wh.lot_stock_id
            picking_type = vehicle_wh.int_type_id
        else:
            src_loc = vehicle_wh.lot_stock_id
            dest_loc = source_wh.lot_stock_id
            picking_type = source_wh.int_type_id
        if not picking_type:
            raise UserError(_(
                "No internal transfer operation type found for warehouse "
                "'%s'.",
                vehicle_wh.name if self.direction == 'load'
                else source_wh.name))
        return src_loc, dest_loc, picking_type

    def action_confirm(self):
        self.ensure_one()
        if not self.line_ids:
            raise UserError(_("Add at least one product line."))
        src_loc, dest_loc, picking_type = self._get_locations()
        vehicle = self.vehicle_id

        move_vals = []
        for line in self.line_ids:
            qty = line.quantity
            if qty <= 0:
                raise UserError(_(
                    "Quantity must be positive for '%s'.",
                    line.product_id.display_name))
            if line.lot_id and line.lot_id.product_id != line.product_id:
                raise UserError(_(
                    "Lot '%s' does not belong to product '%s'.",
                    line.lot_id.name, line.product_id.display_name))
            move_vals.append((0, 0, {
                'product_id': line.product_id.id,
                'product_uom_qty': qty,
                'product_uom': line.product_uom_id.id,
                'location_id': src_loc.id,
                'location_dest_id': dest_loc.id,
                'move_line_ids': [(0, 0, {
                    'product_id': line.product_id.id,
                    'product_uom_id': line.product_uom_id.id,
                    'quantity': qty,
                    'lot_id': line.lot_id.id if line.lot_id else False,
                    'location_id': src_loc.id,
                    'location_dest_id': dest_loc.id,
                })],
            }))

        picking = self.env['stock.picking'].create({
            'name': '/',
            'picking_type_id': picking_type.id,
            'location_id': src_loc.id,
            'location_dest_id': dest_loc.id,
            'scheduled_date': self.scheduled_date,
            'origin': _('%(direction)s — %(vehicle)s',
                        direction=dict(self._fields['direction'].selection)
                        .get(self.direction),
                        vehicle=vehicle.name),
            'company_id': self.vehicle_id.company_id.id,
            'move_ids': move_vals,
        })
        picking.action_confirm()
        if self.auto_validate:
            picking.button_validate()

        if self.notes:
            picking.message_post(body=self.notes)
        if self.responsible_employee_id:
            picking.message_post(body=_(
                "Responsible employee: %s",
                self.responsible_employee_id.name))

        return {
            'type': 'ir.actions.act_window',
            'name': _('Vehicle Transfer'),
            'res_model': 'stock.picking',
            'res_id': picking.id,
            'views': [(False, 'form')],
            'target': 'current',
        }


class DistributionVehicleTransferLine(models.TransientModel):
    _name = 'distribution.vehicle.transfer.line'
    _description = 'Load / Unload Vehicle Wizard Line'

    wizard_id = fields.Many2one(
        'distribution.vehicle.transfer.wizard', ondelete='cascade',
        required=True)
    product_id = fields.Many2one(
        'product.product', string='Product', required=True,
        domain="[('type', '!=', 'service')]")
    product_uom_id = fields.Many2one(
        'uom.uom', string='UoM', related='product_id.uom_id')
    quantity = fields.Float(string='Quantity', default=1.0, required=True)
    lot_id = fields.Many2one(
        'stock.lot', string='Lot/Serial',
        domain="[('product_id', '=', product_id)]")
