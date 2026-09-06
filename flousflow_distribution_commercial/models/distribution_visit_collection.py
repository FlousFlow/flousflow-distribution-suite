# -*- coding: utf-8 -*-
"""Operational Customer Collection for Route Visits.

The salesman records "I received an amount". Accounting keeps an INDEPENDENT
control: journal, accounting date, invoice allocation and posting are done by
an accounting-capable validator through STANDARD Odoo payment logic
(account.payment + standard reconciliation). Operational Collection
≠ Posted Accounting Payment until validated.

No sudo accounting bypass: validating requires real account payment rights.
"""
from odoo import _, api, fields, models
from odoo.exceptions import UserError, ValidationError

GROUP_ACCOUNT_BILLING = 'account.group_account_invoice'

COLLECTION_METHODS = [
    ('cash', 'Cash'),
    ('bank_transfer', 'Bank Transfer'),
    ('cheque', 'Cheque'),
    ('other', 'Other'),
]


class DistributionVisitCollection(models.Model):
    _name = 'distribution.visit.collection'
    _description = 'Distribution Visit Collection'
    _inherit = ['mail.thread', 'mail.activity.mixin']
    _order = 'collection_date desc, id desc'
    _check_company_auto = True

    # Locked once the collection leaves draft (spec #33/#56).
    FINANCIAL_FIELDS = (
        'amount', 'collection_method', 'journal_id', 'payment_method_line_id',
        'invoice_ids', 'payment_reference', 'customer_reference',
    )

    name = fields.Char(
        string='Reference', required=True, copy=False, readonly=True,
        index=True, default=lambda self: _('New'))
    state = fields.Selection(
        selection=[
            ('draft', 'Draft'),
            ('submitted', 'Submitted'),
            ('validated', 'Validated'),
            ('rejected', 'Rejected'),
            ('cancelled', 'Cancelled'),
        ],
        string='Status', default='draft', required=True,
        index=True, copy=False, tracking=True)

    visit_id = fields.Many2one(
        'distribution.route.visit', string='Visit', required=True,
        index=True, check_company=True, ondelete='restrict',
        domain="[('partner_id', '!=', False)]")
    route_id = fields.Many2one(
        related='visit_id.route_id', store=True, index=True,
        string='Route Plan')
    partner_id = fields.Many2one(
        related='visit_id.partner_id', store=True, index=True,
        string='Customer')
    employee_id = fields.Many2one(
        related='visit_id.employee_id', store=True, index=True,
        string='Employee')
    company_id = fields.Many2one(
        related='visit_id.company_id', store=True, index=True,
        string='Company')
    currency_id = fields.Many2one(
        related='company_id.currency_id', store=True, string='Currency')

    amount = fields.Monetary(string='Amount', required=True, tracking=True,
                             currency_field='currency_id', default=1.0)
    collection_date = fields.Datetime(
        string='Collection Date', default=fields.Datetime.now(),
        required=True, tracking=True)

    # Operational classification ONLY — not a replacement for
    # account.payment.method.line (spec #27).
    collection_method = fields.Selection(
        selection=COLLECTION_METHODS, string='Collection Method',
        required=True, default='cash', tracking=True)

    # Accounting control (validator side)
    journal_id = fields.Many2one(
        'account.journal', string='Payment Journal', check_company=True,
        domain="[('type', 'in', ('bank', 'cash')), ('company_id', '=', company_id)]")
    payment_method_line_id = fields.Many2one(
        'account.payment.method.line', string='Payment Method Line',
        domain="[('journal_id', '=', journal_id), "
               "('payment_method_id.payment_type', '=', 'inbound')]")
    payment_reference = fields.Char(string='Payment Reference')
    customer_reference = fields.Char(string='Customer Reference')
    notes = fields.Text(string='Notes & Evidence Notes')
    invoice_ids = fields.Many2many(
        'account.move', 'distribution_collection_invoice_rel',
        'collection_id', 'move_id', string='Customer Invoices',
        check_company=True, copy=False,
        domain="[('move_type', '=', 'out_invoice'), ('state', '=', 'posted'), "
               "('partner_id', '=', partner_id), "
               "('payment_state', 'in', ('not_paid', 'partial'))]")
    accounting_date = fields.Date(
        string='Accounting Date', copy=False,
        help="Set by the accounting validator according to the accounting "
             "period. The salesman cannot change it.")
    payment_id = fields.Many2one(
        'account.payment', string='Payment', readonly=True, copy=False,
        check_company=True)
    payment_state = fields.Selection(
        compute='_compute_payment_state', string='Accounting Status',
        selection=[
            ('not_created', 'Not Created'),
            ('draft', 'Draft'),
            ('posted', 'Posted'),
            ('cancelled', 'Cancelled'),
        ])

    rejection_reason = fields.Text(string='Rejection Reason', copy=False,
                                   readonly=True, tracking=True)
    rejected_by = fields.Many2one('res.users', string='Rejected By',
                                  readonly=True, copy=False)
    rejected_datetime = fields.Datetime(string='Rejected On', readonly=True,
                                        copy=False)

    _amount_check = models.Constraint(
        'CHECK (amount > 0)',
        'The collection amount must be strictly positive. If the customer '
        'did not pay, use the visit result instead of a zero collection.')

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            if not vals.get('name') or vals['name'] == _('New'):
                vals['name'] = self.env['ir.sequence'].next_by_code(
                    'distribution.visit.collection') or _('New')
        return super().create(vals_list)

    # ------------------------------------------------------------------
    @api.depends('payment_id.state')
    def _compute_payment_state(self):
        mapping = {'draft': 'draft', 'posted': 'posted', 'paid': 'posted',
                   'in_payment': 'posted', 'cancel': 'cancelled',
                   'canceled': 'cancelled'}
        for collection in self:
            if not collection.payment_id:
                collection.payment_state = 'not_created'
            else:
                collection.payment_state = mapping.get(
                    collection.payment_id.state, 'not_created')

    @api.onchange('journal_id')
    def _onchange_journal_id(self):
        self.payment_method_line_id = False

    @api.constrains('invoice_ids', 'partner_id', 'company_id')
    def _check_invoices(self):
        for collection in self:
            for invoice in collection.invoice_ids:
                if invoice.partner_id.commercial_partner_id != \
                        collection.partner_id.commercial_partner_id:
                    raise ValidationError(_(
                        "Invoice %(invoice)s does not belong to customer "
                        "%(customer)s.",
                        invoice=invoice.name, customer=collection.partner_id.display_name))
                if invoice.company_id != collection.company_id:
                    raise ValidationError(_(
                        "Invoice %(invoice)s does not belong to the "
                        "collection company.",
                        invoice=invoice.name))

    @api.constrains('journal_id', 'currency_id', 'company_id')
    def _check_journal(self):
        for collection in self:
            if collection.journal_id:
                if collection.journal_id.company_id != collection.company_id:
                    raise ValidationError(_(
                        "The payment journal must belong to the collection "
                        "company."))
                if collection.journal_id.currency_id and \
                        collection.journal_id.currency_id != collection.currency_id:
                    raise ValidationError(_(
                        "The payment journal currency does not match the "
                        "collection currency."))

    # ------------------------------------------------------------------
    # Access helpers
    # ------------------------------------------------------------------
    def _is_own_collection(self):
        """The assigned employee (or its user) owns the collection."""
        self.ensure_one()
        return bool(self.employee_id.user_id) and \
            self.employee_id.user_id.id == self.env.uid

    def _is_distribution_manager(self):
        return self.env.su or self.env.user.has_group(
            'flousflow_distribution_route_base.group_distribution_route_manager')

    def _is_validator(self):
        return self.env.su or self.env.user.has_group(
            'flousflow_distribution_commercial.'
            'group_distribution_collection_validator')

    def _has_accounting_rights(self):
        """Real accounting permission check — never bypassed with sudo."""
        return self.env.su or self.env.user.has_group(GROUP_ACCOUNT_BILLING)

    # ------------------------------------------------------------------
    # Guards
    # ------------------------------------------------------------------
    def write(self, vals):
        changed_financial = [f for f in self.FINANCIAL_FIELDS if f in vals]
        for collection in self:
            if not changed_financial:
                break
            if collection.state == 'draft':
                continue
            if collection.state == 'submitted':
                # Only the accounting date may be adjusted while submitted
                # (by an accounting-capable user) — nothing else.
                allowed = set(vals) <= {'accounting_date'} and \
                    collection._has_accounting_rights()
                if not allowed:
                    raise UserError(_(
                        "Submitted collection %(name)s is locked. A manager "
                        "may reset it to draft.", name=collection.name))
            else:  # validated / rejected / cancelled
                raise UserError(_(
                    "Collection %(name)s is %(state)s and can no longer be "
                    "modified.", name=collection.name,
                    state=collection.state))
        return super().write(vals)

    @api.ondelete(at_uninstall=False)
    def _unlink_except_draft(self):
        for collection in self:
            if collection.state != 'draft':
                raise UserError(_(
                    "Only draft collections can be deleted. Collection "
                    "%(name)s is %(state)s.",
                    name=collection.name, state=collection.state))

    # ------------------------------------------------------------------
    # Workflow: Submit (salesman) — spec #31/#32
    # ------------------------------------------------------------------
    def action_submit(self):
        for collection in self:
            if collection.state != 'draft':
                raise UserError(_(
                    "Collection %(name)s is already %(state)s.",
                    name=collection.name, state=collection.state))
            if not collection.visit_id:
                raise UserError(_("A collection must be linked to a visit."))
            if not collection.partner_id:
                raise UserError(_("The visit has no customer."))
            if collection.amount <= 0:
                raise UserError(_("The collection amount must be positive."))
            if not collection.collection_method:
                raise UserError(_("Select a collection method."))
            if collection.company_id.require_collection_attachment and \
                    not collection._get_attachment_count():
                raise UserError(_(
                    "This company requires at least one attachment "
                    "(receipt, transfer proof) on customer collections."))
            # Ownership check via the visit's stored user_id column —
            # reading employee private fields is not allowed for
            # non-HR profiles (Odoo 19).
            if collection.visit_id.user_id and \
                    collection.visit_id.user_id.id != self.env.uid and \
                    not (self.env.su or self._is_distribution_manager()):
                raise UserError(_(
                    "You can only submit collections recorded for your own "
                    "visits."))
        self.write({'state': 'submitted'})
        self.activity_schedule(
            'mail.mail_activity_data_todo',
            note=_("Customer collection awaiting accounting validation."),
            user_id=self.env.user.id)
        self.message_post(body=_("Collection submitted for accounting "
                                 "validation."))
        return True

    def _check_invoice_policy(self):
        """Unallocated / overpayment policies (spec #42/#43). Reading the
        invoices' residual is a system-level, read-only check (salesmen
        have no accounting read access) — no sudo on any write path."""
        self.ensure_one()
        company = self.company_id
        if self.invoice_ids:
            residual = sum(
                invoice.sudo().amount_residual
                for invoice in self.invoice_ids)
            if self.amount > residual and \
                    not company.allow_collection_overpayment:
                raise UserError(_(
                    "Collection amount %(amount)s exceeds the outstanding "
                    "balance of the selected invoices (%(residual)s). "
                    "Adjust the amount or enable the overpayment policy.",
                    amount=self.amount, residual=residual))
        elif not company.allow_unallocated_customer_collection:
            raise UserError(_(
                "Unallocated customer collections are not allowed by "
                "policy. Select at least one customer invoice."))

    # ------------------------------------------------------------------
    # Workflow: Validate (accounting) — spec #49/#115
    # ------------------------------------------------------------------
    def action_validate(self):
        for collection in self:
            if collection.state != 'submitted':
                raise UserError(_(
                    "Only submitted collections can be validated. "
                    "Collection %(name)s is %(state)s.",
                    name=collection.name, state=collection.state))
            if not collection._has_accounting_rights():
                raise UserError(_(
                    "You need billing/accounting access to validate "
                    "customer collections."))
            if not collection.journal_id:
                raise UserError(_("Select a payment journal."))
            if not collection.payment_method_line_id:
                raise UserError(_("Select a payment method line."))
            collection._check_invoice_policy()
        self._create_standard_payments()
        self.write({'state': 'validated'})
        self.activity_feedback(['mail.mail_activity_data_todo'])
        self.message_post(body=_(
            "Collection validated — payment %(payment)s created and posted.",
            payment=self.payment_id.name or ''))
        return True

    def _create_standard_payments(self):
        """Create and post standard account.payment, then rely on STANDARD
        reconciliation. Runs inside the normal transaction: if anything
        fails, the collection stays 'submitted' (spec #50/#124)."""
        for collection in self:
            payment = self.env['account.payment'].create({
                'partner_type': 'customer',
                'payment_type': 'inbound',
                'partner_id': collection.partner_id.commercial_partner_id.id,
                'amount': collection.amount,
                'currency_id': collection.currency_id.id,
                'journal_id': collection.journal_id.id,
                'payment_method_line_id': collection.payment_method_line_id.id,
                'date': collection.accounting_date or
                        (collection.collection_date and
                         collection.collection_date.date()) or
                        fields.Date.context_today(collection),
                'memo': collection.payment_reference or collection.name,
            })
            payment.action_post()
            if collection.invoice_ids:
                # v19: account.payment has no line_ids — use the move's
                payment_lines = payment.move_id.line_ids.filtered(
                    lambda l: l.account_id.account_type == 'asset_receivable')
                invoice_lines = collection.invoice_ids.line_ids.filtered(
                    lambda l: l.account_id.account_type == 'asset_receivable'
                    and not l.reconciled)
                (payment_lines + invoice_lines).reconcile()
            collection.payment_id = payment.id

    # ------------------------------------------------------------------
    # Workflow: Reject / Reset / Cancel — spec #51/#52/#53
    # ------------------------------------------------------------------
    def action_reject(self, reason):
        for collection in self:
            if collection.state != 'submitted':
                raise UserError(_(
                    "Only submitted collections can be rejected."))
            if not collection._is_validator() and \
                    not collection._is_distribution_manager() and \
                    not collection._has_accounting_rights():
                raise UserError(_(
                    "Only collection validators may reject a collection."))
            if not reason:
                raise UserError(_("A rejection reason is required."))
        self.write({
            'state': 'rejected',
            'rejection_reason': reason,
            'rejected_by': self.env.uid,
            'rejected_datetime': fields.Datetime.now(),
        })
        self.message_post(body=_("Collection rejected: %s", reason))
        return True

    def action_reset_draft(self):
        """Rejected (or validated with a cancelled payment) goes back to
        draft. A POSTED payment must first be handled through the standard
        accounting workflow (spec #52)."""
        for collection in self:
            if collection.state not in ('rejected', 'validated'):
                raise UserError(_(
                    "Only rejected collections can be reset to draft."))
            if collection.payment_id and \
                    collection.payment_id.state == 'posted':
                raise UserError(_(
                    "Collection %(name)s has a posted payment. Cancel the "
                    "payment through standard accounting first.",
                    name=collection.name))
            if not (collection._is_validator() or
                    collection._is_distribution_manager()):
                raise UserError(_(
                    "Only validators or distribution managers may reset a "
                    "collection to draft."))
        self.write({
            'state': 'draft',
            'rejection_reason': False,
            'rejected_by': False,
            'rejected_datetime': False,
        })
        self.message_post(body=_("Collection reset to draft."))
        return True

    def action_cancel(self):
        for collection in self:
            if collection.state == 'validated' and collection.payment_id \
                    and collection.payment_id.state == 'posted':
                raise UserError(_(
                    "Collection %(name)s has a posted payment. Cancel the "
                    "payment through standard accounting first.",
                    name=collection.name))
            if collection.state in ('validated', 'cancelled'):
                raise UserError(_(
                    "Collection %(name)s is %(state)s and cannot be "
                    "cancelled.", name=collection.name,
                    state=collection.state))
            if not (collection._is_own_collection() or
                    collection._is_distribution_manager() or
                    collection._is_validator()):
                raise UserError(_("You cannot cancel this collection."))
        self.write({'state': 'cancelled'})
        self.message_post(body=_("Collection cancelled."))
        return True

    # ------------------------------------------------------------------
    # Open helpers
    # ------------------------------------------------------------------
    def _get_attachment_count(self):
        self.ensure_one()
        return self.env['ir.attachment'].search_count([
            ('res_model', '=', self._name),
            ('res_id', 'in', self.ids),
        ])

    def action_open_reject_wizard(self):
        self.ensure_one()
        return {
            'type': 'ir.actions.act_window',
            'name': _('Reject Collection'),
            'res_model': 'distribution.collection.review.wizard',
            'view_mode': 'form',
            'views': [(False, 'form')],
            'target': 'new',
            'context': {
                'default_collection_id': self.id,
                'default_action_type': 'reject',
            },
        }

    def action_open_reset_wizard(self):
        self.ensure_one()
        return {
            'type': 'ir.actions.act_window',
            'name': _('Reset Collection to Draft'),
            'res_model': 'distribution.collection.review.wizard',
            'view_mode': 'form',
            'views': [(False, 'form')],
            'target': 'new',
            'context': {
                'default_collection_id': self.id,
                'default_action_type': 'reset_draft',
            },
        }

    def action_open_payment(self):
        self.ensure_one()
        if not self.payment_id:
            raise UserError(_("No payment has been created yet."))
        return {
            'type': 'ir.actions.act_window',
            'name': _('Payment'),
            'res_model': 'account.payment',
            'res_id': self.payment_id.id,
            'views': [(False, 'form')],
            'target': 'current',
        }

    def action_open_customer_ledger(self):
        """Standard partner ledger — only with accounting access (#84)."""
        self.ensure_one()
        if not self._has_accounting_rights():
            raise UserError(_(
                "You need billing/accounting access to open the customer "
                "ledger."))
        return {
            'type': 'ir.actions.act_window',
            'name': _('Customer Ledger'),
            'res_model': 'account.move.line',
            'view_mode': 'list,pivot,graph',
            'domain': [
                ('partner_id', '=', self.partner_id.commercial_partner_id.id),
                ('account_id.account_type', '=', 'asset_receivable'),
            ],
            'context': {},
        }
