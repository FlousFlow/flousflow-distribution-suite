from odoo import fields, models
class FleetVehicle(models.Model):
    _inherit='fleet.vehicle'
    inspection_ids=fields.One2many('distribution.vehicle.inspection','vehicle_id')
    inspection_count=fields.Integer(compute='_compute_inspection_count')
    def _compute_inspection_count(self):
        for v in self: v.inspection_count=len(v.inspection_ids)
