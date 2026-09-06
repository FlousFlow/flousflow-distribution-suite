# -*- coding: utf-8 -*-
{
    'name': 'Distribution Route Management',
    'version': '19.0.1.1.0',
    'category': 'Sales/Distribution',
    'summary': 'Route planning and visit execution for distribution representatives',
    'description': """
FlousFlow Distribution Management - Route Planning & Visit Execution
====================================================================
Builds on flousflow_distribution_route_base to provide the operational
route planning layer:

* Route Plans (daily operational routes per distribution employee)
* Route Visits (ordered customer visits with planned vs actual tracking)
* Configurable Visit Results (success / unsuccessful outcomes)
* Complete Visit / Skip Visit / Cancel Route wizards
* Execution Rate vs Success Rate analytics (Pivot / Graph)
* Calendar and Kanban views, customer & employee smart buttons
* Real record rules: representatives see only their own routes/visits

This module intentionally contains NO GPS tracking, NO sales orders,
NO collections accounting and NO vehicle/warehouse integration.
Those come as separate extension modules (GPS, Sales, Vehicle) that
inherit these models without architectural changes.
""",
    'author': 'Flous Flow',
    'website': 'https://flousflow.com',
    'license': 'LGPL-3',
    'depends': [
        'flousflow_distribution_route_base',
        'mail',
    ],
    'data': [
        'security/ir.model.access.csv',
        'security/security.xml',
        'data/ir_sequence_data.xml',
        'data/distribution_visit_result_data.xml',
        'views/distribution_visit_result_views.xml',
        'views/distribution_route_plan_views.xml',
        'views/distribution_route_visit_views.xml',
        'views/res_partner_views.xml',
        'views/hr_employee_views.xml',
        'views/wizard_views.xml',
        'views/menu_views.xml',
    ],
    'images': [
        'static/description/icon.png',
    ],
    'installable': True,
    'application': False,
    'auto_install': False,
}
