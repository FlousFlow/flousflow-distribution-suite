# -*- coding: utf-8 -*-
"""GPS analytics for the distribution dashboard (read-only)."""
from odoo import _, api, models


def _rate(num, den):
    return round(num / den * 100.0, 2) if den else 0.0


class DistributionDashboardDataGps(models.Model):
    _inherit = 'distribution.dashboard.data'

    # ------------------------------------------------------------------
    def _get_extra_sections(self, filters, date_from, date_to):
        sections = super()._get_extra_sections(filters, date_from, date_to)
        visit_domain = self._visit_domain(filters, date_from, date_to)
        Visit = self.env['distribution.route.visit']
        Event = self.env['distribution.visit.gps.event']

        executed_groups = Visit._read_group(
            visit_domain + [('state', '=', 'done')],
            ['checkin_geofence_status'], ['__count'])
        executed = sum(cnt for _s, cnt in executed_groups)
        geo = {s or 'none': cnt for (s, cnt) in executed_groups}
        inside = geo.get('inside', 0)
        outside = geo.get('outside', 0)
        unknown = geo.get('none', 0) + geo.get('missing', 0) + \
            geo.get('pending', 0)

        override_groups = Event._read_group(
            [('route_id.date', '>=', str(date_from)),
             ('route_id.date', '<=', str(date_to)),
             ('company_id', 'in', self.env.companies.ids)],
            ['event_type'], ['__count'])
        by_type = {t or 'none': cnt for (t, cnt) in override_groups}

        done_domain = visit_domain + [('state', '=', 'done')]
        avg_dist = Visit._read_group(done_domain, [],
                                     ['checkin_distance:avg'])
        avg_acc = Visit._read_group(done_domain, [], ['checkin_accuracy:avg'])
        avg_distance = (avg_dist[0][0] or 0.0) if avg_dist else 0.0
        avg_accuracy = (avg_acc[0][0] or 0.0) if avg_acc else 0.0

        rows = [
            {'metric': _('Executed Visits'), 'value': executed},
            {'metric': _('Inside Geofence'), 'value': inside},
            {'metric': _('Outside Geofence'), 'value': outside},
            {'metric': _('Outside Geofence Rate'),
             'value': _rate(outside, executed)},
            {'metric': _('Unknown / Missing GPS'), 'value': unknown},
            {'metric': _('GPS Overrides'),
             'value': by_type.get('manager_override', 0)},
            {'metric': _('GPS Errors'),
             'value': by_type.get('gps_error', 0)},
            {'metric': _('Rejected Check-Ins'),
             'value': by_type.get('checkin_rejected', 0)},
            {'metric': _('Avg Check-In Distance (m)'),
             'value': round(avg_distance, 1)},
            {'metric': _('Avg GPS Accuracy (m)'),
             'value': round(avg_accuracy, 1)},
        ]
        sections.append({
            'key': 'gps',
            'title': _('GPS Compliance'),
            'unavailable': False,
            'columns': [
                {'key': 'metric', 'label': _('Metric')},
                {'key': 'value', 'label': _('Value'), 'align': 'end'},
            ],
            'rows': rows,
        })

        # Customers whose recorded location may be wrong (#35): everyone
        # checks in far away from the same customer.
        done = Visit.search_fetch(
            visit_domain + [('state', '=', 'done'),
                            ('checkin_geofence_status', '=', 'outside')],
            ['partner_id', 'checkin_distance'])
        cust_stats = {}
        for v in done:
            if not v.partner_id:
                continue
            s = cust_stats.setdefault(v.partner_id.id,
                                      {'count': 0, 'total': 0.0})
            s['count'] += 1
            s['total'] += v.checkin_distance or 0.0
        partners = self.env['res.partner'].browse(cust_stats)
        names = {p.id: p.display_name or '' for p in partners}
        cust_rows = [{'customer': names.get(pid, ''),
                      'outside_visits': s['count'],
                      'avg_distance': round(s['total'] / s['count'], 1)}
                     for pid, s in sorted(
                         cust_stats.items(),
                         key=lambda kv: -kv[1]['avg_distance'])[:20]]
        sections.append({
            'key': 'gps_customers',
            'title': _('GPS Customer Location Review (possible wrong '
                       'customer locations)'),
            'unavailable': False,
            'columns': [
                {'key': 'customer', 'label': _('Customer')},
                {'key': 'outside_visits', 'label': _('Outside Visits'),
                 'align': 'end'},
                {'key': 'avg_distance', 'label': _('Avg Distance (m)'),
                 'align': 'end'},
            ],
            'rows': cust_rows,
        })
        return sections

    # ------------------------------------------------------------------
    def _postprocess_employees(self, rows, filters, date_from, date_to):
        rows = super()._postprocess_employees(rows, filters, date_from,
                                              date_to)
        visit_domain = self._visit_domain(filters, date_from, date_to)
        Visit = self.env['distribution.route.visit']
        outside = self._group_count(
            visit_domain + [('state', '=', 'done'),
                            ('checkin_geofence_status', '=', 'outside')],
            'employee_id')
        inside = self._group_count(
            visit_domain + [('state', '=', 'done'),
                            ('checkin_geofence_status', '=', 'inside')],
            'employee_id')
        for row in rows:
            row['gps_outside'] = outside.get(row['id'], 0)
            row['gps_inside'] = inside.get(row['id'], 0)
        return rows

    # ------------------------------------------------------------------
    @api.model
    def get_gps_customer_analysis(self, filters=None):
        """Customers whose recorded location may be wrong: every
        representative checks in far away from the same customer."""
        filters = dict(filters or {})
        date_from, date_to = self._resolve_period(filters)
        visit_domain = self._visit_domain(filters, date_from, date_to)
        Visit = self.env['distribution.route.visit']
        done = Visit.search_fetch(
            visit_domain + [('state', '=', 'done'),
                            ('checkin_geofence_status', '=', 'outside')],
            ['partner_id', 'checkin_distance'])
        stats = {}
        for v in done:
            if not v.partner_id:
                continue
            s = stats.setdefault(v.partner_id.id,
                                 {'count': 0, 'total': 0.0})
            s['count'] += 1
            s['total'] += v.checkin_distance or 0.0
        partners = self.env['res.partner'].browse(stats)
        names = {p.id: p.display_name or '' for p in partners}
        return [{'id': pid, 'name': names.get(pid, ''),
                 'outside_visits': s['count'],
                 'avg_distance': round(s['total'] / s['count'], 1)}
                for pid, s in sorted(stats.items(),
                                     key=lambda kv: -kv[1]['avg_distance'])]
