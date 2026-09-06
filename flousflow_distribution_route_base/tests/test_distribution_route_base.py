# -*- coding: utf-8 -*-
import psycopg2
from odoo.exceptions import AccessError, ValidationError
from odoo.tests import Form, TransactionCase, tagged


@tagged('post_install', '-at_install')
class TestDistributionRouteBase(TransactionCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.Area = cls.env['distribution.area']
        cls.VisitType = cls.env['distribution.visit.type']
        cls.Partner = cls.env['res.partner']
        cls.Employee = cls.env['hr.employee']
        cls.company = cls.env.company
        cls.company_b = cls.env['res.company'].create({'name': 'Distribution Test Co B'})

        cls.group_user = cls.env.ref(
            'flousflow_distribution_route_base.group_distribution_route_user')
        cls.group_manager = cls.env.ref(
            'flousflow_distribution_route_base.group_distribution_route_manager')

        # Test users
        cls.route_user = cls.env['res.users'].create({
            'name': 'Route User',
            'login': 'route_user_test',
            'email': 'route_user@test.example.com',
            'group_ids': [(6, 0, [cls.group_user.id])],
        })
        cls.route_manager = cls.env['res.users'].create({
            'name': 'Route Manager',
            'login': 'route_manager_test',
            'email': 'route_manager@test.example.com',
            'group_ids': [(6, 0, [cls.group_manager.id])],
        })
        # User restricted to company B (for multi-company isolation test)
        cls.user_company_b = cls.env['res.users'].create({
            'name': 'Route User Co B',
            'login': 'route_user_cob_test',
            'email': 'route_user_cob@test.example.com',
            'group_ids': [(6, 0, [cls.group_user.id])],
            'company_id': cls.company_b.id,
            'company_ids': [(6, 0, [cls.company_b.id])],
        })

        # Basic master data
        cls.area_root = cls.Area.create({
            'name': 'Cairo',
            'code': 'CAI',
            'company_id': cls.company.id,
        })
        cls.area_child = cls.Area.create({
            'name': 'Maadi',
            'code': 'CAI-MDI',
            'parent_id': cls.area_root.id,
            'company_id': cls.company.id,
        })

    # ------------------------------------------------------------------
    # 1. Area creation
    # ------------------------------------------------------------------
    def test_01_area_create(self):
        area = self.Area.create({'name': 'Giza', 'code': 'GIZ'})
        self.assertEqual(area.company_id, self.company)
        self.assertTrue(area.active)
        self.assertEqual(area.parent_id, self.Area)

    def test_02_area_code_unique_per_company(self):
        # Enforced by the SQL constraint (Odoo 19 raises the raw DB error in ORM;
        # the service layer converts it to a ValidationError for real users).
        with self.assertRaises(psycopg2.errors.UniqueViolation):
            self.Area.create({'name': 'Cairo Duplicate', 'code': 'CAI'})

    def test_03_area_code_reusable_across_companies(self):
        # Same code is allowed in another company (uniqueness is per company)
        area = self.Area.create({
            'name': 'Cairo B',
            'code': 'CAI',
            'company_id': self.company_b.id,
        })
        self.assertEqual(area.company_id, self.company_b)

    # ------------------------------------------------------------------
    # 2. Hierarchy
    # ------------------------------------------------------------------
    def test_04_parent_child_hierarchy(self):
        self.assertEqual(self.area_child.parent_id, self.area_root)
        self.assertIn(self.area_child, self.area_root.child_ids)
        grandchild = self.Area.create({
            'name': 'Zahraa Maadi',
            'parent_id': self.area_child.id,
        })
        self.assertEqual(grandchild.parent_id, self.area_child)

    def test_05_self_parent_forbidden(self):
        with self.assertRaises(ValidationError):
            self.area_root.parent_id = self.area_root.id

    def test_06_circular_hierarchy_forbidden(self):
        area_b = self.Area.create({'name': 'Area B', 'parent_id': self.area_root.id})
        area_c = self.Area.create({'name': 'Area C', 'parent_id': area_b.id})
        # Making the root a child of area_c would create A -> B -> C -> A
        with self.assertRaises(ValidationError):
            self.area_root.parent_id = area_c.id

    # ------------------------------------------------------------------
    # 3. Visit Types
    # ------------------------------------------------------------------
    def test_07_visit_type_create(self):
        visit_type = self.VisitType.create({
            'name': 'Audit Visit',
            'code': 'audit',
            'require_customer': False,
        })
        self.assertEqual(visit_type.company_id, self.company)
        self.assertTrue(visit_type.active)
        self.assertFalse(visit_type.require_customer)

    def test_08_visit_type_code_unique_per_company(self):
        with self.assertRaises(psycopg2.errors.UniqueViolation):
            self.VisitType.create({'name': 'Sales Duplicate', 'code': 'sales'})

    def test_09_default_visit_types_loaded(self):
        for code in ('sales', 'collection', 'followup', 'prospect',
                     'complaint', 'merchandising', 'delivery', 'other'):
            visit_type = self.VisitType.search([('code', '=', code)], limit=1)
            self.assertTrue(visit_type, f"Missing default visit type: {code}")

    # ------------------------------------------------------------------
    # 4. Customer / Employee configuration
    # ------------------------------------------------------------------
    def test_10_partner_area_link(self):
        partner = self.Partner.create({
            'name': 'Supermarket Al Noor',
            'company_id': self.company.id,
            'distribution_area_id': self.area_child.id,
        })
        self.assertEqual(partner.distribution_area_id, self.area_child)
        partners_in_area = self.Partner.search([
            ('distribution_area_id', '=', self.area_child.id)])
        self.assertIn(partner, partners_in_area)

    def test_11_employee_multi_area(self):
        employee = self.Employee.create({
            'name': 'Ahmed Mohamed',
            'is_distribution_employee': True,
            'distribution_area_ids': [(6, 0, [self.area_root.id, self.area_child.id])],
        })
        self.assertEqual(len(employee.distribution_area_ids), 2)
        self.assertEqual(employee.distribution_active, True)
        self.assertIn(employee, self.area_root.employee_ids)

    def test_12_employee_supervisor(self):
        supervisor = self.Employee.create({'name': 'Mohamed Ali'})
        employee = self.Employee.create({
            'name': 'Ahmed Mohamed 2',
            'is_distribution_employee': True,
            'distribution_supervisor_id': supervisor.id,
        })
        self.assertEqual(employee.distribution_supervisor_id, supervisor)

    def test_13_employee_area_company_mismatch(self):
        with self.assertRaises(ValidationError):
            self.Employee.create({
                'name': 'Wrong Company Employee',
                'is_distribution_employee': True,
                'distribution_area_ids': [(6, 0, [self.area_root.id])],
                'company_id': self.company_b.id,
            })

    def test_14_area_employee_company_mismatch(self):
        employee_b = self.Employee.create({
            'name': 'Employee Co B',
            'company_id': self.company_b.id,
        })
        with self.assertRaises(ValidationError):
            self.area_root.employee_ids = [(4, employee_b.id)]

    # ------------------------------------------------------------------
    # 5. Multi-company isolation
    # ------------------------------------------------------------------
    def test_15_multi_company_isolation(self):
        area_b = self.Area.create({
            'name': 'Area Co B',
            'company_id': self.company_b.id,
        })
        # User restricted to company B must NOT see company A areas
        visible_areas = self.Area.with_user(self.user_company_b).search([])
        self.assertNotIn(self.area_root, visible_areas)
        self.assertIn(area_b, visible_areas)
        # And must not read a company A record directly
        with self.assertRaises(AccessError):
            self.area_root.with_user(self.user_company_b).read(['name'])
        # Visit types follow the same rule
        visit_b = self.VisitType.create({
            'name': 'Visit B', 'code': 'visitb', 'company_id': self.company_b.id})
        visible_visits = self.VisitType.with_user(self.user_company_b).search([])
        self.assertNotIn(self.VisitType.search([('code', '=', 'sales')]), visible_visits)
        self.assertIn(visit_b, visible_visits)

    # ------------------------------------------------------------------
    # 6. Permissions
    # ------------------------------------------------------------------
    def test_16_user_read_only(self):
        area = self.Area.with_user(self.route_user)
        # Read is allowed
        self.assertTrue(area.search([('id', '=', self.area_root.id)]))
        # Write is forbidden
        with self.assertRaises(AccessError):
            self.area_root.with_user(self.route_user).name = 'Hacked'
        # Create is forbidden
        with self.assertRaises(AccessError):
            self.Area.with_user(self.route_user).create({'name': 'Nope'})
        # Delete is forbidden
        with self.assertRaises(AccessError):
            self.area_child.with_user(self.route_user).unlink()

    def test_17_user_no_visit_type_write(self):
        with self.assertRaises(AccessError):
            self.VisitType.with_user(self.route_user).create(
                {'name': 'User Visit', 'code': 'uservisit'})
        visit_type = self.VisitType.search([('code', '=', 'sales')], limit=1)
        with self.assertRaises(AccessError):
            visit_type.with_user(self.route_user).require_customer = False

    def test_18_manager_full_access(self):
        Area = self.Area.with_user(self.route_manager)
        new_area = Area.create({'name': 'Manager Area'})
        new_area.name = 'Manager Area Updated'
        new_area.unlink()
        # Manager group implies the user group (read rights inherited)
        self.assertIn(self.group_user, self.group_manager.all_implied_ids)

    # ------------------------------------------------------------------
    # 7. Settings enforcement
    # ------------------------------------------------------------------
    def test_19_require_area_on_customer_setting(self):
        if 'customer_rank' not in self.Partner._fields:
            self.skipTest("The customer_rank field requires the sale module")
        self.company.distribution_require_area_on_customer = True
        try:
            with self.assertRaises(ValidationError):
                self.Partner.create({
                    'name': 'Customer Without Area',
                    'company_id': self.company.id,
                    'customer_rank': 1,
                })
            # Same-company customer WITH an area is allowed
            partner = self.Partner.create({
                'name': 'Customer With Area',
                'company_id': self.company.id,
                'customer_rank': 1,
                'distribution_area_id': self.area_child.id,
            })
            self.assertTrue(partner.distribution_area_id)
        finally:
            self.company.distribution_require_area_on_customer = False

    def test_20_default_area_on_partner(self):
        self.company.distribution_default_area_id = self.area_root
        try:
            partner_form = Form(self.Partner)
            self.assertEqual(partner_form.distribution_area_id, self.area_root)
        finally:
            self.company.distribution_default_area_id = self.Area

    def test_21_multi_area_setting_off(self):
        self.company.distribution_allow_multi_area_employee = False
        try:
            with self.assertRaises(ValidationError):
                self.Employee.create({
                    'name': 'Single Area Only',
                    'is_distribution_employee': True,
                    'distribution_area_ids': [
                        (6, 0, [self.area_root.id, self.area_child.id])],
                })
        finally:
            self.company.distribution_allow_multi_area_employee = True

    def test_22_require_area_on_employee_setting(self):
        self.company.distribution_require_area_on_distribution_employee = True
        try:
            with self.assertRaises(ValidationError):
                self.Employee.create({
                    'name': 'No Area Employee',
                    'is_distribution_employee': True,
                })
        finally:
            self.company.distribution_require_area_on_distribution_employee = False
