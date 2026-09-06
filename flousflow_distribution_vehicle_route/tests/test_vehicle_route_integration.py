# -*- coding: utf-8 -*-
"""Route ↔ Vehicle Integration tests (spec #36-#40).

Covers: assignment auto-resolution (single / none / multiple), confirm
snapshot + historical integrity, change guards (user / manager / started /
completed), concurrent employee & vehicle routes, multi-company, wrong-POS
blocking, copy resets, and the spec #37/#38 core scenario (Ahmed VAN-01 →
VAN-02 while ROUTE-001 keeps VAN-01).
"""
from datetime import datetime, time, timedelta

from odoo import fields
from odoo.exceptions import UserError, ValidationError
from odoo.tests import TransactionCase, tagged


@tagged('post_install', '-at_install')
class TestVehicleRouteIntegration(TransactionCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.company = cls.env.company

        # Groups / users
        cls.group_route_user = cls.env.ref(
            'flousflow_distribution_route_base.group_distribution_route_user')
        cls.group_route_manager = cls.env.ref(
            'flousflow_distribution_route_base.'
            'group_distribution_route_manager')
        cls.group_vehicle_user = cls.env.ref(
            'flousflow_distribution_vehicle.'
            'group_distribution_vehicle_user')
        cls.group_vehicle_manager = cls.env.ref(
            'flousflow_distribution_vehicle.'
            'group_distribution_vehicle_manager')

        cls.manager_user = cls.env['res.users'].create({
            'name': 'Route Vehicle Manager',
            'login': 'veh_route_manager',
            'email': 'vrmanager@example.com',
            'group_ids': [(6, 0, [cls.group_route_manager.id,
                                  cls.group_vehicle_manager.id,
                                  cls.env.ref('hr.group_hr_user').id])],
        })
        cls.sales_user = cls.env['res.users'].create({
            'name': 'Ahmed Salesman',
            'login': 'veh_route_ahmed',
            'email': 'ahmedvr@example.com',
            'group_ids': [(6, 0, [cls.group_route_user.id,
                                  cls.group_vehicle_user.id])],
        })
        cls.mgr = cls.env(user=cls.manager_user)

        # Employees (distribution employees with user mapping)
        cls.emp_ahmed = cls.env['hr.employee'].create({
            'name': 'Ahmed Employee', 'company_id': cls.company.id,
            'user_id': cls.sales_user.id,
            'is_distribution_employee': True, 'distribution_active': True,
        })
        cls.emp_other = cls.env['hr.employee'].create({
            'name': 'Other Employee', 'company_id': cls.company.id,
            'is_distribution_employee': True, 'distribution_active': True,
        })

        # Master data
        cls.area = cls.env['distribution.area'].create({
            'name': 'Route Vehicle Area', 'company_id': cls.company.id,
            'employee_ids': [(6, 0, [cls.emp_ahmed.id, cls.emp_other.id])],
        })
        cls.visit_type = cls.env['distribution.visit.type'].create({
            'name': 'Vehicle Route Visit', 'code': 'veh_route_visit',
            'company_id': cls.company.id, 'require_customer': True,
        })
        cls.partner = cls.env['res.partner'].create({
            'name': 'Route Vehicle Customer', 'company_id': cls.company.id,
        })

        # Fleet: model + 3 vehicles configured via the vehicle wizard
        cls.vehicle_model = cls.env['fleet.vehicle.model'].create({
            'name': 'Route Van',
            'brand_id': cls.env['fleet.vehicle.model.brand'].create({
                'name': 'RouteBrand'}).id,
        })
        cls.car1, cls.car2, cls.car3 = (
            cls.env['fleet.vehicle'].create({
                'name': 'VAN-%02d' % seq,
                'license_plate': 'VR-%03d' % seq,
                'model_id': cls.vehicle_model.id,
                'company_id': cls.company.id,
                'is_distribution_vehicle': True,
            }) for seq in (1, 2, 3))
        for vehicle in (cls.car1, cls.car2, cls.car3):
            # Admin env: warehouse/POS creation needs stock & POS admin
            # rights which the distribution route manager does not carry.
            cls._configure_vehicle(cls.env, vehicle)

        cls.route_date = fields.Date.today()

    # ------------------------------------------------------------------
    @classmethod
    def _configure_vehicle(cls, env, vehicle):
        env['distribution.vehicle.configure.wizard'].create({
            'vehicle_id': vehicle.id,
            'company_id': cls.company.id,
            'main_warehouse_id': cls.env['stock.warehouse'].search(
                [('company_id', '=', cls.company.id),
                 ('distribution_vehicle_ids', '=', False)], limit=1).id,
            'warehouse_mode': 'create_new',
            'pos_mode': 'create_new',
            'activate': True,
        }).action_confirm()

    def _assignment(self, employee, vehicle, date_from=None, date_to=None):
        return self.mgr['fleet.vehicle.employee.assignment'].create({
            'employee_id': employee.id,
            'vehicle_id': vehicle.id,
            'role': 'sales_rep',
            'date_from': date_from or self.route_date - timedelta(days=7),
            'date_to': date_to,
            'company_id': self.company.id,
        })

    def _route(self, employee=None, **kwargs):
        vals = {
            'date': self.route_date,
            'employee_id': (employee or self.emp_ahmed).id,
            'area_id': self.area.id,
            'company_id': self.company.id,
        }
        vals.update(kwargs)
        return self.mgr['distribution.route.plan'].create(vals)

    def _visit(self, route):
        return self.mgr['distribution.route.visit'].create({
            'route_id': route.id,
            'sequence': 10,
            'partner_id': self.partner.id,
            'visit_type_id': self.visit_type.id,
            'planned_datetime': datetime.combine(
                fields.Date.to_date(route.date), time(10, 0)),
        })

    def _start(self, route):
        route.action_confirm()
        route.action_start_route()

    # ------------------------------------------------------------------
    # Resolution
    # ------------------------------------------------------------------
    def test_01_auto_resolve_single_assignment(self):
        """Spec #6/#7: one valid assignment → vehicle + warehouse + POS."""
        assignment = self._assignment(self.emp_ahmed, self.car1)
        route = self._route()
        self.assertEqual(route.vehicle_assignment_id, assignment)
        self.assertEqual(route.vehicle_id, self.car1)
        self.assertEqual(route.vehicle_warehouse_id,
                         self.car1.distribution_warehouse_id)
        self.assertEqual(route.vehicle_pos_config_id,
                         self.car1.distribution_pos_config_id)

    def test_02_no_assignment_and_require_setting(self):
        """Spec #9/#10: no assignment → confirm blocked by default,
        allowed when the setting is off."""
        route = self._route(employee=self.emp_other)
        self.assertFalse(route.vehicle_id)
        self.assertTrue(
            self.company.distribution_require_vehicle_on_route)
        self._visit(route)
        with self.assertRaises(UserError):
            route.action_confirm()
        self.company.distribution_require_vehicle_on_route = False
        route.action_confirm()
        self.assertEqual(route.state, 'confirmed')

    def test_03_multiple_assignments_ask_manager(self):
        """Spec #8: several valid assignments → never random; confirm
        blocked until the manager chooses."""
        self._assignment(self.emp_ahmed, self.car1)  # open
        self._assignment(self.emp_ahmed, self.car2,
                         date_from=self.route_date - timedelta(days=1),
                         date_to=self.route_date + timedelta(days=5))
        route = self._route()
        self.assertTrue(route.multiple_vehicle_assignments)
        self.assertFalse(route.vehicle_id)
        self._visit(route)
        with self.assertRaises(UserError):
            route.action_confirm()
        chosen = self.mgr['fleet.vehicle.employee.assignment'].search(
            [('employee_id', '=', self.emp_ahmed.id),
             ('vehicle_id', '=', self.car2.id)])
        route.vehicle_assignment_id = chosen
        route.action_confirm()
        self.assertEqual(route.vehicle_id, self.car2)

    # ------------------------------------------------------------------
    # Snapshot integrity (spec #37/#38)
    # ------------------------------------------------------------------
    def test_04_snapshot_frozen_after_assignment_change(self):
        """Spec #37: Ahmed VAN-01; route confirmed; Ahmed moved to VAN-02
        → ROUTE keeps VAN-01."""
        assignment1 = self._assignment(self.emp_ahmed, self.car1)
        route = self._route()
        self._visit(route)
        route.action_confirm()
        self.assertEqual(route.vehicle_id, self.car1)

        assignment1.action_close()
        assignment2 = self._assignment(self.emp_ahmed, self.car2)
        self.assertEqual(route.vehicle_id, self.car1)
        self.assertEqual(route.vehicle_warehouse_id,
                         self.car1.distribution_warehouse_id)
        self.assertEqual(route.vehicle_pos_config_id,
                         self.car1.distribution_pos_config_id)

    def test_05_second_route_uses_new_assignment(self):
        """Spec #38: after the reassignment the NEW route resolves VAN-02."""
        assignment1 = self._assignment(self.emp_ahmed, self.car1)
        route1 = self._route()
        self._visit(route1)
        route1.action_confirm()
        # Close the old assignment BEFORE the route date so the new one is
        # unambiguous for new routes (an assignment closed today still
        # covers today per the validity rule).
        assignment1.date_to = self.route_date - timedelta(days=1)
        self._assignment(self.emp_ahmed, self.car2)
        route2 = self._route()
        self.assertEqual(route2.vehicle_id, self.car2)
        self.assertEqual(route2.vehicle_warehouse_id,
                         self.car2.distribution_warehouse_id)
        self.assertEqual(route2.vehicle_pos_config_id,
                         self.car2.distribution_pos_config_id)
        # Route1 untouched
        self.assertEqual(route1.vehicle_id, self.car1)

    def test_06_snapshot_after_vehicle_config_change(self):
        """Spec #27: confirmed route survives vehicle reconfiguration."""
        self._assignment(self.emp_ahmed, self.car1)
        route = self._route()
        self._visit(route)
        route.action_confirm()
        old_wh = route.vehicle_warehouse_id
        old_pos = route.vehicle_pos_config_id
        # Manager reconfigures the vehicle with different warehouse/POS
        self.car1.distribution_pos_config_id = False
        self.car1.distribution_warehouse_id = False
        self._configure_vehicle(self.env, self.car1)
        self.assertEqual(route.vehicle_warehouse_id, old_wh)
        self.assertEqual(route.vehicle_pos_config_id, old_pos)

    # ------------------------------------------------------------------
    # Change guards (spec #13/#27)
    # ------------------------------------------------------------------
    def test_07_user_cannot_change_after_confirm(self):
        self._assignment(self.emp_ahmed, self.car1)
        route = self._route()
        self._visit(route)
        route.action_confirm()
        assignment2 = self._assignment(self.emp_other, self.car2)
        with self.assertRaises(UserError):
            route.with_user(self.sales_user).write({
                'vehicle_assignment_id': assignment2.id})
        with self.assertRaises(UserError):
            route.with_user(self.sales_user).write({'vehicle_id': self.car2.id})

    def test_08_manager_change_only_before_start(self):
        self._assignment(self.emp_ahmed, self.car1)
        route = self._route()
        self._visit(route)
        route.action_confirm()
        # Ahmed moves from VAN-01 to VAN-03 (closed before the route date
        # so the new open assignment is unambiguous)
        assignment1 = route.vehicle_assignment_id
        assignment1.date_to = self.route_date - timedelta(days=1)
        assignment3 = self._assignment(self.emp_ahmed, self.car3)
        # Manager may adjust while merely confirmed
        route.write({'vehicle_assignment_id': assignment3.id,
                     'vehicle_id': self.car3.id})
        self.assertEqual(route.vehicle_id, self.car3)
        # But not once started (route is already confirmed)
        route.action_start_route()
        with self.assertRaises(UserError):
            route.write({'vehicle_id': self.car1.id})

    def test_09_completed_route_immutable(self):
        """Spec #27: after completed nothing changes, even for managers."""
        self._assignment(self.emp_ahmed, self.car1)
        route = self._route()
        visit = self._visit(route)
        self._start(route)
        visit.action_start_visit()
        visit.action_finalize_visit(
            result_id=self.env.ref(
                'flousflow_distribution_route_management.'
                'visit_result_completed').id)
        route.action_complete_route()
        with self.assertRaises(UserError):
            route.write({'vehicle_id': self.car2.id})

    # ------------------------------------------------------------------
    # Start-route validation & concurrency (spec #14/#24/#25)
    # ------------------------------------------------------------------
    def test_10_start_after_assignment_closed_keeps_snapshot(self):
        """Spec #14: assignment closed between confirm and start → start
        succeeds, snapshot unchanged (no silent re-resolution)."""
        assignment = self._assignment(self.emp_ahmed, self.car1)
        route = self._route()
        self._visit(route)
        route.action_confirm()
        assignment.action_close()
        route.action_start_route()
        self.assertEqual(route.state, 'in_progress')
        self.assertEqual(route.vehicle_id, self.car1)

    def test_11_start_blocked_when_vehicle_deactivated(self):
        self._assignment(self.emp_ahmed, self.car1)
        route = self._route()
        self._visit(route)
        route.action_confirm()
        self.car1.distribution_active = False
        with self.assertRaises(UserError):
            route.action_start_route()
        self.car1.distribution_active = True
        route.action_start_route()

    def test_12_concurrent_employee_route_block(self):
        """Spec #24: one route in progress per employee."""
        self._assignment(self.emp_ahmed, self.car1)
        route1 = self._route()
        visit1 = self._visit(route1)
        self._start(route1)
        route2 = self._route()
        self._visit(route2)
        route2.action_confirm()
        with self.assertRaises(UserError):
            route2.action_start_route()
        # Once route1 completes, route2 can start
        visit1.action_start_visit()
        visit1.action_finalize_visit(
            result_id=self.env.ref(
                'flousflow_distribution_route_management.'
                'visit_result_completed').id)
        route1.action_complete_route()
        route2.action_start_route()
        self.assertEqual(route2.state, 'in_progress')

    def test_13_concurrent_vehicle_route_block(self):
        """Spec #25: a vehicle cannot run two routes at once (two different
        employees, same vehicle)."""
        self._assignment(self.emp_ahmed, self.car1)
        self._assignment(self.emp_other, self.car1)
        route1 = self._route(self.emp_ahmed)
        visit1 = self._visit(route1)
        self._start(route1)
        route2 = self._route(self.emp_other)
        self._visit(route2)
        route2.action_confirm()
        with self.assertRaises(UserError):
            route2.action_start_route()
        visit1.action_start_visit()
        visit1.action_finalize_visit(
            result_id=self.env.ref(
                'flousflow_distribution_route_management.'
                'visit_result_completed').id)
        route1.action_complete_route()
        route2.action_start_route()

    # ------------------------------------------------------------------
    # Multi-company (spec #34)
    # ------------------------------------------------------------------
    def test_14_multi_company_conflict(self):
        company2 = self.env['res.company'].create({'name': 'VR Company 2'})
        emp2 = self.env['hr.employee'].create({
            'name': 'Company2 Employee', 'company_id': company2.id,
            'is_distribution_employee': True, 'distribution_active': True,
        })
        area2 = self.env['distribution.area'].create({
            'name': 'Company2 Area', 'company_id': company2.id,
            'employee_ids': [(6, 0, [emp2.id])],
        })
        # Admin env: the manager user is company-scoped by record rules;
        # only the cross-company field check must be the thing that fires.
        with self.assertRaises(UserError):
            self.env['distribution.route.plan'].create({
                'date': self.route_date,
                'employee_id': emp2.id,
                'area_id': area2.id,
                'company_id': company2.id,
                'vehicle_id': self.car1.id,  # company 1 vehicle
            })

    # ------------------------------------------------------------------
    # POS enforcement (spec #22/#39) — reuses the vehicle module check
    # ------------------------------------------------------------------
    def test_15_wrong_pos_blocked_for_assigned_employee(self):
        """Spec #39: Ahmed started his route on VAN-01; opening an order on
        the VAN-02 POS is blocked by the existing vehicle authorization."""
        self._assignment(self.emp_ahmed, self.car1)
        route = self._route()
        self._visit(route)
        self._start(route)

        product = self.env['product.product'].create({
            'name': 'VR Test Product', 'type': 'consu', 'is_storable': True,
            'list_price': 10.0,
        })
        session2 = self.car2.distribution_pos_config_id.current_session_id
        if not session2 or session2.state == 'closed':
            self.car2.distribution_pos_config_id.open_ui()
            session2 = self.car2.distribution_pos_config_id.current_session_id
        with self.assertRaises(UserError):
            self.env(user=self.sales_user)['pos.order'].create({
                'company_id': self.company.id,
                'session_id': session2.id,
                'lines': [(0, 0, {
                    'product_id': product.id,
                    'qty': 1,
                    'price_unit': product.lst_price,
                    'price_subtotal': product.lst_price,
                    'price_subtotal_incl': product.lst_price,
                })],
            })

    # ------------------------------------------------------------------
    # Copy (spec #28)
    # ------------------------------------------------------------------
    def test_16_copy_route_resets_snapshot(self):
        """Duplicated route: fresh draft, snapshot re-resolved from the
        CURRENT assignment, never copied from the old route."""
        assignment1 = self._assignment(self.emp_ahmed, self.car1)
        route = self._route()
        self._visit(route)
        route.action_confirm()
        assignment1.date_to = self.route_date - timedelta(days=1)
        self._assignment(self.emp_ahmed, self.car3)
        copied = route.copy()
        self.assertEqual(copied.state, 'draft')
        self.assertEqual(copied.vehicle_id, self.car3)
        self.assertNotEqual(copied.vehicle_assignment_id,
                            route.vehicle_assignment_id)

    # ------------------------------------------------------------------
    # Visits & smart buttons (spec #18/#19/#20/#29)
    # ------------------------------------------------------------------
    def test_17_visit_reaches_snapshot(self):
        self._assignment(self.emp_ahmed, self.car1)
        route = self._route()
        visit = self._visit(route)
        self.assertEqual(visit.vehicle_id, self.car1)
        self.assertEqual(visit.vehicle_warehouse_id,
                         self.car1.distribution_warehouse_id)
        self.assertEqual(visit.vehicle_pos_config_id,
                         self.car1.distribution_pos_config_id)

    def test_18_smart_button_counts(self):
        self._assignment(self.emp_ahmed, self.car1)
        route = self._route()
        self.assertEqual(self.car1.distribution_route_count, 1)
        assignment = route.vehicle_assignment_id
        self.assertEqual(assignment.distribution_route_count, 1)
        action = self.car1.action_view_distribution_routes()
        self.assertEqual(action['res_model'], 'distribution.route.plan')
        action = assignment.action_view_distribution_routes()
        self.assertEqual(action['domain'],
                         [('vehicle_assignment_id', '=', assignment.id)])

    def test_19_route_smart_actions(self):
        self._assignment(self.emp_ahmed, self.car1)
        route = self._route()
        self._visit(route)
        route.action_confirm()
        action = route.action_view_route_vehicle_stock()
        self.assertEqual(action['res_model'], 'stock.quant')
        action = route.action_view_route_pos_orders()
        self.assertEqual(action['res_model'], 'pos.order')
        self.assertIn(('distribution_vehicle_id', '=', self.car1.id),
                      action['domain'])

    def test_20_current_route_helper(self):
        """Spec #23: current route computed from employee + state on
        demand, not stored globally."""
        self._assignment(self.emp_ahmed, self.car1)
        route = self._route()
        self.assertFalse(
            self.emp_ahmed._get_current_distribution_route())
        self._visit(route)
        route.action_confirm()
        route.action_start_route()
        self.assertEqual(self.emp_ahmed._get_current_distribution_route(),
                         route)
