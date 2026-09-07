from odoo import api, fields, models, _
from odoo.exceptions import ValidationError


class PosConfig(models.Model):
    """POS → Warehouse assignment.

    Every Point of Sale configuration is assigned to a warehouse. Odoo 19
    already routes every POS order through ``pos.config.picking_type_id`` — an
    outgoing operation type whose source location is the assigned warehouse's
    stock location (``stock.warehouse.pos_type_id``). This module makes the
    *warehouse* the primary, user-facing setting: the operation type is derived
    automatically from the assigned warehouse, so POS sales deduct inventory
    from that warehouse only, and returns go back to that same warehouse.
    """

    _inherit = 'pos.config'

    warehouse_source_location_id = fields.Many2one(
        'stock.location',
        string='Warehouse Source Location',
        related='picking_type_id.default_location_src_id',
        readonly=True,
        help='Stock location from which POS sales are deducted. '
             'Derived automatically from the assigned warehouse.',
    )

    # ------------------------------------------------------------------
    # Warehouse → operation type derivation
    # ------------------------------------------------------------------

    @api.model
    def _get_picking_type_for_warehouse(self, warehouse):
        """Return the POS operation type of ``warehouse``.

        Standard Odoo creates ``stock.warehouse.pos_type_id`` automatically for
        every warehouse. If it is missing (e.g. a warehouse created before the
        Point of Sale was installed) we create it on the fly, and raise a clear
        error if it still cannot be resolved.
        """
        if not warehouse:
            return self.env['stock.picking.type']
        if not warehouse.pos_type_id:
            warehouse._create_missing_pos_picking_types()
        if not warehouse.pos_type_id:
            raise ValidationError(_(
                "The warehouse assigned to this Point of Sale (%s) does not "
                "have a valid stock operation type.",
                warehouse.name,
            ))
        return warehouse.pos_type_id

    @api.onchange('warehouse_id')
    def _onchange_warehouse_id(self):
        """When the assigned warehouse changes, derive the operation type."""
        if self.warehouse_id:
            self.picking_type_id = self._get_picking_type_for_warehouse(self.warehouse_id)

    @api.model_create_multi
    def create(self, vals_list):
        # Keep the operation type in sync when the warehouse is provided at
        # creation time (API writes bypass the onchange).
        for vals in vals_list:
            if vals.get('warehouse_id'):
                warehouse = self.env['stock.warehouse'].browse(vals['warehouse_id'])
                vals['picking_type_id'] = self._get_picking_type_for_warehouse(warehouse).id
        return super().create(vals_list)

    def write(self, vals):
        # Keep the operation type in sync when the warehouse is written
        # directly. Because ``warehouse_id`` is a stored computed field
        # (dependent on ``picking_type_id``), a bare warehouse write would be
        # overwritten by the standard recompute; deriving the operation type
        # from the warehouse keeps both consistent.
        if vals.get('warehouse_id'):
            warehouse = self.env['stock.warehouse'].browse(vals['warehouse_id'])
            picking_type = self._get_picking_type_for_warehouse(warehouse)
            if picking_type:
                vals['picking_type_id'] = picking_type.id
        return super().write(vals)

    # ------------------------------------------------------------------
    # Validation
    # ------------------------------------------------------------------

    @api.constrains('warehouse_id', 'company_id')
    def _check_warehouse_company(self):
        for config in self:
            if config.warehouse_id and config.warehouse_id.company_id != config.company_id:
                raise ValidationError(_(
                    "The warehouse assigned to this Point of Sale (%(pos)s) "
                    "must belong to the same company as the Point of Sale.",
                    pos=config.name,
                ))

    # ------------------------------------------------------------------
    # Session consistency
    # ------------------------------------------------------------------

    def _get_forbidden_change_fields(self):
        """Block warehouse changes while a POS session is open so one session
        never creates stock moves from two different warehouses."""
        return super()._get_forbidden_change_fields() + ['warehouse_id', 'picking_type_id']
