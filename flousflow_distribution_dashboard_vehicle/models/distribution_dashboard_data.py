# -*- coding: utf-8 -*-
"""Vehicle analytics for the distribution dashboard (read-only)."""
from odoo import _, api, models


def _rate(num, den):
    return round(num / den * 100.0, 2) if den else 0.0


class DistributionDashboardDataVehicle(models.Model):
    _inherit = 'distribution.dashboard.data'

    # ------------------------------------------------------------------
    def _get_extra_route_domain(self, filters):
        domain = super()._get_extra_route_domain(filters)
        if filters.get('vehicle_id'):
            domain.append(('vehicle_id', '=', filters['vehicle_id']))
        return domain

    def _get_extra_visit_domain(self, filters):
        domain = super()._get_extra_visit_domain(filters)
        if filters.get('vehicle_id'):
            domain.append(('route_id.vehicle_id', '=',
                           filters['vehicle_id']))
        return domain

    # ------------------------------------------------------------------
    def _get_extra_sections(self, filters, date_from, date_to):
        sections = super()._get_extra_sections(filters, date_from, date_to)
        route_domain = self._route_domain(filters, date_from, date_to)
        visit_domain = self._visit_domain(filters, date_from, date_to)
        Route = self.env['distribution.route.plan']
        Visit = self.env['distribution.route.visit']

        routes = Route._read_group(route_domain, ['vehicle_id'], ['__count'])
        route_done = Route._read_group(
            route_domain + [('state', '=', 'completed')],
            ['vehicle_id'], ['__count'])
        visits = self._group_count(visit_domain, 'route_id')
        # visits per vehicle via route -> employee mapping not needed here:
        # count visits grouped by route then map through route.vehicle_id
        plans = Route.search_fetch(route_domain, ['vehicle_id'])
        vehicle_of_route = {p.id: p.vehicle_id.id for p in plans}
        visits_by_vehicle, executed_by_vehicle = {}, {}
        for (route, cnt) in Visit._read_group(
                visit_domain, ['route_id'], ['__count']):
            if route and route.id in vehicle_of_route and \
                    vehicle_of_route[route.id]:
                vid = vehicle_of_route[route.id]
                visits_by_vehicle[vid] = \
                    visits_by_vehicle.get(vid, 0) + cnt
        for (route, cnt) in Visit._read_group(
                visit_domain + [('state', '=', 'done')],
                ['route_id'], ['__count']):
            if route and route.id in vehicle_of_route and \
                    vehicle_of_route[route.id]:
                vid = vehicle_of_route[route.id]
                executed_by_vehicle[vid] = \
                    executed_by_vehicle.get(vid, 0) + cnt
        successful = self._group_count(
            visit_domain + [('state', '=', 'done'),
                            ('result_id.is_success', '=', True)],
            'route_id')
        success_by_vehicle = {}
        for rid, cnt in successful.items():
            vid = vehicle_of_route.get(rid)
            if vid:
                success_by_vehicle[vid] = \
                    success_by_vehicle.get(vid, 0) + cnt

        routes_by_vehicle = {v.id: cnt for (v, cnt) in routes if v}
        done_by_vehicle = {v.id: cnt for (v, cnt) in route_done if v}
        vehicles = self.env['fleet.vehicle'].browse(
            set(routes_by_vehicle) | set(visits_by_vehicle))
        names = {v.id: v.display_name or '' for v in vehicles.sudo()}
        rows = []
        for vid in sorted(set(routes_by_vehicle) | set(visits_by_vehicle),
                          key=lambda i: -(routes_by_vehicle.get(i, 0))):
            rows.append({
                'vehicle': names.get(vid, ''),
                'routes': routes_by_vehicle.get(vid, 0),
                'routes_completed': done_by_vehicle.get(vid, 0),
                'visits': visits_by_vehicle.get(vid, 0),
                'executed': executed_by_vehicle.get(vid, 0),
                'success_rate': _rate(success_by_vehicle.get(vid, 0),
                                      executed_by_vehicle.get(vid, 0)),
            })
        sections.append({
            'key': 'vehicle',
            'title': _('Vehicle Utilization (routes / visits per vehicle)'),
            'unavailable': False,
            'columns': [
                {'key': 'vehicle', 'label': _('Vehicle')},
                {'key': 'routes', 'label': _('Routes'), 'align': 'end'},
                {'key': 'routes_completed', 'label': _('Completed'),
                 'align': 'end'},
                {'key': 'visits', 'label': _('Visits'), 'align': 'end'},
                {'key': 'executed', 'label': _('Executed'), 'align': 'end'},
                {'key': 'success_rate', 'label': _('Success'),
                 'align': 'end'},
            ],
            'rows': rows,
        })

        # Current stock per vehicle warehouse — STANDARD stock.quant data,
        # clearly labeled CURRENT (never a historical snapshot, #39/#40).
        stock_rows = []
        Quant = self.env['stock.quant']
        for vehicle in self.env['fleet.vehicle'].search_fetch(
                [('is_distribution_vehicle', '=', True),
                 ('distribution_warehouse_id', '!=', False)],
                ['distribution_warehouse_id'], limit=50).sudo():
            wh = vehicle.distribution_warehouse_id
            loc = wh.lot_stock_id
            groups = Quant._read_group(
                [('location_id', 'in',
                  [loc.id] + loc.child_internal_location_ids.ids),
                 ('quantity', '!=', 0)],
                ['product_id'], ['quantity:sum'])
            products = {p.id for (p, _q) in groups if p}
            total_qty = sum((q or 0.0) for (_p, q) in groups)
            stock_rows.append({
                'vehicle': vehicle.display_name or '',
                'warehouse': wh.name or '',
                'products': len(products),
                'total_quantity': round(total_qty, 1),
            })
        sections.append({
            'key': 'vehicle_stock',
            'title': _('Current Vehicle Stock (live stock.quant — not a '
                       'historical route snapshot)'),
            'unavailable': False,
            'columns': [
                {'key': 'vehicle', 'label': _('Vehicle')},
                {'key': 'warehouse', 'label': _('Warehouse')},
                {'key': 'products', 'label': _('Products'),
                 'align': 'end'},
                {'key': 'total_quantity', 'label': _('Total Qty On Hand'),
                 'align': 'end'},
            ],
            'rows': stock_rows,
        })
        return sections

    # ------------------------------------------------------------------
    def _postprocess_employees(self, rows, filters, date_from, date_to):
        rows = super()._postprocess_employees(rows, filters, date_from,
                                              date_to)
        # vehicle name column for the employee table (if resolvable)
        date_from2, date_to2 = self._resolve_period(filters)
        Route = self.env['distribution.route.plan']
        plans = Route.search_fetch(
            self._route_domain(filters, date_from2, date_to2),
            ['employee_id', 'vehicle_id'])
        emp_vehicle = {}
        for p in plans:
            if p.vehicle_id:
                emp_vehicle.setdefault(p.employee_id.id,
                                       p.vehicle_id.display_name or '')
        for row in rows:
            row['vehicle'] = emp_vehicle.get(row['id'], '—')
        return rows

    # ------------------------------------------------------------------
    @api.model
    def _filter_options(self, filters):
        options = super()._filter_options(filters)
        date_from, date_to = self._resolve_period(filters)
        groups = self.env['distribution.route.plan']._read_group(
            self._route_domain(filters, date_from, date_to),
            ['vehicle_id'], [])
        vehicles = self.env['fleet.vehicle'].browse(
            {g[0].id for g in groups if g[0]})
        options['vehicles'] = [{'id': v.id, 'name': v.display_name or ''}
                               for v in vehicles.sudo()]
        return options
