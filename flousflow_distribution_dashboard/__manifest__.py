# -*- coding: utf-8 -*-
{
    'name': 'Distribution Performance Dashboard',
    'version': '19.0.1.0.0',
    'category': 'Sales/Distribution',
    'summary': 'Management dashboard and analytics for distribution routes, '
               'visits, employees, areas and customers (read-only)',
    'description': """
FlousFlow Distribution Management - Performance Dashboard
=========================================================
Read / Analyze / Aggregate / Report ONLY. Creates no business workflow,
modifies no route/visit/GPS/vehicle state.

* One screen for daily operations visibility (KPI cards + tables)
* KPIs: Planned/Started/Completed Routes, Planned/Executed/Successful/
  Unsuccessful/Pending/Needs-Revisit Visits, Execution Rate, Success Rate
* Time analytics: average visit duration, arrival variance, late delay
* Performance tables: Employee, Area, Customer, Visit Type, Route
* Daily trend + result/state distributions
* Needs Attention section (delayed visits, late starts, low execution)
* Full drill-down: every KPI opens the exact records behind it
  (identical domain, identical count)
* Optional extension modules: dashboard_gps / dashboard_vehicle
* No sudo: standard record rules and allowed companies apply
* read_group based aggregation (no N+1), works on 30k+ visits

Future sales/collections modules can register extra sections without
touching the dashboard core.
""",
    'author': 'Flous Flow',
    'website': 'https://flousflow.com',
    'license': 'LGPL-3',
    'depends': [
        'flousflow_distribution_route_management',
    ],
    'data': [
        'security/security.xml',
        'views/res_config_settings_views.xml',
        'views/distribution_visit_views.xml',
        'views/menu_views.xml',
    ],
    'assets': {
        'web.assets_backend': [
            'flousflow_distribution_dashboard/static/src/scss/dashboard.scss',
            'flousflow_distribution_dashboard/static/src/js/dashboard_action.js',
            'flousflow_distribution_dashboard/static/src/xml/dashboard_templates.xml',
        ],
    },
        'images': [
        'static/description/index.html',
        'static/description/thumbnail.png',
        'static/description/cover.png',
        'static/description/banner.png',
        'static/description/icon.png',
    ],
'installable': True,
    'application': False,
    'auto_install': False,
}
