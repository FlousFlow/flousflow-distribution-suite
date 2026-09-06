# -*- coding: utf-8 -*-
"""Vehicle Analytic Accounting — each distribution vehicle gets its own
analytic account (profit center). Created automatically by the vehicle
configure wizard and applied to the vehicle POS so sales + COGS land on
the vehicle's analytic account without manual steps (spec: vehicle P&L)."""
from odoo import _, api, fields, models


class FleetVehicle(models.Model):
    _inherit = 'fleet.vehicle'

    distribution_analytic_account_id = fields.Many2one(
        'account.analytic.account',
        string='Vehicle Analytic Account', index=True, tracking=True,
        copy=False, check_company=True, ondelete='restrict',
        domain="[('company_id', '=', company_id)]",
        help="Profit-center analytic account for this vehicle. Applied to "
             "its POS sales and COGS so you get a P&L per vehicle.")

    def _prepare_vehicle_analytic_vals(self, name):
        """Analytic account values for this vehicle (plan: analytic)."""
        self.ensure_one()
        company = self.company_id or self.env.company
        # analytic plan = the first available (standard 'analytic' plan)
        plan = self.env['account.analytic.plan'].sudo().search([], limit=1)
        vals = {
            'name': name,
            'company_id': company.id,
        }
        if plan:
            vals['plan_id'] = plan.id
        return vals

    def _ensure_vehicle_analytic_account(self):
        """Create the vehicle's analytic account if missing; return it."""
        self.ensure_one()
        if self.distribution_analytic_account_id:
            return self.distribution_analytic_account_id
        name = _('Vehicle %s', self.display_name)
        account = self.env['account.analytic.account'].sudo().create(
            self._prepare_vehicle_analytic_vals(name))
        self.distribution_analytic_account_id = account.id
        return account


class PosConfig(models.Model):
    _inherit = 'pos.config'

    def _sync_vehicle_analytic(self):
        """Keep the POS analytic account aligned with its vehicle's."""
        for config in self:
            vehicle = config.distribution_vehicle_id
            if not vehicle or not vehicle.distribution_analytic_account_id:
                continue
            if config.analytic_account_id != \
                    vehicle.distribution_analytic_account_id:
                config.analytic_account_id = \
                    vehicle.distribution_analytic_account_id.id
