# -*- coding: utf-8 -*-
"""Distribution Dashboard — read-only aggregation engine.

Every KPI, table and drill-down goes through the same domain builders so
the number on a card always equals the record count behind it (spec #45).

Query strategy (no N+1, spec #55/#56):
* ``read_group`` on distribution.route.visit (native + STORED related
  columns: employee_id / area_id / user_id / company_id)
* ``read_group`` on distribution.route.plan for route KPIs
* one batched fetch of done visits for the time analytics that cannot be
  SQL-aggregated (computed fields: actual_duration, arrival variance)
* NO sudo — standard record rules and allowed companies apply (spec #51)
"""
from collections import defaultdict
from datetime import datetime, timedelta

from odoo import _, api, fields, models

VISIT_STATES = [('pending', 'Pending'), ('in_progress', 'In Progress'),
                ('done', 'Done'), ('cancelled', 'Cancelled')]


def _rate(numerator, denominator):
    """Percentage with 2 decimals; 0.0 on zero denominator (spec #97)."""
    return round(numerator / denominator * 100.0, 2) if denominator else 0.0


class DistributionDashboardData(models.Model):
    _name = 'distribution.dashboard.data'
    _description = 'Distribution Dashboard Data Provider'
    _auto = False

    # ------------------------------------------------------------------
    # Public entry points
    # ------------------------------------------------------------------
    @api.model
    def get_dashboard_data(self, filters=None):
        """Full payload for the OWL dashboard (single RPC)."""
        filters = dict(filters or {})
        date_from, date_to = self._resolve_period(filters)
        visit_domain = self._visit_domain(filters, date_from, date_to)
        route_domain = self._route_domain(filters, date_from, date_to)

        route_kpi = self._kpi_routes(route_domain)
        visit_kpi, by_state = self._kpi_visits(visit_domain)
        done_visits = self._fetch_done_visits(visit_domain)
        visit_kpi.update(self._time_analytics(done_visits))

        by_route = self._counts_by_route(visit_domain)
        employees = self._employee_performance(
            filters, visit_domain, done_visits, by_route)
        areas = self._area_performance(filters, visit_domain, by_route)
        routes_table = self._routes_table(
            filters, route_domain, visit_domain, by_route)
        payload = {
            'period': {
                'date_from': fields.Date.to_string(date_from),
                'date_to': fields.Date.to_string(date_to),
                'label': filters.get('period', 'today'),
            },
            'capabilities': self._capabilities(),
            'kpi': {
                'routes': route_kpi,
                'visits': visit_kpi,
                'execution_rate': _rate(
                    visit_kpi['executed'], visit_kpi['planned_active']),
                'success_rate': _rate(
                    visit_kpi['successful'], visit_kpi['executed']),
            },
            'visits_by_state': by_state,
            'visits_by_result': self._visits_by_result(visit_domain),
            'daily_trend': self._daily_trend(
                filters, visit_domain, date_from, date_to),
            'employees': employees,
            'areas': areas,
            'customers': self._customer_analysis(visit_domain, done_visits),
            'visit_types': self._visit_type_analysis(visit_domain),
            'routes': routes_table,
            'attention': self._needs_attention(filters, date_from, date_to),
            'sections': self._get_extra_sections(filters, date_from, date_to),
            'options': self._filter_options(filters),
        }
        return payload

    @api.model
    def get_drill_down(self, filters=None, target=None, res_id=None):
        """Action opening the records behind a KPI (spec #44/#45).

        The domain is built with the SAME helpers used for aggregation, so
        the list count always equals the card number.
        """
        filters = dict(filters or {})
        date_from, date_to = self._resolve_period(filters)
        visit_domain = self._visit_domain(filters, date_from, date_to)
        route_domain = self._route_domain(filters, date_from, date_to)
        label = target.replace('_', ' ').title()
        if target.startswith('route_'):
            domain = route_domain
            model = 'distribution.route.plan'
            if target == 'route_completed':
                domain = route_domain + [('state', '=', 'completed')]
            elif target == 'route_started':
                domain = route_domain + [
                    ('state', 'in', ('in_progress', 'completed'))]
        else:
            model = 'distribution.route.visit'
            domain = list(visit_domain)
            extra = {
                'visit_planned': [],
                'visit_executed': [('state', '=', 'done')],
                'visit_successful': [('state', '=', 'done'),
                                     ('result_id.is_success', '=', True)],
                'visit_unsuccessful': [('state', '=', 'done'),
                                       '|', ('result_id', '=', False),
                                       ('result_id.is_success', '=', False)],
                'visit_pending': [('state', 'in', ('pending',
                                                   'in_progress'))],
                'visit_needs_revisit': [('requires_revisit', '=', True)],
                'visit_attention_delayed': [
                    ('state', 'in', ('pending', 'in_progress')),
                    ('planned_datetime', '<', self._delay_cutoff()),
                ],
            }.get(target, [])
            domain += extra
        if res_id and model == 'distribution.route.plan':
            return {
                'type': 'ir.actions.act_window',
                'name': label,
                'res_model': model,
                'res_id': res_id,
                'views': [(False, 'form')],
                'target': 'current',
            }
        return {
            'type': 'ir.actions.act_window',
            'name': label,
            'res_model': model,
            'view_mode': 'list,form,pivot,graph',
            'views': [[False, 'list'], [False, 'form'], [False, 'pivot'],
                      [False, 'graph']],
            'domain': domain,
            'context': {},
            'target': 'current',
        }

    # ------------------------------------------------------------------
    # Period & domains
    # ------------------------------------------------------------------
    @api.model
    def _resolve_period(self, filters):
        """Date range from a named preset or explicit custom bounds."""
        today = fields.Date.context_today(self)
        period = filters.get('period') or self.env.company. \
            distribution_dashboard_default_period or 'today'
        if filters.get('date_from') and filters.get('date_to'):
            date_from = fields.Date.to_date(filters['date_from'])
            date_to = fields.Date.to_date(filters['date_to'])
        elif period == 'yesterday':
            date_from = date_to = today - timedelta(days=1)
        elif period == 'this_week':
            date_from = today - timedelta(days=today.weekday())
            date_to = date_from + timedelta(days=6)
        elif period == 'last_week':
            date_from = today - timedelta(days=today.weekday() + 7)
            date_to = date_from + timedelta(days=6)
        elif period == 'this_month':
            date_from = today.replace(day=1)
            next_month = (date_from.replace(day=28) +
                          timedelta(days=4)).replace(day=1)
            date_to = next_month - timedelta(days=1)
        elif period == 'last_month':
            first_this = today.replace(day=1)
            date_to = first_this - timedelta(days=1)
            date_from = date_to.replace(day=1)
        else:  # today
            date_from = date_to = today
        return date_from, date_to

    def _route_domain(self, filters, date_from, date_to):
        domain = [
            ('date', '>=', fields.Date.to_string(date_from)),
            ('date', '<=', fields.Date.to_string(date_to)),
            ('company_id', 'in', self.env.companies.ids),
        ]
        if filters.get('employee_id'):
            domain.append(('employee_id', '=', filters['employee_id']))
        if filters.get('supervisor_id'):
            domain.append(('supervisor_id', '=', filters['supervisor_id']))
        if filters.get('area_id'):
            domain.append(('area_id', '=', filters['area_id']))
        if filters.get('route_state'):
            domain.append(('state', '=', filters['route_state']))
        domain += self._get_extra_route_domain(filters)
        return domain

    def _visit_domain(self, filters, date_from, date_to):
        domain = [
            ('route_id.date', '>=', fields.Date.to_string(date_from)),
            ('route_id.date', '<=', fields.Date.to_string(date_to)),
            ('company_id', 'in', self.env.companies.ids),
        ]
        if filters.get('employee_id'):
            domain.append(('employee_id', '=', filters['employee_id']))
        if filters.get('supervisor_id'):
            domain.append(('route_id.supervisor_id', '=',
                           filters['supervisor_id']))
        if filters.get('area_id'):
            domain.append(('area_id', '=', filters['area_id']))
        if filters.get('route_state'):
            domain.append(('route_state', '=', filters['route_state']))
        if filters.get('partner_id'):
            domain.append(('partner_id', '=', filters['partner_id']))
        if filters.get('visit_type_id'):
            domain.append(('visit_type_id', '=', filters['visit_type_id']))
        if filters.get('result_id'):
            domain.append(('result_id', '=', filters['result_id']))
        domain += self._get_extra_visit_domain(filters)
        return domain

    def _delay_cutoff(self):
        threshold = self.env.company. \
            distribution_dashboard_visit_delay_alert_minutes or 30
        return fields.Datetime.now() - timedelta(minutes=threshold)

    # -- Extension hooks (spec #43) ---------------------------------------
    def _get_extra_route_domain(self, filters):
        """Override to add route-domain terms (e.g. vehicle filter)."""
        return []

    def _get_extra_visit_domain(self, filters):
        """Override to add visit-domain terms (e.g. vehicle filter)."""
        return []

    def _get_extra_sections(self, filters, date_from, date_to):
        """Override to add optional dashboard sections (GPS, vehicle...).

        Each section = dict(key, title, unavailable=bool, rows=[...], kpi={})
        A failing optional section must never break the dashboard (#66):
        the core already guards each call below.
        """
        return []

    def _postprocess_employees(self, rows, filters, date_from, date_to):
        """Override to enrich employee rows (e.g. GPS columns)."""
        return rows

    def _capabilities(self):
        plan_fields = self.env['distribution.route.plan']._fields
        visit_fields = self.env['distribution.route.visit']._fields
        return {
            'vehicle': 'vehicle_id' in plan_fields,
            'gps': 'checkin_geofence_status' in visit_fields,
        }

    # ------------------------------------------------------------------
    # KPI aggregations
    # ------------------------------------------------------------------
    def _kpi_routes(self, route_domain):
        Route = self.env['distribution.route.plan']
        groups = Route._read_group(route_domain, ['state'], ['__count'])
        counts = {state or 'none': cnt for (state, cnt) in groups}
        total = sum(counts.values())
        return {
            'planned': total,
            'started': counts.get('in_progress', 0) +
                       counts.get('completed', 0),
            'completed': counts.get('completed', 0),
            'in_progress': counts.get('in_progress', 0),
            'not_started': counts.get('draft', 0) +
                           counts.get('confirmed', 0),
            'cancelled': counts.get('cancelled', 0),
        }

    def _kpi_visits(self, visit_domain):
        Visit = self.env['distribution.route.visit']
        groups = Visit._read_group(visit_domain, ['state'], ['__count'])
        counts = {state or 'none': cnt for (state, cnt) in groups}
        total = sum(counts.values())
        executed = counts.get('done', 0)
        successful = Visit.search_count(
            visit_domain + [('state', '=', 'done'),
                            ('result_id.is_success', '=', True)])
        needs_revisit = Visit.search_count(
            visit_domain + [('requires_revisit', '=', True)])
        kpi = {
            'planned': total,
            'planned_active': total - counts.get('cancelled', 0),
            'executed': executed,
            'successful': successful,
            'unsuccessful': executed - successful,
            'pending': counts.get('pending', 0) +
                       counts.get('in_progress', 0),
            'needs_revisit': needs_revisit,
        }
        by_state = [
            {'state': state, 'label': label, 'count': counts.get(state, 0)}
            for state, label in VISIT_STATES
        ]
        return kpi, by_state

    def _counts_by_route(self, visit_domain):
        """{route_id: {'planned', 'executed', 'successful'}} — 3 queries."""
        Visit = self.env['distribution.route.visit']
        result = defaultdict(lambda: {'planned': 0, 'executed': 0,
                                      'successful': 0})
        for (route, cnt) in Visit._read_group(
                visit_domain, ['route_id'], ['__count']):
            if route:
                result[route.id]['planned'] = cnt
        for (route, cnt) in Visit._read_group(
                visit_domain + [('state', '=', 'done')],
                ['route_id'], ['__count']):
            if route:
                result[route.id]['executed'] = cnt
        for (route, cnt) in Visit._read_group(
                visit_domain + [('state', '=', 'done'),
                                ('result_id.is_success', '=', True)],
                ['route_id'], ['__count']):
            if route:
                result[route.id]['successful'] = cnt
        return result

    # ------------------------------------------------------------------
    # Time analytics (computed fields -> Python over one batched fetch)
    # ------------------------------------------------------------------
    def _fetch_done_visits(self, visit_domain):
        Visit = self.env['distribution.route.visit']
        return Visit.search_fetch(
            visit_domain + [('state', '=', 'done')],
            ['employee_id', 'area_id', 'route_id', 'partner_id',
             'visit_type_id', 'result_id', 'planned_datetime',
             'actual_start_datetime', 'actual_end_datetime',
             'requires_revisit', 'planned_duration'],
        )

    def _time_analytics(self, done_visits):
        """Average visit duration / arrival variance / late delay (minutes).

        Variance = actual start - planned time (negative = early, #15).
        Late delay counts only positive variance.
        """
        durations, variances, lates = [], [], []
        for v in done_visits:
            if v.actual_start_datetime and v.actual_end_datetime:
                durations.append(
                    (v.actual_end_datetime - v.actual_start_datetime)
                    .total_seconds() / 60.0)
            if v.actual_start_datetime and v.planned_datetime:
                variance = (v.actual_start_datetime - v.planned_datetime) \
                    .total_seconds() / 60.0
                variances.append(variance)
                if variance > 0:
                    lates.append(variance)
        return {
            'avg_visit_duration': round(sum(durations) / len(durations), 1)
            if durations else 0.0,
            'avg_arrival_variance': round(
                sum(variances) / len(variances), 1) if variances else 0.0,
            'avg_late_delay': round(sum(lates) / len(lates), 1)
            if lates else 0.0,
        }

    # ------------------------------------------------------------------
    # Performance tables
    # ------------------------------------------------------------------
    def _time_by_key(self, done_visits, key):
        """avg duration / avg variance / late minutes per employee|area|type."""
        stats = defaultdict(lambda: {'dur': [], 'var': []})
        for v in done_visits:
            k = key(v)
            if not k:
                continue
            s = stats[k.id]
            if v.actual_start_datetime and v.actual_end_datetime:
                s['dur'].append(
                    (v.actual_end_datetime - v.actual_start_datetime)
                    .total_seconds() / 60.0)
            if v.actual_start_datetime and v.planned_datetime:
                s['var'].append(
                    (v.actual_start_datetime - v.planned_datetime)
                    .total_seconds() / 60.0)
        return stats

    def _employee_performance(self, filters, visit_domain, done_visits,
                              by_route):
        Visit = self.env['distribution.route.visit']
        Route = self.env['distribution.route.plan']

        planned = self._group_count(visit_domain, 'employee_id')
        executed = self._group_count(
            visit_domain + [('state', '=', 'done')], 'employee_id')
        successful = self._group_count(
            visit_domain + [('state', '=', 'done'),
                            ('result_id.is_success', '=', True)],
            'employee_id')
        routes = Route._read_group(
            self._route_domain(filters, *self._resolve_period(filters)),
            ['employee_id'], ['__count'])
        routes_by_emp = {emp.id: cnt for (emp, cnt) in routes if emp}
        completed = Route._read_group(
            self._route_domain(filters, *self._resolve_period(filters)) +
            [('state', '=', 'completed')],
            ['employee_id'], ['__count'])
        completed_by_emp = {emp.id: cnt for (emp, cnt) in completed if emp}
        time_stats = self._time_by_key(done_visits, lambda v: v.employee_id)

        min_ranking = self.env.company. \
            distribution_dashboard_minimum_visits_for_ranking or 0
        rows = []
        all_emps = self.env['hr.employee'].browse(
            set(planned) | set(executed) | set(routes_by_emp))
        names = {e.id: e.sudo().name or '' for e in all_emps}
        for emp_id in sorted(set(planned) | set(executed) | set(routes_by_emp),
                             key=lambda i: -(executed.get(i, 0))):
            emp_done = executed.get(emp_id, 0)
            emp_success = successful.get(emp_id, 0)
            stats = time_stats.get(emp_id, {'dur': [], 'var': []})
            rows.append({
                'id': emp_id,
                'name': names.get(emp_id, ''),
                'routes': routes_by_emp.get(emp_id, 0),
                'routes_completed': completed_by_emp.get(emp_id, 0),
                'planned': planned.get(emp_id, 0),
                'executed': emp_done,
                'execution_rate': _rate(emp_done, planned.get(emp_id, 0)),
                'successful': emp_success,
                'success_rate': _rate(emp_success, emp_done),
                'avg_duration': round(
                    sum(stats['dur']) / len(stats['dur']), 1)
                if stats['dur'] else 0.0,
                'avg_variance': round(
                    sum(stats['var']) / len(stats['var']), 1)
                if stats['var'] else 0.0,
                'rankable': emp_done >= min_ranking,
            })
        return self._postprocess_employees(rows, filters,
                                           *self._resolve_period(filters))

    def _area_performance(self, filters, visit_domain, by_route):
        Route = self.env['distribution.route.plan']
        planned = self._group_count(visit_domain, 'area_id')
        executed = self._group_count(
            visit_domain + [('state', '=', 'done')], 'area_id')
        successful = self._group_count(
            visit_domain + [('state', '=', 'done'),
                            ('result_id.is_success', '=', True)],
            'area_id')
        route_domain = self._route_domain(
            filters, *self._resolve_period(filters))
        routes = Route._read_group(route_domain, ['area_id'], ['__count'])
        routes_by_area = {a.id: cnt for (a, cnt) in routes if a}
        route_done = Route._read_group(
            route_domain + [('state', '=', 'completed')],
            ['area_id'], ['__count'])
        completed_by_area = {a.id: cnt for (a, cnt) in route_done if a}
        # average route delay per area from plans with actual start vs
        # planned start
        rows = []
        all_areas = self.env['distribution.area'].browse(
            set(planned) | set(routes_by_area))
        names = {a.id: a.display_name or '' for a in all_areas}
        for area_id in sorted(set(planned) | set(routes_by_area),
                              key=lambda i: -(executed.get(i, 0))):
            area_done = executed.get(area_id, 0)
            rows.append({
                'id': area_id,
                'name': names.get(area_id, ''),
                'routes': routes_by_area.get(area_id, 0),
                'routes_completed': completed_by_area.get(area_id, 0),
                'planned': planned.get(area_id, 0),
                'executed': area_done,
                'execution_rate': _rate(area_done, planned.get(area_id, 0)),
                'successful': successful.get(area_id, 0),
                'success_rate': _rate(successful.get(area_id, 0), area_done),
            })
        return rows

    def _customer_analysis(self, visit_domain, done_visits):
        visits = self._group_count(visit_domain, 'partner_id')
        successful = self._group_count(
            visit_domain + [('state', '=', 'done'),
                            ('result_id.is_success', '=', True)],
            'partner_id')
        done = self._group_count(
            visit_domain + [('state', '=', 'done')], 'partner_id')
        needs_revisit = self._group_count(
            visit_domain + [('requires_revisit', '=', True)], 'partner_id')
        # last visit + most common result from the batched done visits
        last_visit, common_result = {}, {}
        for v in done_visits:
            if not v.partner_id:
                continue
            pid = v.partner_id.id
            cur = last_visit.get(pid)
            if not cur or (v.actual_end_datetime or v.planned_datetime) > cur:
                last_visit[pid] = v.actual_end_datetime or \
                    v.planned_datetime
            if v.result_id:
                common_result.setdefault(pid, defaultdict(int))
                common_result[pid][v.result_id.name] += 1
        rows = []
        partners = self.env['res.partner'].browse(set(visits))
        names = {p.id: p.display_name or '' for p in partners}
        for pid in sorted(visits, key=lambda i: -visits[i]):
            common = ''
            if common_result.get(pid):
                common = max(common_result[pid].items(),
                             key=lambda kv: kv[1])[0]
            rows.append({
                'id': pid,
                'name': names.get(pid, ''),
                'visits': visits.get(pid, 0),
                'successful': successful.get(pid, 0),
                'unsuccessful': done.get(pid, 0) - successful.get(pid, 0),
                'needs_revisit': needs_revisit.get(pid, 0),
                'last_visit': fields.Datetime.to_string(
                    last_visit.get(pid, False) or False),
                'most_common_result': common,
            })
        return rows[:50]

    def _visit_type_analysis(self, visit_domain):
        planned = self._group_count(visit_domain, 'visit_type_id')
        executed = self._group_count(
            visit_domain + [('state', '=', 'done')], 'visit_type_id')
        successful = self._group_count(
            visit_domain + [('state', '=', 'done'),
                            ('result_id.is_success', '=', True)],
            'visit_type_id')
        types = self.env['distribution.visit.type'].browse(set(planned))
        names = {t.id: t.name or '' for t in types}
        return [{
            'id': tid,
            'name': names.get(tid, ''),
            'planned': planned.get(tid, 0),
            'executed': executed.get(tid, 0),
            'execution_rate': _rate(executed.get(tid, 0), planned.get(tid, 0)),
            'successful': successful.get(tid, 0),
            'success_rate': _rate(successful.get(tid, 0),
                                  executed.get(tid, 0)),
        } for tid in sorted(planned, key=lambda i: -planned[i])]

    def _routes_table(self, filters, route_domain, visit_domain, by_route):
        Route = self.env['distribution.route.plan']
        plans = Route.search_fetch(
            route_domain,
            ['name', 'date', 'employee_id', 'area_id', 'state',
             'planned_start_time', 'actual_start_datetime',
             'actual_end_datetime'] +
            (['vehicle_id'] if 'vehicle_id' in Route._fields else []),
            order='date DESC, id DESC', limit=50,
        )
        has_vehicle = 'vehicle_id' in Route._fields
        employee_names = {
            e.id: e.sudo().name or '' for e in plans.employee_id}
        area_names = {a.id: a.display_name or ''
                      for a in plans.area_id}
        rows = []
        for p in plans:
            stats = by_route.get(p.id, {'planned': 0, 'executed': 0,
                                        'successful': 0})
            row = {
                'id': p.id,
                'name': p.name,
                'date': fields.Date.to_string(p.date),
                'employee': employee_names.get(p.employee_id.id, ''),
                'area': area_names.get(p.area_id.id, ''),
                'state': p.state,
                'planned': stats['planned'],
                'executed': stats['executed'],
                'execution_rate': _rate(stats['executed'], stats['planned']),
                'success_rate': _rate(stats['successful'], stats['executed']),
                'actual_start': fields.Datetime.to_string(
                    p.actual_start_datetime or False),
                'actual_end': fields.Datetime.to_string(
                    p.actual_end_datetime or False),
                'vehicle': '',
            }
            if has_vehicle:
                row['vehicle'] = p.vehicle_id.display_name or ''
            rows.append(row)
        return rows

    def _visits_by_result(self, visit_domain):
        Visit = self.env['distribution.route.visit']
        groups = Visit._read_group(
            visit_domain + [('state', '=', 'done')],
            ['result_id'], ['__count'])
        results = [r for (r, _cnt) in groups if r]
        success_map = {r.id: bool(r.sudo().is_success) for r in results}
        out = []
        for result, cnt in groups:
            if result:
                out.append({'id': result.id, 'name': result.name or '',
                            'count': cnt,
                            'is_success': success_map.get(result.id, False)})
            else:
                out.append({'id': 0, 'name': 'No Result', 'count': cnt,
                            'is_success': False})
        return out

    def _daily_trend(self, filters, visit_domain, date_from, date_to):
        Visit = self.env['distribution.route.visit']
        Route = self.env['distribution.route.plan']
        # visits per day: group by route, map through route date (1 query)
        route_day = {}
        plans = Route.search_fetch(
            [('date', '>=', fields.Date.to_string(date_from)),
             ('date', '<=', fields.Date.to_string(date_to)),
             ('company_id', 'in', self.env.companies.ids)],
            ['date'])
        for p in plans:
            route_day[p.id] = p.date
        trend = defaultdict(lambda: {'planned': 0, 'executed': 0,
                                     'successful': 0})
        for (route, cnt) in Visit._read_group(
                visit_domain, ['route_id'], ['__count']):
            if route and route.id in route_day:
                trend[route_day[route.id]]['planned'] += cnt
        for (route, cnt) in Visit._read_group(
                visit_domain + [('state', '=', 'done')],
                ['route_id'], ['__count']):
            if route and route.id in route_day:
                trend[route_day[route.id]]['executed'] += cnt
        for (route, cnt) in Visit._read_group(
                visit_domain + [('state', '=', 'done'),
                                ('result_id.is_success', '=', True)],
                ['route_id'], ['__count']):
            if route and route.id in route_day:
                trend[route_day[route.id]]['successful'] += cnt
        out, day = [], date_from
        while day <= date_to:
            row = trend.get(day, {'planned': 0, 'executed': 0,
                                  'successful': 0})
            out.append({'date': fields.Date.to_string(day),
                        **row})
            day += timedelta(days=1)
        # cap long custom ranges for payload size (analytics stay in menus)
        return out[-62:]

    def _needs_attention(self, filters, date_from, date_to):
        """Attention list (#71-#74) — only with data actually available."""
        now = fields.Datetime.now()
        today = fields.Date.context_today(self)
        company = self.env.company
        route_domain = self._route_domain(
            filters, *self._resolve_period(filters))
        Route = self.env['distribution.route.plan']
        Visit = self.env['distribution.route.visit']
        items = []

        # 1. Routes not started although their planned start has passed
        late_start_cut = now - timedelta(
            minutes=company.distribution_dashboard_route_start_delay_minutes
            or 15)
        for p in Route.search_fetch(
                route_domain + [
                    ('state', 'in', ('draft', 'confirmed')),
                    ('planned_start_time', '<', late_start_cut)],
                ['name', 'employee_id', 'state'], limit=20):
            items.append({
                'type': 'route_late_start',
                'model': 'distribution.route.plan',
                'res_id': p.id,
                'label': _('Route %s not started (planned %s)',
                           p.name,
                           fields.Datetime.to_string(
                               p.planned_start_time or False)),
            })

        # 2. Visits delayed beyond the threshold and not executed
        delayed = Visit.search_fetch(
            self._visit_domain(filters, date_from, date_to) + [
                ('state', 'in', ('pending', 'in_progress')),
                ('planned_datetime', '<', self._delay_cutoff()),
            ],
            ['partner_id', 'employee_id', 'planned_datetime'], limit=20)
        for v in delayed:
            items.append({
                'type': 'visit_delayed',
                'model': 'distribution.route.visit',
                'res_id': v.id,
                'label': _('Visit delayed — %s (planned %s)',
                           v.partner_id.sudo().display_name or '—',
                           fields.Datetime.to_string(
                               v.planned_datetime or False)),
            })
        if len(delayed) == 20:
            items.append({'type': 'visit_delayed_more',
                          'label': _('…and more delayed visits'),
                          'model': 'distribution.route.visit',
                          'res_id': False})

        # 3. Low execution routes (time-of-day aware — never naive)
        low = company.distribution_dashboard_low_execution_percentage or 50
        plan_rows = Route.search_fetch(
            route_domain + [('state', 'in', ('in_progress', 'completed'))],
            ['name', 'state', 'employee_id'], limit=100)
        stats = self._counts_by_route(self._visit_domain(
            filters, *self._resolve_period(filters)))
        for p in plan_rows:
            s = stats.get(p.id, {'planned': 0, 'executed': 0})
            if not s['planned']:
                continue
            rate = s['executed'] / s['planned'] * 100.0
            if rate >= low:
                continue
            # in-progress routes are only flagged once the day is mostly
            # over (after 15:00) — a morning route is not an alert
            if p.state == 'in_progress' and now.hour < 15 \
                    and p.date == today:
                continue
            items.append({
                'type': 'route_low_execution',
                'model': 'distribution.route.plan',
                'res_id': p.id,
                'label': _('Route %s execution %d%% (< %d%%)',
                           p.name, round(rate), int(low)),
            })

        # 4. Routes with no vehicle assignment (vehicle integration only)
        if 'vehicle_id' in Route._fields:
            no_vehicle = Route.search_count(
                route_domain + [('vehicle_id', '=', False)])
            if no_vehicle:
                items.append({
                    'type': 'route_no_vehicle',
                    'model': 'distribution.route.plan',
                    'res_id': False,
                    'label': _('%s route(s) without vehicle assignment',
                               no_vehicle),
                })
        return items

    def _filter_options(self, filters):
        """Bounded option lists for the filter bar."""
        date_from, date_to = self._resolve_period(filters)
        visit_domain = self._visit_domain(filters, date_from, date_to)
        route_domain = self._route_domain(filters, date_from, date_to)
        Visit = self.env['distribution.route.visit']
        Route = self.env['distribution.route.plan']

        def opts(groups, recset):
            recs = recset.browse({g[0].id for g in groups if g[0]})
            return [{'id': r.id, 'name': r.display_name or ''}
                    for r in recs.sudo()]

        return {
            'employees': opts(
                Visit._read_group(visit_domain, ['employee_id'], []),
                self.env['hr.employee']),
            'areas': opts(
                Visit._read_group(visit_domain, ['area_id'], []),
                self.env['distribution.area']),
            'supervisors': opts(
                Route._read_group(route_domain, ['supervisor_id'], []),
                self.env['hr.employee']),
            'visit_types': opts(
                Visit._read_group(visit_domain, ['visit_type_id'], []),
                self.env['distribution.visit.type']),
            'results': opts(
                Visit._read_group(visit_domain, ['result_id'], []),
                self.env['distribution.visit.result']),
            'route_states': [
                {'id': s, 'name': l}
                for s, l in Route._fields['state'].selection
            ],
        }

    # ------------------------------------------------------------------
    @api.model
    def _group_count(self, domain, groupby):
        """{record_id: count} with a single grouped query."""
        res = {}
        for (rec, cnt) in self.env['distribution.route.visit']._read_group(
                domain, [groupby], ['__count']):
            if rec:
                res[rec.id] = cnt
        return res
