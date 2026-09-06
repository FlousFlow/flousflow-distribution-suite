# -*- coding: utf-8 -*-
{
    'name': 'Distribution Vehicle Route Integration',
    'version': '19.0.1.0.0',
    'category': 'Sales/Distribution',
    'summary': 'Bind route plans to the representative\'s assigned vehicle, '
               'warehouse and POS (historical snapshot at confirm)',
    'description': """
FlousFlow Distribution Management - Route ↔ Vehicle Integration
===============================================================
Extension module linking Distribution Route Management with the
Distribution Vehicle Core:

* Route Plan resolves the employee's active vehicle assignment
  automatically (employee + route date)
* Auto-fill: Vehicle → Vehicle Warehouse → Vehicle POS
* HISTORICAL SNAPSHOT at Confirm: the route keeps its vehicle/warehouse/
  POS even when the employee is later reassigned to another vehicle
* Validation at Confirm and at Start Route (vehicle active, configured,
  company consistency, assignment validity)
* Concurrent route protection: one route in progress per employee and
  per vehicle
* Manager can adjust vehicle data before Start; nobody after
* Smart buttons: Routes on Vehicle and on Assignment, Vehicle Stock and
  POS Orders on the Route
* Overridable helpers for the future Sales/Collections module
* Settings: require vehicle / require vehicle POS on routes

Does NOT include: GPS tracking, route maps, optimization, expenses,
fuel, accounting, collections, commissions, dashboards.
""",
    'author': 'Flous Flow',
    'website': 'https://flousflow.com',
    'license': 'LGPL-3',
    'depends': [
        'flousflow_distribution_vehicle',
        'flousflow_distribution_route_management',
    ],
    'data': [
        'security/security.xml',
        'security/ir.model.access.csv',
        'views/res_config_settings_views.xml',
        'views/distribution_route_plan_views.xml',
    ],
    'images': [
        'static/description/icon.png',
    ],
    'installable': True,
    'application': False,
    'auto_install': False,
}
