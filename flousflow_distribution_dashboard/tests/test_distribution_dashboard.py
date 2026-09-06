# -*- coding: utf-8 -*-
"""Distribution Dashboard test suite (spec #94-#106).

Read-only tests: build controlled route/visit data, then assert the
dashboard aggregation (formulas, zero-division, entity aggregation,
filters, multi-company isolation, drill-down domain consistency,
needs-revisit and the optional GPS/vehicle sections).
"""
from datetime import datetime, time, timedelta

from odoo import fields
from odoo.tests import TransactionCase, tagged


@tagged('post_install', '-at_install')
class TestDistributionDashboard(TransactionCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.company_a = cls.env.company
        cls.company_b = cls.env['res.company'].create(
            {'name': 'Dashboard Co B'})

        cls.group_manager = cls.env.ref(
            'flousflow_distribution_route_base.'
            'group_distribution_route_manager')
        cls.manager_user = cls.env['res.users'].create({
            'name': 'Dash Manager', 'login': 'dash_manager',
            'email': 'dash@example.com',
            'group_ids': [(6, 0, [cls.group_manager.id])],
        })
        # Dashboard tests create routes WITHOUT vehicle data; the
        # vehicle-route extension requires one by default. Switch it off
        # for this suite.
        cls.company_a.distribution_require_vehicle_on_route = False
        # manager sees only company A (allowed companies)
        cls.manager_user.company_ids = [(6, 0, [cls.company_a.id])]
        cls.mgr = cls.env(user=cls.manager_user)

        cls.area_maadi = cls.env['distribution.area'].create({
            'name': 'Maadi', 'company_id': cls.company_a.id})
        cls.area_nasr = cls.env['distribution.area'].create({
            'name': 'Nasr City', 'company_id': cls.company_a.id})
        cls.visit_type = cls.env['distribution.visit.type'].create({
            'name': 'Dash Sales Visit', 'code': 'dash_sales',
            'company_id': cls.company_a.id, 'require_customer': True})
        cls.result_success = cls.env.ref(
            'flousflow_distribution_route_management.visit_result_completed')
        # any non-success result for business-failure tests
        cls.result_failed = cls.env.ref(
            'flousflow_distribution_route_management.'
            'visit_result_customer_closed')

        cls.emp_ahmed = cls.env['hr.employee'].create({
            'name': 'Ahmed Dash', 'company_id': cls.company_a.id,
            'is_distribution_employee': True, 'distribution_active': True})
        cls.emp_mohamed = cls.env['hr.employee'].create({
            'name': 'Mohamed Dash', 'company_id': cls.company_a.id,
            'is_distribution_employee': True, 'distribution_active': True})
        cls.area_maadi.write(
            {'employee_ids': [(6, 0, [cls.emp_ahmed.id])]})
        cls.area_nasr.write(
            {'employee_ids': [(6, 0, [cls.emp_mohamed.id])]})

        cls.partner = cls.env['res.partner'].create({
            'name': 'Dash Customer', 'company_id': cls.company_a.id})

        cls.today = fields.Date.context_today(cls.emp_ahmed)

    # ------------------------------------------------------------------
    def _route(self, employee, area, date=None, n_visits=1,
               state='draft'):
        """Route with n visits, optionally confirmed and started.
        Visits are created BEFORE confirming (confirm requires them)."""
        route = self.mgr['distribution.route.plan'].create({
            'date': date or self.today,
            'employee_id': employee.id,
            'area_id': area.id,
            'company_id': self.company_a.id,
        })
        visits = [self._visit(route, i) for i in range(n_visits)]
        if state != 'draft':
            route.action_confirm()
        if state == 'in_progress':
            route.action_start_route()
        return route, visits

    def _visit(self, route, offset_hours=0):
        # minute offsets keep up to 20 visits inside the route date
        when = datetime.combine(
            fields.Date.to_date(route.date), time(10, 0)) + \
            timedelta(minutes=offset_hours * 20)
        return self.mgr['distribution.route.visit'].create({
            'route_id': route.id,
            'partner_id': self.partner.id,
            'visit_type_id': self.visit_type.id,
            'planned_datetime': when,
        })

    def _visit_result(self, visit, success):
        """Close a visit via the standard finalize API."""
        visit.action_start_visit()
        visit.action_finalize_visit(
            result_id=self.result_success.id if success
            else self.result_failed.id,
            failure_reason=None if success else 'dashboard test',
        )

    def _data(self, filters=None):
        return self.mgr['distribution.dashboard.data'].get_dashboard_data(
            filters or {})

    # ------------------------------------------------------------------
    # Spec #95/#96/#97: core formulas + zero division
    # ------------------------------------------------------------------
    def test_01_execution_and_success_formulas(self):
        """20 planned / 15 executed -> 75% ; 9 successful -> 60%."""
        route, visits = self._route(self.emp_ahmed, self.area_maadi,
                                    n_visits=20, state='in_progress')
        for v in visits[:9]:
            self._visit_result(v, success=True)
        for v in visits[9:15]:
            self._visit_result(v, success=False)
        data = self._data()
        self.assertEqual(data['kpi']['visits']['planned'], 20)
        self.assertEqual(data['kpi']['visits']['executed'], 15)
        self.assertEqual(data['kpi']['visits']['successful'], 9)
        self.assertEqual(data['kpi']['visits']['unsuccessful'], 6)
        self.assertEqual(data['kpi']['execution_rate'], 75.0)
        self.assertEqual(data['kpi']['success_rate'], 60.0)

    def test_02_zero_division(self):
        """No visits at all -> rates 0, no ZeroDivisionError (#97)."""
        data = self._data()
        self.assertEqual(data['kpi']['execution_rate'], 0.0)
        self.assertEqual(data['kpi']['success_rate'], 0.0)
        self.assertEqual(data['kpi']['visits']['avg_visit_duration'], 0.0)
        self.assertEqual(data['kpi']['visits']['avg_arrival_variance'], 0.0)

    def test_03_executed_but_not_planned_active_cancelled(self):
        """Cancelled visits count in planned but not in planned_active."""
        route, visits = self._route(self.emp_ahmed, self.area_maadi,
                                    n_visits=2, state='in_progress')
        visits[1].action_skip_visit('dashboard test cancel')
        data = self._data()
        self.assertEqual(data['kpi']['visits']['planned'], 2)
        self.assertEqual(data['kpi']['visits']['planned_active'], 1)
        self.assertEqual(data['kpi']['visits']['pending'], 1)

    # ------------------------------------------------------------------
    # Spec #98/#99: employee math + business-result semantics
    # ------------------------------------------------------------------
    def test_04_employee_aggregation_and_success_denominator(self):
        """Ahmed 10 planned / 8 executed / 6 successful -> 80% / 75%.

        Success uses EXECUTED as denominator (6/8), never planned (6/10).
        """
        route, visits = self._route(self.emp_ahmed, self.area_maadi,
                                    n_visits=10, state='in_progress')
        for v in visits[:6]:
            self._visit_result(v, success=True)
        for v in visits[6:8]:
            self._visit_result(v, success=False)
        rows = self._data()['employees']
        ahmed = next(r for r in rows if r['name'] == 'Ahmed Dash')
        self.assertEqual(ahmed['planned'], 10)
        self.assertEqual(ahmed['executed'], 8)
        self.assertEqual(ahmed['successful'], 6)
        self.assertEqual(ahmed['execution_rate'], 80.0)
        self.assertEqual(ahmed['success_rate'], 75.0)

    def test_05_business_failure_is_not_unvisited(self):
        """'Customer Closed' = executed visit, unsuccessful business
        result (#76/#99): Executed+1, Successful+0."""
        route, visits = self._route(self.emp_ahmed, self.area_maadi,
                                    n_visits=1, state='in_progress')
        self._visit_result(visits[0], success=False)  # Customer Closed
        data = self._data()
        self.assertEqual(data['kpi']['visits']['executed'], 1)
        self.assertEqual(data['kpi']['visits']['successful'], 0)
        self.assertEqual(data['kpi']['visits']['unsuccessful'], 1)
        self.assertEqual(data['kpi']['visits']['pending'], 0)

    # ------------------------------------------------------------------
    # Spec #106: full two-employee scenario
    # ------------------------------------------------------------------
    def test_06_final_manual_scenario(self):
        """Ahmed 20/18/15 (90% / 83.33%) — Mohamed 20/15/8 (75% / 53.33%)."""
        for exec_n, succ_n in [(9, 8), (9, 7)]:
            r_ahmed, visits = self._route(self.emp_ahmed, self.area_maadi,
                                          n_visits=10,
                                          state='in_progress')
            for v in visits[:succ_n]:
                self._visit_result(v, success=True)
            for v in visits[succ_n:exec_n]:
                self._visit_result(v, success=False)
        for exec_n, succ_n in [(8, 4), (7, 4)]:
            r_mohamed, visits_m = self._route(
                self.emp_mohamed, self.area_nasr, n_visits=10,
                state='in_progress')
            for v in visits_m[:succ_n]:
                self._visit_result(v, success=True)
            for v in visits_m[succ_n:exec_n]:
                self._visit_result(v, success=False)

        rows = self._data()['employees']
        ahmed = next(r for r in rows if r['name'] == 'Ahmed Dash')
        mohamed = next(r for r in rows if r['name'] == 'Mohamed Dash')
        self.assertEqual((ahmed['planned'], ahmed['executed'],
                          ahmed['successful']), (20, 18, 15))
        self.assertEqual(ahmed['execution_rate'], 90.0)
        self.assertEqual(ahmed['success_rate'], 83.33)
        self.assertEqual((mohamed['planned'], mohamed['executed'],
                          mohamed['successful']), (20, 15, 8))
        self.assertEqual(mohamed['execution_rate'], 75.0)
        self.assertEqual(mohamed['success_rate'], 53.33)

    # ------------------------------------------------------------------
    # Aggregations: area / customer / type / route / trend / needs-revisit
    # ------------------------------------------------------------------
    def test_07_area_and_type_and_customer_aggregation(self):
        route, visits = self._route(self.emp_ahmed, self.area_maadi,
                                    n_visits=4, state='in_progress')
        self._visit_result(visits[0], success=True)
        self._visit_result(visits[1], success=False)
        self._visit_result(visits[2], success=True)
        visits[2].requires_revisit = True

        data = self._data()
        area = next(a for a in data['areas'] if a['name'] == 'Maadi')
        self.assertEqual((area['planned'], area['executed'],
                          area['successful']), (4, 3, 2))
        self.assertEqual(area['execution_rate'], 75.0)
        self.assertEqual(area['success_rate'],
                         round(2 / 3 * 100, 2))

        vtype = next(t for t in data['visit_types']
                     if t['name'] == 'Dash Sales Visit')
        self.assertEqual((vtype['planned'], vtype['executed']), (4, 3))
        self.assertEqual(data['kpi']['visits']['needs_revisit'], 1)

        cust = next(c for c in data['customers']
                    if c['name'] == 'Dash Customer')
        self.assertEqual(cust['visits'], 4)
        self.assertEqual(cust['successful'], 2)
        self.assertEqual(cust['unsuccessful'], 1)
        self.assertEqual(cust['needs_revisit'], 1)
        self.assertEqual(cust['most_common_result'],
                         self.result_success.name)

        route_row = next(r for r in data['routes'] if r['id'] == route.id)
        self.assertEqual(route_row['planned'], 4)
        self.assertEqual(route_row['execution_rate'], 75.0)

        trend_day = next(t for t in data['daily_trend']
                         if t['date'] == fields.Date.to_string(self.today))
        self.assertEqual((trend_day['planned'], trend_day['executed'],
                          trend_day['successful']), (4, 3, 2))

    # ------------------------------------------------------------------
    # Filters (#94): date + entity filters
    # ------------------------------------------------------------------
    def test_08_date_filter_excludes_other_periods(self):
        yesterday = self.today - timedelta(days=1)
        self._route(self.emp_ahmed, self.area_maadi, date=yesterday,
                    n_visits=1, state='in_progress')
        self._route(self.emp_ahmed, self.area_maadi,
                    n_visits=1, state='in_progress')

        # Use an explicit custom range (never a named preset) so the
        # assertion cannot race with a midnight rollover.
        data_today = self._data({'date_from': self.today,
                                 'date_to': self.today})
        self.assertEqual(data_today['kpi']['routes']['planned'], 1)
        self.assertEqual(data_today['kpi']['visits']['planned'], 1)

        data_yesterday = self._data({'date_from': yesterday,
                                     'date_to': yesterday})
        self.assertEqual(data_yesterday['kpi']['routes']['planned'], 1)
        self.assertEqual(data_yesterday['kpi']['visits']['planned'], 1)

        data_week = self._data({'period': 'this_week'})
        self.assertGreaterEqual(data_week['kpi']['routes']['planned'], 2)

    def test_09_entity_filters(self):
        self._route(self.emp_ahmed, self.area_maadi,
                    n_visits=1, state='in_progress')
        self._route(self.emp_mohamed, self.area_nasr,
                    n_visits=2, state='in_progress')

        data_ahmed = self._data({'employee_id': self.emp_ahmed.id})
        self.assertEqual(data_ahmed['kpi']['routes']['planned'], 1)
        self.assertEqual(data_ahmed['kpi']['visits']['planned'], 1)

        data_nasr = self._data({'area_id': self.area_nasr.id})
        self.assertEqual(data_nasr['kpi']['visits']['planned'], 2)

        data_mohamed = self._data({'employee_id': self.emp_mohamed.id})
        self.assertEqual(data_mohamed['kpi']['visits']['planned'], 2)

    # ------------------------------------------------------------------
    # Multi-company isolation (#101/#53) — record rules respected
    # ------------------------------------------------------------------
    def test_10_multi_company_isolation(self):
        # 1 visit for company A
        self._route(self.emp_ahmed, self.area_maadi,
                    n_visits=1, state='in_progress')
        # 2 visits for company B — created with admin env because the
        # manager user has no allowed company B (record rules block the
        # create; that isolation is exactly what we assert below).
        emp_b = self.env['hr.employee'].create({
            'name': 'B Employee', 'company_id': self.company_b.id,
            'is_distribution_employee': True, 'distribution_active': True})
        area_b = self.env['distribution.area'].create({
            'name': 'B Area', 'company_id': self.company_b.id,
            'employee_ids': [(6, 0, [emp_b.id])]})
        self.company_b.distribution_require_vehicle_on_route = False
        visit_type_b = self.env['distribution.visit.type'].create({
            'name': 'B Visit Type', 'code': 'b_visit',
            'company_id': self.company_b.id, 'require_customer': True})
        partner_b = self.env['res.partner'].create({
            'name': 'B Customer', 'company_id': self.company_b.id})
        route_b = self.env['distribution.route.plan'].create({
            'date': self.today, 'employee_id': emp_b.id,
            'area_id': area_b.id, 'company_id': self.company_b.id})
        for hours in (11, 12):
            self.env['distribution.route.visit'].create({
                'route_id': route_b.id, 'partner_id': partner_b.id,
                'visit_type_id': visit_type_b.id,
                'planned_datetime': datetime.combine(
                    fields.Date.to_date(route_b.date), time(hours, 0))})
        route_b.action_confirm()

        # manager is allowed only on company A -> sees 1, never 3 (#101)
        data = self._data()
        self.assertEqual(data['kpi']['routes']['planned'], 1)
        self.assertEqual(data['kpi']['visits']['planned'], 1)

        # with both companies allowed, both sides appear
        self.manager_user.company_ids = [
            (6, 0, [self.company_a.id, self.company_b.id])]
        self.env.invalidate_all()
        data2 = self.mgr[
            'distribution.dashboard.data'].get_dashboard_data({})
        self.assertEqual(data2['kpi']['visits']['planned'], 3)

    # ------------------------------------------------------------------
    # Drill-down domain consistency (#102/#45)
    # ------------------------------------------------------------------
    def test_11_drill_down_count_consistency(self):
        route, visits = self._route(self.emp_ahmed, self.area_maadi,
                                    n_visits=5, state='in_progress')
        for v in visits[:2]:
            self._visit_result(v, success=True)
        self._visit_result(visits[2], success=False)

        filters = {}
        Dashboard = self.mgr['distribution.dashboard.data']
        for target, expected in [('visit_planned', 5),
                                 ('visit_executed', 3),
                                 ('visit_successful', 2),
                                 ('visit_unsuccessful', 1),
                                 ('visit_pending', 2)]:
            action = Dashboard.get_drill_down(filters, target)
            count = self.mgr[action['res_model']].search_count(
                action['domain'])
            self.assertEqual(
                count, expected,
                'drill-down %s: card says %s, domain returns %s'
                % (target, expected, count))

        payload = self._data()
        self.assertEqual(payload['kpi']['visits']['executed'], 3)
        self.assertEqual(payload['kpi']['visits']['successful'], 2)
        self.assertEqual(payload['kpi']['visits']['pending'], 2)
        self.assertEqual(payload['kpi']['visits']['planned'], 5)

    # ------------------------------------------------------------------
    # Needs attention (#71-#74)
    # ------------------------------------------------------------------
    def test_12_needs_attention_delayed_visit(self):
        # visit planned 5 hours ago, still pending -> delayed (threshold
        # 30). The route date must equal the planned date, and the period
        # must cover it even if "now - 5h" crosses midnight.
        late = datetime.now() - timedelta(hours=5)
        route, _visits = self._route(
            self.emp_ahmed, self.area_maadi,
            date=late.date(), state='confirmed')
        self.mgr['distribution.route.visit'].create({
            'route_id': route.id, 'partner_id': self.partner.id,
            'visit_type_id': self.visit_type.id,
            'planned_datetime': late})
        route.action_start_route()
        attention = self._data({'date_from': route.date,
                                'date_to': route.date})['attention']
        types = [a['type'] for a in attention]
        self.assertIn('visit_delayed', types)

    def test_13_needs_attention_low_execution_completed(self):
        route, visits = self._route(self.emp_ahmed, self.area_maadi,
                                    n_visits=4, state='in_progress')
        self._visit_result(visits[0], success=True)
        route.action_complete_route(force=True, reason='dashboard test')
        # 1 of 4 executed = 25% < 50% threshold
        attention = self._data()['attention']
        self.assertIn('route_low_execution',
                      [a['type'] for a in attention])

    # ------------------------------------------------------------------
    # Optional sections (#94/#100)
    # ------------------------------------------------------------------
    def test_14_optional_sections_present_and_safe(self):
        payload = self._data()
        caps = payload['capabilities']
        section_keys = [s['key'] for s in payload['sections']]
        if caps['gps']:
            self.assertIn('gps', section_keys)
            gps = next(s for s in payload['sections']
                       if s['key'] == 'gps')
            # totals must equal the visit GPS data exactly (#100)
            done_inside = self.mgr['distribution.route.visit'].search_count(
                [('route_id.date', '>=', payload['period']['date_from']),
                 ('route_id.date', '<=', payload['period']['date_to']),
                 ('company_id', 'in', self.env.companies.ids),
                 ('state', '=', 'done'),
                 ('checkin_geofence_status', '=', 'inside')])
            row_inside = next(r for r in gps['rows']
                              if r['metric'] == 'Inside Geofence')
            self.assertEqual(row_inside['value'], done_inside)
        if caps['vehicle']:
            self.assertIn('vehicle', section_keys)
        # sections must never crash the payload — implicitly proven above

    def test_15_settings_defaults(self):
        company = self.company_a
        self.assertEqual(
            company.distribution_dashboard_default_period, 'today')
        self.assertEqual(
            company.distribution_dashboard_minimum_visits_for_ranking, 10)
        self.assertEqual(
            company.distribution_dashboard_visit_delay_alert_minutes, 30)
