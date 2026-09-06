# -*- coding: utf-8 -*-
"""Review wizard: reject (reason required) or reset to draft (spec #51/#52)."""
from odoo import _, fields, models
from odoo.exceptions import UserError


class DistributionCollectionReviewWizard(models.TransientModel):
    _name = 'distribution.collection.review.wizard'
    _description = 'Collection Review Wizard'

    collection_id = fields.Many2one(
        'distribution.visit.collection', required=True)
    action_type = fields.Selection(
        selection=[('reject', 'Reject'), ('reset_draft', 'Reset to Draft')],
        required=True, default='reject')
    reason = fields.Text(
        string='Reason',
        help="Required when rejecting the collection.")

    def _get_collection(self):
        self.ensure_one()
        return self.env['distribution.visit.collection'].browse(
            self.collection_id.id)

    def apply(self):
        self.ensure_one()
        collection = self._get_collection()
        if self.action_type == 'reject':
            if not self.reason:
                raise UserError(_("A rejection reason is required."))
            collection.action_reject(self.reason)
        else:
            collection.action_reset_draft()
        return {
            'type': 'ir.actions.act_window',
            'name': _('Customer Collection'),
            'res_model': 'distribution.visit.collection',
            'res_id': collection.id,
            'views': [(False, 'form')],
            'target': 'current',
        }
