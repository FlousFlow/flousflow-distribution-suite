from odoo import api, fields, models, _
from odoo.exceptions import UserError, ValidationError

class VehicleInspection(models.Model):
    _name = 'distribution.vehicle.inspection'
    _description = 'Vehicle Inspection'
    _inherit = ['mail.thread', 'mail.activity.mixin']
    _check_company_auto = True
    _order = 'create_date desc, id desc'
    name = fields.Char(
        required=True,
        copy=False,
        default=lambda self: 'جديد' if self.env.lang == 'ar_001' else 'New',
    )
    company_id = fields.Many2one('res.company', required=True, default=lambda s:s.env.company, index=True)
    inspection_type = fields.Selection([('pre_trip','Pre-trip'),('post_trip','Post-trip'),('adhoc','Ad hoc')], required=True)
    template_id = fields.Many2one('distribution.vehicle.inspection.template', required=True, check_company=True)
    route_plan_id = fields.Many2one('distribution.route.plan', index=True, ondelete='restrict')
    vehicle_id = fields.Many2one('fleet.vehicle', required=True, check_company=True)
    vehicle_assignment_id = fields.Many2one('fleet.vehicle.employee.assignment', check_company=True)
    driver_id = fields.Many2one('hr.employee', check_company=True)
    scheduled_date = fields.Date(default=fields.Date.context_today, index=True)
    priority = fields.Selection([('0','Normal'),('1','High'),('2','Urgent')], default='0', index=True)
    instructions = fields.Text()
    assigned_user_id = fields.Many2one(related='driver_id.user_id', store=True, index=True)
    state = fields.Selection([('draft','Draft'),('in_progress','In Progress'),('submitted','Submitted'),('reviewed','Reviewed'),('cancelled','Cancelled')], default='draft', tracking=True)
    result = fields.Selection([('pending','Pending'),('passed','Passed'),('passed_with_issues','Passed with issues'),('failed','Failed')], default='pending', tracking=True)
    manager_override = fields.Boolean(readonly=True)
    review_decision = fields.Selection([('pending','Pending Review'),('accepted','Accepted'),('rejected','Rejected')], default='pending', tracking=True)
    completed_by = fields.Many2one('res.users', readonly=True, copy=False)
    completed_at = fields.Datetime(readonly=True, copy=False)
    overdue = fields.Boolean(compute='_compute_overdue', store=True)
    line_ids = fields.One2many('distribution.vehicle.inspection.line','inspection_id', copy=True)
    _route_unique = models.Constraint("UNIQUE(route_plan_id, inspection_type)", 'Only one active inspection of each type is allowed per route.')

    def _is_manager(self):
        return self.env.su or self.env.user.has_group('flousflow_distribution_vehicle_inspection.group_inspection_manager') or self.env.user.has_group('flousflow_distribution_vehicle.group_distribution_vehicle_manager') or self.env.user.has_group('flousflow_distribution_route_base.group_distribution_route_manager')

    @api.model_create_multi
    def create(self, vals_list):
        records = super().create(vals_list)
        for rec in records:
            if rec.name in ('New', 'جديد'):
                rec.name = self.env['ir.sequence'].next_by_code('distribution.vehicle.inspection') or f'INS/{rec.id}'
            if not rec.line_ids and rec.template_id:
                self.env['distribution.vehicle.inspection.line'].create([{'inspection_id':rec.id,'template_line_id':l.id,'name':l.name,'response_type':l.response_type,'selection_values':l.selection_values,'required':l.required,'critical':l.critical,'requires_photo':l.requires_photo,'requires_note':l.requires_note,'min_value':l.min_value,'max_value':l.max_value} for l in rec.template_id.line_ids])
        return records
    def action_start(self): self.write({'state':'in_progress'}); return True
    @api.depends('scheduled_date','state')
    def _compute_overdue(self):
        today=fields.Date.context_today(self)
        for rec in self: rec.overdue = bool(rec.scheduled_date and rec.scheduled_date < today and rec.state not in ('submitted','reviewed','cancelled'))
    def _notify_managers(self, summary):
        activity=self.env.ref('mail.mail_activity_data_todo')
        managers=self.env['res.users'].search([('groups_id','in',[self.env.ref('flousflow_distribution_vehicle.group_distribution_vehicle_manager').id])])
        for user in managers:
            self.activity_schedule(activity.id, user_id=user.id, summary=summary, note=summary)
    def action_submit(self):
        for rec in self:
            rec._validate_completion(); rec._compute_result(); rec.write({'state':'submitted','completed_by':self.env.user.id,'completed_at':fields.Datetime.now()}); rec._notify_managers(_('Inspection submitted for review'))
        return True
    def action_review(self):
        if not self._is_manager(): raise UserError(_('Only managers can review inspections.'))
        self.write({'state':'reviewed','review_decision':'accepted'}); return True
    def action_reject(self):
        if not self._is_manager(): raise UserError(_('Only managers can reject inspections.'))
        self.write({'state':'reviewed','review_decision':'rejected'}); return True
    @api.model
    def cron_create_daily_tasks(self):
        today=fields.Date.context_today(self); Template=self.env['distribution.vehicle.inspection.template']
        for template in Template.search([('active','=',True),('daily_task','=',True),('inspection_type','=','adhoc')]):
            for driver in template.driver_ids:
                assignment=self.env['fleet.vehicle.employee.assignment'].search([('employee_id','=',driver.id),('role','=','driver'),('company_id','=',template.company_id.id),('date_from','<=',today),'|',('date_to','=',False),('date_to','>=',today)], order='date_from desc', limit=1)
                if not assignment: continue
                exists=self.search([('template_id','=',template.id),('driver_id','=',driver.id),('scheduled_date','=',today),('inspection_type','=','adhoc')],limit=1)
                if not exists: self.create({'inspection_type':'adhoc','template_id':template.id,'driver_id':driver.id,'vehicle_id':assignment.vehicle_id.id,'vehicle_assignment_id':assignment.id,'scheduled_date':today})
        return True
    @api.model
    def cron_notify_overdue(self):
        for rec in self.search([('overdue','=',True),('review_decision','!=','rejected')]): rec._notify_managers(_('Inspection task is overdue: %s') % rec.display_name)
        return True
    def action_cancel(self): self.write({'state':'cancelled'}); return True
    def action_reopen(self):
        if not self._is_manager(): raise UserError(_('Only managers can reopen inspections.'))
        self.write({'state':'in_progress'}); return True
    def action_override(self):
        if not self._is_manager(): raise UserError(_('Only managers can override.'))
        self.write({'manager_override':True}); return True
    def _validate_completion(self):
        for line in self.line_ids:
            if line.required and not line.response_value: raise ValidationError(_('Required item is missing: %s') % line.name)
            if line.response_type == 'numeric' and line.response_value:
                try: value=float(line.response_value)
                except ValueError: raise ValidationError(_('Numeric value required for %s') % line.name)
                if line.min_value and value < line.min_value or line.max_value and value > line.max_value: raise ValidationError(_('Value out of range for %s') % line.name)
            if line.requires_note and not line.note: raise ValidationError(_('Note required for %s') % line.name)
            if line.requires_photo and not line.attachment_ids: raise ValidationError(_('Photo required for %s') % line.name)
    def _compute_result(self):
        failed=[l for l in self.line_ids if l.is_failure]
        self.result = 'failed' if any(l.critical for l in failed) else ('passed_with_issues' if failed else 'passed')

class VehicleInspectionLine(models.Model):
    _name='distribution.vehicle.inspection.line'; _description='Vehicle Inspection Line'; _order='sequence,id'
    inspection_id=fields.Many2one('distribution.vehicle.inspection',required=True,ondelete='cascade'); template_line_id=fields.Many2one('distribution.vehicle.inspection.template.line',ondelete='set null')
    sequence=fields.Integer(default=10); name=fields.Char(required=True); response_type=fields.Selection([('pass_fail','Pass/Fail'),('yes_no','Yes/No'),('numeric','Numeric'),('text','Text'),('selection','Selection')], required=True); selection_values=fields.Char(); response_value=fields.Char(); note=fields.Text(); attachment_ids=fields.Many2many('ir.attachment', string='Photos'); required=fields.Boolean(); critical=fields.Boolean(); requires_photo=fields.Boolean(); requires_note=fields.Boolean(); min_value=fields.Float(); max_value=fields.Float(); is_failure=fields.Boolean(compute='_compute_failure',store=True)
    @api.depends('response_value','response_type')
    def _compute_failure(self):
        for l in self:
            v=(l.response_value or '').strip().lower(); l.is_failure = (l.response_type in ('pass_fail','yes_no') and v in ('fail','failed','no','false','0'))
