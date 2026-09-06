# -*- coding: utf-8 -*-
from odoo import _, api, fields, models
from odoo.exceptions import UserError

GROUP_VEHICLE_MANAGER = (
    'flousflow_distribution_vehicle.group_distribution_vehicle_manager')


class PosOrder(models.Model):
    _inherit = 'pos.order'

    # Historical snapshots (#36/#37): stored once at creation, never
    # derived from the vehicle's *current* configuration.
    distribution_vehicle_id = fields.Many2one(
        'fleet.vehicle', string='Distribution Vehicle',
        index=True, readonly=True, copy=False,
        help="Vehicle linked to the POS session when the order was "
             "created (historical snapshot).")
    distribution_warehouse_id = fields.Many2one(
        'stock.warehouse', string='Distribution Warehouse',
        index=True, readonly=True, copy=False,
        help="Vehicle warehouse used by this order (historical snapshot).")

    # ------------------------------------------------------------------
    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            session_id = vals.get('session_id')
            if not session_id:
                continue
            session = self.env['pos.session'].browse(session_id)
            vehicle = session.config_id.distribution_vehicle_id
            if not vehicle or not vehicle.distribution_active:
                continue
            # Historical snapshot — independent from future reassignments.
            vals.setdefault('distribution_vehicle_id', vehicle.id)
            vals.setdefault(
                'distribution_warehouse_id',
                vehicle.distribution_warehouse_id.id)
            self._check_vehicle_order_authorization(vehicle)
            if vals.get('distribution_warehouse_id'):
                self._check_vehicle_stock_availability(
                    vehicle, vals.get('lines'))
        return super().create(vals_list)

    # ------------------------------------------------------------------
    def _check_vehicle_order_authorization(self, vehicle):
        """The cashier must be assigned to the vehicle (or be a
        distribution vehicle manager)."""
        if self.env.su or self.env.user.has_group(GROUP_VEHICLE_MANAGER):
            return
        assigned = vehicle.sudo().distribution_employee_ids
        if any(a.user_id and a.user_id.id == self.env.user.id
               for a in assigned):
            return
        # Fallback: an employee of the user is assigned to the vehicle.
        if any(e.id in assigned.ids for e in self.env.user.employee_ids):
            return
        raise UserError(_(
            "You are not assigned to vehicle '%(vehicle)s' — this POS "
            "cannot be used. Your vehicle: %(own)s.",
            vehicle=vehicle.name,
            own=self.env.user.employee_ids[:1]
            .current_distribution_vehicle_id.name or _('none')))

    def _check_vehicle_stock_availability(self, vehicle, lines_command):
        """Block selling more than the vehicle holds (unless allowed)."""
        icp = self.env['ir.config_parameter'].sudo()
        if icp.get_param('distribution_vehicle.allow_negative_stock'):
            return
        location = vehicle.distribution_warehouse_id.lot_stock_id
        needed = {}
        for command in (lines_command or []):
            if command[0] not in (0, 1) or not isinstance(command[2], dict):
                continue
            line_vals = command[2]
            product_id = line_vals.get('product_id')
            qty = line_vals.get('qty', 0) or 0
            if product_id and qty > 0:
                needed[product_id] = needed.get(product_id, 0.0) + qty
        if not needed:
            return
        quants = self.env['stock.quant'].sudo().read_group(
            [('product_id', 'in', list(needed)),
             ('location_id', '=', location.id)],
            ['quantity:sum'], ['product_id'])
        available = {
            q['product_id'][0]: q['quantity'] for q in quants}
        for product_id, qty in needed.items():
            product = self.env['product.product'].browse(product_id)
            if product.type != 'consu' or not product.is_storable:
                continue
            if qty > available.get(product_id, 0.0):
                raise UserError(_(
                    "Not enough stock in vehicle '%(vehicle)s' for "
                    "'%(product)s' (available: %(available).2f, needed: "
                    "%(needed).2f). Enable 'Allow Vehicle Negative Stock' "
                    "or load the vehicle first.",
                    vehicle=vehicle.name,
                    product=product.display_name,
                    available=available.get(product_id, 0.0),
                    needed=qty))
