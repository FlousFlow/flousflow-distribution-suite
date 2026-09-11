from odoo import api, fields, models
from odoo.exceptions import ValidationError

class InspectionTemplate(models.Model):
    _name = 'distribution.vehicle.inspection.template'
    _description = 'Vehicle Inspection Template'
    _check_company_auto = True
    name = fields.Char(required=True)
    active = fields.Boolean(default=True)
    company_id = fields.Many2one('res.company', required=True, default=lambda s: s.env.company)
    inspection_type = fields.Selection([('pre_trip','Pre-trip'),('post_trip','Post-trip'),('adhoc','Ad hoc')], required=True, default='pre_trip')
    auto_create_on_confirm = fields.Boolean(default=True)
    auto_create_on_complete = fields.Boolean(default=True)
    required_before_start = fields.Boolean(default=True)
    daily_task = fields.Boolean(string='Daily Task')
    driver_ids = fields.Many2many('hr.employee', string='Assigned Drivers', domain="[('user_id','!=',False)]")
    line_ids = fields.One2many('distribution.vehicle.inspection.template.line','template_id', copy=True)

class InspectionTemplateLine(models.Model):
    _name = 'distribution.vehicle.inspection.template.line'
    _description = 'Vehicle Inspection Template Line'
    _order = 'sequence, id'
    template_id = fields.Many2one('distribution.vehicle.inspection.template', required=True, ondelete='cascade')
    sequence = fields.Integer(default=10)
    name = fields.Char(required=True)
    response_type = fields.Selection([('pass_fail','Pass/Fail'),('yes_no','Yes/No'),('numeric','Numeric'),('text','Text'),('selection','Selection')], required=True, default='pass_fail')
    selection_values = fields.Char(help='Comma-separated values for selection responses.')
    min_value = fields.Float(); max_value = fields.Float()
    required = fields.Boolean(default=True); critical = fields.Boolean(); requires_photo = fields.Boolean(); requires_note = fields.Boolean()
    @api.constrains('min_value','max_value')
    def _check_range(self):
        for r in self:
            if r.min_value and r.max_value and r.min_value > r.max_value: raise ValidationError('Minimum must not exceed maximum.')
