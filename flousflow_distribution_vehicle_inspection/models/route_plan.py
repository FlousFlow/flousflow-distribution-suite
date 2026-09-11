from odoo import api, fields, models, _
from odoo.exceptions import UserError

class DistributionRoutePlan(models.Model):
    _inherit='distribution.route.plan'
    inspection_ids=fields.One2many('distribution.vehicle.inspection','route_plan_id')
    inspection_count=fields.Integer(compute='_compute_inspections')
    inspection_status=fields.Selection([('none','None'),('pending','Pending'),('passed','Passed'),('failed','Failed')],compute='_compute_inspections')
    def _compute_inspections(self):
        for r in self:
            xs=r.inspection_ids.filtered(lambda x:x.state!='cancelled'); r.inspection_count=len(xs); r.inspection_status='none' if not xs else ('failed' if any(x.result=='failed' and not x.manager_override for x in xs) else ('passed' if all(x.state in ('submitted','reviewed') and x.result!='pending' for x in xs) else 'pending'))
    def _inspection_template(self, typ):
        return self.env['distribution.vehicle.inspection.template'].search([('company_id','=',self.company_id.id),('inspection_type','=',typ),('active','=',True)], order='id', limit=1)
    def _ensure_inspection(self, typ):
        self.ensure_one()
        if not self.vehicle_id: return self.env['distribution.vehicle.inspection']
        existing=self.inspection_ids.filtered(lambda x:x.inspection_type==typ and x.state!='cancelled')
        if existing: return existing[:1]
        template=self._inspection_template(typ)
        return self.env['distribution.vehicle.inspection'].create({'company_id':self.company_id.id,'inspection_type':typ,'template_id':template.id,'route_plan_id':self.id,'vehicle_id':self.vehicle_id.id,'vehicle_assignment_id':self.vehicle_assignment_id.id,'driver_id':self.employee_id.id}) if template else self.env['distribution.vehicle.inspection']
    def action_confirm(self):
        res=super().action_confirm()
        self._ensure_inspection('pre_trip')
        return res
    def action_start_route(self):
        pre=self._ensure_inspection('pre_trip')
        if pre and (pre.state not in ('submitted','reviewed') or pre.result=='failed' and not pre.manager_override): raise UserError(_('A completed, non-failed pre-trip inspection is required before starting this route.'))
        return super().action_start_route()
    def action_complete_route(self, force=False, reason=None):
        res=super().action_complete_route(force=force, reason=reason)
        for route in self: route._ensure_inspection('post_trip')
        return res
