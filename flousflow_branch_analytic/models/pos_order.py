from odoo import models


class PosOrder(models.Model):
    _inherit = 'pos.order'

    def _prepare_invoice_vals(self):
        vals = super()._prepare_invoice_vals()
        account = self.config_id.analytic_account_id
        if account:
            vals['analytic_account_id'] = account.id
        return vals

    def _get_invoice_lines_values(self, line_values, pos_line, move_type):
        vals = super()._get_invoice_lines_values(line_values, pos_line, move_type)
        account = self.config_id.analytic_account_id
        # Only commercial product lines carry the analytic distribution.
        # Combo sections ('line_section') and note lines have no product_id.
        if account and vals.get('product_id'):
            vals['analytic_distribution'] = {str(account.id): 100.0}
        return vals
