# -*- coding: utf-8 -*-
{
    'name': 'Distribution Vehicle (Fleet ↔ Warehouse ↔ POS)',
    'version': '19.0.1.1.0',
    'category': 'Sales/Distribution',
    'summary': 'Dedicated warehouse and POS per distribution vehicle, loading/unloading and employee assignments',
    'description': """
FlousFlow Distribution Management - Vehicle Core
================================================
Each distribution vehicle is a standard `fleet.vehicle` bound 1:1 to a
dedicated `stock.warehouse` (the vehicle IS a warehouse from the user's
point of view) with its own POS configuration:

* Vehicle ↔ Dedicated Warehouse (unique per active vehicle)
* Vehicle ↔ POS Configuration (bound to the vehicle warehouse)
* Employee assignments with full history (driver / sales rep / helper...)
* Load Vehicle / Unload Vehicle via standard stock pickings
* POS orders keep a historical vehicle + warehouse snapshot
* Salesmen only see their own vehicle's POS and warehouse
* Server-side validation: POS warehouse must match the cashier's vehicle
* Compatible with Lots, Expiration dates, UoM, Packages, Multi-company

Reuses flousflow_pos_warehouse (POS ↔ warehouse binding) and the standard
fleet/stock/POS models. No direct quant manipulation, no core changes.
""",
    'author': 'Flous Flow',
    'website': 'https://flousflow.com',
    'license': 'LGPL-3',
    'depends': [
        'fleet',
        'stock',
        'hr',
        'point_of_sale',
        'flousflow_pos_warehouse', 'flousflow_branch_analytic',],
    'data': [
        'security/security.xml',
        'security/ir.model.access.csv',
        'views/fleet_vehicle_views.xml',
        'views/hr_employee_views.xml',
        'views/pos_views.xml',
        'views/res_config_settings_views.xml',
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
