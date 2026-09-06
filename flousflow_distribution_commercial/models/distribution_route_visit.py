# -*- coding: utf-8 -*-
"""Commercial extensions for Route Visits: sale orders, POS orders and
customer collections linked explicitly to the visit."""
from odoo import _, api, fields, models
from odoo.exceptions import UserError

GROUP_ROUTE_MANAGER = (
    'flousflow_distribution_route_base.group_distribution_route_manager')


class DistributionRouteVisit(models.Model):
    _inherit = 'distribution.route.visit'

    # -- Explicit commercial links -----------------------------------------
    sale_order_ids = fields.One2many(
        'sale.order', 'distribution_visit_id', string='Quotations & Sales')
    pos_order_ids = fields.One2many(
        'pos.order', 'distribution_visit_id', string='POS Orders')
    collection_ids = fields.One2many(
        'distribution.visit.collection', 'visit_id', string='Collections')

    sale_order_count = fields.Integer(
        compute='_compute_commercial', string='Quotations & Sales')
    pos_order_count = fields.Integer(
        compute='_compute_commercial', string='POS Orders')
    collection_count = fields.Integer(
        compute='_compute_commercial', string='Collections')

    quotation_amount_total = fields.Monetary(
        compute='_compute_commercial', string='Quotation Amount',
        currency_field='company_currency_id',
        help="Draft/sent quotations linked to this visit (not revenue yet).")
    confirmed_sale_amount_total = fields.Monetary(
        compute='_compute_commercial', string='Confirmed Sales Amount',
        currency_field='company_currency_id')
    pos_sales_amount_total = fields.Monetary(
        compute='_compute_commercial', string='POS Sales Amount (net)',
        currency_field='company_currency_id',
        help="Paid POS orders net of refunds. Cancelled orders excluded.")
    submitted_collection_amount = fields.Monetary(
        compute='_compute_commercial', string='Submitted Collections',
        currency_field='company_currency_id')
    validated_collection_amount = fields.Monetary(
        compute='_compute_commercial', string='Validated Collections',
        currency_field='company_currency_id')

    has_quotation = fields.Boolean(compute='_compute_commercial')
    has_confirmed_sale = fields.Boolean(compute='_compute_commercial')
    has_pos_sale = fields.Boolean(compute='_compute_commercial')
    has_submitted_collection = fields.Boolean(compute='_compute_commercial')
    has_validated_collection = fields.Boolean(compute='_compute_commercial')
    has_collection = fields.Boolean(compute='_compute_commercial')
    has_sale = fields.Boolean(compute='_compute_commercial')

    company_currency_id = fields.Many2one(
        related='company_id.currency_id', string='Company Currency')

    # ------------------------------------------------------------------
    def _compute_commercial(self):
        for visit in self:
            quotations = visit.sale_order_ids.filtered(
                lambda s: s.state in ('draft', 'sent'))
            confirmed = visit.sale_order_ids.filtered(
                lambda s: s.state == 'sale')
            pos_orders = visit.pos_order_ids.filtered(
                lambda o: o.state != 'cancel')
            submitted = visit.collection_ids.filtered(
                lambda c: c.state == 'submitted')
            validated = visit.collection_ids.filtered(
                lambda c: c.state == 'validated')
            visit.sale_order_count = len(visit.sale_order_ids)
            visit.pos_order_count = len(visit.pos_order_ids)
            visit.collection_count = len(visit.collection_ids)
            visit.quotation_amount_total = sum(quotations.mapped('amount_total'))
            visit.confirmed_sale_amount_total = sum(
                confirmed.mapped('amount_total'))
            visit.pos_sales_amount_total = sum(
                pos_orders.mapped('amount_total'))
            visit.submitted_collection_amount = sum(
                submitted.mapped('amount'))
            visit.validated_collection_amount = sum(
                validated.mapped('amount'))
            visit.has_quotation = bool(quotations)
            visit.has_confirmed_sale = bool(confirmed)
            visit.has_pos_sale = bool(pos_orders)
            visit.has_submitted_collection = bool(submitted)
            visit.has_validated_collection = bool(validated)
            visit.has_sale = bool(visit.sale_order_ids or visit.pos_order_ids)
            visit.has_collection = bool(visit.collection_ids)

    # ------------------------------------------------------------------
    # Access
    # ------------------------------------------------------------------
    def _can_manage_commercial(self):
        """Assigned employee's user or a distribution manager."""
        self.ensure_one()
        return self.env.su or self._is_manager() or \
            (self.user_id and self.user_id.id == self.env.uid)

    def _check_can_commercial(self):
        for visit in self:
            if not visit._can_manage_commercial():
                raise UserError(_(
                    "Only the assigned employee or a distribution manager "
                    "can run commercial actions on visit %(visit)s.",
                    visit=visit.display_name))

    # ------------------------------------------------------------------
    # Create Quotation from Visit (spec #11/#12)
    # ------------------------------------------------------------------
    def action_create_quotation(self):
        self.ensure_one()
        self._check_can_commercial()
        if not self.partner_id:
            raise UserError(_("This visit has no customer."))
        order = self.env['sale.order'].create({
            'partner_id': self.partner_id.id,
            'company_id': self.company_id.id,
            'distribution_route_id': self.route_id.id,
            'distribution_visit_id': self.id,
            'distribution_employee_id': self.employee_id.id,
            'distribution_vehicle_id': self.route_id.vehicle_id.id,
        })
        # keep commercial links consistent when Odoo fills defaults
        order.write({'distribution_route_id': self.route_id.id})
        return {
            'type': 'ir.actions.act_window',
            'name': _('Quotation'),
            'res_model': 'sale.order',
            'res_id': order.id,
            'views': [(False, 'form')],
            'target': 'current',
            'context': {'default_distribution_visit_id': self.id},
        }

    def action_view_quotations(self):
        self.ensure_one()
        return {
            'type': 'ir.actions.act_window',
            'name': _('Quotations'),
            'res_model': 'sale.order',
            'view_mode': 'list,form',
            'domain': [('distribution_visit_id', '=', self.id),
                       ('state', 'in', ('draft', 'sent'))],
            'context': {'default_distribution_visit_id': self.id},
        }

    def action_view_sale_orders(self):
        self.ensure_one()
        return {
            'type': 'ir.actions.act_window',
            'name': _('Sales Orders'),
            'res_model': 'sale.order',
            'view_mode': 'list,form',
            'domain': [('distribution_visit_id', '=', self.id),
                       ('state', '=', 'sale')],
            'context': {'default_distribution_visit_id': self.id},
        }

    def action_view_pos_orders(self):
        self.ensure_one()
        return {
            'type': 'ir.actions.act_window',
            'name': _('POS Orders'),
            'res_model': 'pos.order',
            'view_mode': 'list,form',
            'domain': [('distribution_visit_id', '=', self.id)],
            'context': {'default_distribution_visit_id': self.id},
        }

    def action_view_collections(self):
        self.ensure_one()
        return {
            'type': 'ir.actions.act_window',
            'name': _('Collections'),
            'res_model': 'distribution.visit.collection',
            'view_mode': 'list,form',
            'domain': [('visit_id', '=', self.id)],
            'context': {'default_visit_id': self.id},
        }

    # ------------------------------------------------------------------
    # Record Collection from Visit (spec #71)
    # ------------------------------------------------------------------
    def action_record_collection(self):
        self.ensure_one()
        self._check_can_commercial()
        if not self.partner_id:
            raise UserError(_("This visit has no customer."))
        collection = self.env['distribution.visit.collection'].create({
            'visit_id': self.id,
        })
        return {
            'type': 'ir.actions.act_window',
            'name': _('Record Collection'),
            'res_model': 'distribution.visit.collection',
            'res_id': collection.id,
            'views': [(False, 'form')],
            'target': 'current',
            'context': {'default_visit_id': self.id},
        }

    # ------------------------------------------------------------------
    # Start POS Sale from Visit (spec #19) — explicit visit context
    # ------------------------------------------------------------------
    def action_start_pos_sale(self):
        self.ensure_one()
        self._check_can_commercial()
        if not self.partner_id:
            raise UserError(_("This visit has no customer."))
        if self.route_state != 'in_progress':
            raise UserError(_(
                "Route %(route)s is not in progress. Start the route "
                "first.", route=self.route_id.name))
        if self.state not in ('pending', 'in_progress'):
            raise UserError(_("This visit is no longer open for sales."))
        config = self.route_id.vehicle_pos_config_id
        if not config:
            raise UserError(_(
                "The route vehicle has no POS configuration."))
        # Route snapshot POS is authoritative (#94) — the vehicle POS
        # enforcement module blocks orders from any other POS.
        config = config.sudo().with_context(
            keep_distribution_visit=True)
        config.distribution_visit_context_raw = self.id
        return config.open_ui()

    # ------------------------------------------------------------------
    # Commercial enforcement on completion (spec #75-#78)
    # ------------------------------------------------------------------
    def action_finalize_visit(self, result_id, result_notes=False,
                              employee_notes=False, failure_reason=False,
                              requires_revisit=False,
                              suggested_revisit_date=False):
        """Enforce optional commercial record policies before completion.
        An unsuccessful business result (e.g. customer refused to pay)
        always completes without any commercial record (#77/#78)."""
        for visit in self:
            visit._check_commercial_enforcement(result_id)
        return super().action_finalize_visit(
            result_id=result_id, result_notes=result_notes,
            employee_notes=employee_notes, failure_reason=failure_reason,
            requires_revisit=requires_revisit,
            suggested_revisit_date=suggested_revisit_date)

    def _check_commercial_enforcement(self, result_id):
        self.ensure_one()
        mode = self.company_id.commercial_validation_mode
        if mode == 'disabled' or not self.visit_type_id:
            return
        result = result_id if isinstance(result_id, models.BaseModel) else \
            self.env['distribution.visit.result'].browse(result_id or False)
        if result and result.is_success is False:
            # Business refusal: never force a commercial record.
            return
        vtype = self.visit_type_id
        needed = vtype.commercial_action_type
        if needed == 'none':
            return
        missing = []
        if needed in ('sale', 'sale_and_collection') and \
                not (self.has_quotation or self.has_confirmed_sale):
            if self.company_id.sales_visit_requires_commercial_record:
                missing.append(_('a quotation or confirmed sale'))
        if needed in ('collection', 'sale_and_collection') and \
                not (self.has_collection or self.has_submitted_collection):
            if self.company_id.collection_visit_requires_collection_record:
                missing.append(_('a recorded collection'))
        if not missing:
            return
        if mode == 'strict':
            raise UserError(_(
                "Visit %(visit)s cannot be completed: the visit type "
                "requires %(missing)s. If the customer refused, set an "
                "unsuccessful business result instead.",
                visit=self.display_name, missing=', '.join(missing)))
        self.message_post(body=_(
            "Commercial warning: this %(type)s visit was completed without "
            "%(missing)s.", type=vtype.name, missing=', '.join(missing)))
