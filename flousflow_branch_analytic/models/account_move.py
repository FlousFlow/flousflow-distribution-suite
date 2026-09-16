from odoo import _, api, fields, models
from odoo.exceptions import UserError


class AccountMove(models.Model):
    _inherit = 'account.move'

    analytic_account_id = fields.Many2one(
        'account.analytic.account',
        string='Analytic Account',
        check_company=True,
        copy=False,
        help='Branch / profit center analytic account applied to invoice product lines and their COGS.',
    )

    @api.onchange('analytic_account_id')
    def _onchange_branch_analytic_account_id(self):
        if not self.analytic_account_id:
            return
        self._apply_branch_analytic_distribution()

    def _get_branch_analytic_distribution(self):
        return {str(self.analytic_account_id.id): 100.0} if self.analytic_account_id else None

    def _apply_branch_analytic_distribution(self):
        """Apply the header analytic account (100%) to commercial invoice lines.

        Only 'product' lines are updated. Tax lines, payment-term lines,
        receivable lines, sections and notes are left untouched. An empty
        header never modifies existing line-level distributions.
        """
        distribution = self._get_branch_analytic_distribution()
        if not distribution:
            return
        for line in self.line_ids.filtered(lambda l: l.display_type == 'product'):
            line.analytic_distribution = distribution

    def _stock_account_prepare_realtime_out_lines_vals(self):
        """Keep balance-sheet stock valuation lines out of analytic P&L.

        ``stock_account`` copies an invoice line's analytic distribution to
        both generated COGS lines: the expense line and the stock-valuation
        (interim) line. The latter is a balance-sheet line and must remain
        untagged. Keep the expense distribution intact and remove it only from
        the valuation line, identified by its originating invoice line and
        product account mapping.
        """
        lines_vals = super()._stock_account_prepare_realtime_out_lines_vals()
        MoveLine = self.env['account.move.line']
        for vals in lines_vals:
            origin_line = MoveLine.browse(vals.get('cogs_origin_id')).exists()
            if not origin_line or not origin_line.product_id:
                continue
            accounts = origin_line.product_id.product_tmpl_id.get_product_accounts(
                fiscal_pos=origin_line.move_id.fiscal_position_id,
            )
            stock_account = accounts.get('stock_valuation')
            if stock_account and vals.get('account_id') == stock_account.id:
                vals.pop('analytic_distribution', None)
        return lines_vals

    def _check_branch_analytic_required(self):
        for move in self:
            if (
                move.company_id.branch_analytic_require_invoice
                and move.move_type in ('out_invoice', 'out_refund')
                and not move.analytic_account_id
            ):
                raise UserError(_(
                    "Please select an Analytic Account before posting this customer invoice."
                ))

    def _post(self, soft=True):
        self._check_branch_analytic_required()
        return super()._post(soft=soft)
