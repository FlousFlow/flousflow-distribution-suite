# -*- coding: utf-8 -*-
"""Sale Order ↔ Distribution Visit integration — standard sale.order only.
Fields are STORED snapshots: confirming a quotation later never loses the
route/visit/employee/vehicle link even if assignments change (spec #14)."""
from odoo import _, api, fields, models
from odoo.exceptions import ValidationError

GROUP_ROUTE_MANAGER = (
    'flousflow_distribution_route_base.group_distribution_route_manager')


class SaleOrder(models.Model):
    _inherit = 'sale.order'

    distribution_route_id = fields.Many2one(
        'distribution.route.plan', string='Distribution Route',
        index=True, copy=False, check_company=True, tracking=True,
        domain="[('company_id', '=', company_id)]")
    distribution_visit_id = fields.Many2one(
        'distribution.route.visit', string='Distribution Visit',
        index=True, copy=False, check_company=True, tracking=True,
        readonly=True,
        help="Visit this sale was created from (explicit link, never "
             "guessed from customer or date).")
    distribution_employee_id = fields.Many2one(
        'hr.employee', string='Distribution Employee', index=True,
        copy=False, readonly=True, tracking=True)
    distribution_vehicle_id = fields.Many2one(
        'fleet.vehicle', string='Distribution Vehicle', index=True,
        copy=False, readonly=True, tracking=True,
        help="Historical vehicle snapshot taken when the sale was created "
             "from the visit.")

    @api.constrains('distribution_visit_id', 'company_id',
                    'distribution_route_id')
    def _check_distribution_visit_consistency(self):
        """Hard data-integrity checks (spec #10). NOTE: Odoo 19 runs
        @api.constrains as sudo, so permission-dependent logic (the
        manager override on the customer rule) lives in the explicit
        create/write overrides below — env.su inside a constrains is
        always True."""
        for order in self:
            visit = order.distribution_visit_id
            if not visit:
                continue
            if order.company_id != visit.company_id:
                raise ValidationError(_(
                    "The sale order company does not match the visit "
                    "company."))
            if order.distribution_route_id and \
                    order.distribution_route_id != visit.route_id:
                raise ValidationError(_(
                    "The sale order route does not match the visit route."))

    # ------------------------------------------------------------------
    # Customer-mismatch guard with manager override (spec #10).
    # Implemented in create/write (NOT constrains) because v19 constrains
    # always run as sudo — the real caller's identity would be lost.
    # ------------------------------------------------------------------
    def _check_visit_customer_permission(self, vals):
        if not ('partner_id' in vals or 'distribution_visit_id' in vals):
            return
        is_manager = self.env.su or \
            self.env.user.has_group(GROUP_ROUTE_MANAGER)
        for order in self:
            visit = order.distribution_visit_id
            if not visit or not order.partner_id:
                continue
            if order.partner_id.commercial_partner_id != \
                    visit.partner_id.commercial_partner_id \
                    and not is_manager:
                raise ValidationError(_(
                    "The sale order customer (%(customer)s) does not match "
                    "the visit customer (%(visit_customer)s). Only "
                    "distribution managers may override this.",
                    customer=order.partner_id.display_name,
                    visit_customer=visit.partner_id.display_name))

    @api.model_create_multi
    def create(self, vals_list):
        orders = super().create(vals_list)
        orders._check_visit_customer_permission({})
        return orders

    def write(self, vals):
        res = super().write(vals)
        self._check_visit_customer_permission(vals)
        return res

    @api.onchange('distribution_visit_id')
    def _onchange_distribution_visit_id(self):
        for order in self:
            if order.distribution_visit_id:
                visit = order.distribution_visit_id
                order.partner_id = visit.partner_id
                order.distribution_route_id = visit.route_id
                order.distribution_employee_id = visit.employee_id

    def action_view_distribution_visit(self):
        self.ensure_one()
        return {
            'type': 'ir.actions.act_window',
            'name': _('Distribution Visit'),
            'res_model': 'distribution.route.visit',
            'res_id': self.distribution_visit_id.id,
            'views': [(False, 'form')],
            'target': 'current',
        }
