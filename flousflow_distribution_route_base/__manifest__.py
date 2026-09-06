# -*- coding: utf-8 -*-
{
    'name': 'Distribution Route Base',
    'version': '19.0.1.1.0',
    'category': 'Sales/Distribution',
    'summary': 'Distribution master data foundation: areas, visit types, employee and customer configuration',
    'description': """
FlousFlow Distribution Management - Foundation Module
=====================================================
Core master data and configuration layer for the FlousFlow Distribution
Management suite:

* Hierarchical Distribution Areas (with manager, employees and sub-areas)
* Configurable Visit Types
* Distribution configuration on Employees (areas, supervisor)
* Distribution Area on Customers (Contacts)
* Foundation settings (multi-area, required area policies)

This module contains NO route planning, visits, GPS or transactions.
Those capabilities come in separate extension modules that build on this
foundation.
""",
    'author': 'FlousFlow',
    'website': 'https://flousflow.com',
    'license': 'LGPL-3',
    'depends': ['base', 'hr'],
    'data': [
        'security/security.xml',
        'security/ir.model.access.csv',
        'data/distribution_visit_type_data.xml',
        'views/distribution_area_views.xml',
        'views/distribution_visit_type_views.xml',
        'views/hr_employee_views.xml',
        'views/res_partner_views.xml',
        'views/res_config_settings_views.xml',
        'views/menu_views.xml',
    ],
    'images': [
        'static/description/icon.png',
    ],
    'installable': True,
    'application': True,
    'auto_install': False,
}
