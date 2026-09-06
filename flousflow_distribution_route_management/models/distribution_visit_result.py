# -*- coding: utf-8 -*-
from odoo import fields, models


class DistributionVisitResult(models.Model):
    _name = 'distribution.visit.result'
    _description = 'Distribution Visit Result'
    _order = 'sequence, name, id'

    name = fields.Char(string='Name', required=True, index=True)
    code = fields.Char(string='Code', index=True)
    sequence = fields.Integer(string='Sequence', default=10)
    active = fields.Boolean(string='Active', default=True)
    company_id = fields.Many2one(
        'res.company',
        string='Company',
        index=True,
        help="Leave empty to share this result with all companies.",
    )
    is_success = fields.Boolean(
        string='Successful Result',
        help="Mark as successful when the visit achieved its business "
             "objective. Unsuccessful results require a failure reason "
             "when closing a visit.",
    )
    requires_notes = fields.Boolean(
        string='Require Notes',
        help="Result notes become mandatory when this result is selected.",
    )
    requires_revisit = fields.Boolean(
        string='Requires Revisit',
        help="When selected, the revisit flag is proposed by default on "
             "the completion wizard.",
    )
    color = fields.Integer(string='Color Index', default=0)
    description = fields.Text(string='Description')

    _code_company_uniq = models.Constraint(
        'unique (code, company_id)',
        'The visit result code must be unique per company!',
    )
