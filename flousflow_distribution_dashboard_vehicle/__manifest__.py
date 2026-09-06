# -*- coding: utf-8 -*-
{
    'name': 'Distribution Dashboard — Vehicle Analytics',
    'version': '19.0.1.0.0',
    'category': 'Sales/Distribution',
    'summary': 'Vehicle section and vehicle analysis reporting for the '
               'distribution dashboard',
    'description': """
Optional add-on for flousflow_distribution_dashboard (requires
flousflow_distribution_vehicle + flousflow_distribution_vehicle_route):

* Vehicle filter in the dashboard filter bar
* Dashboard section: Routes / Visits / Executed / Success Rate per vehicle,
  active route days as a utilization indicator (NOT a time-based
  utilization claim)
* Current Vehicle Stock: standard stock.quant quantities per vehicle
  warehouse — clearly labeled CURRENT stock, never historical (#40)
* Vehicle Analysis reporting menu

Read-only — adds no workflow, changes no vehicle/stock data.
""",
    'author': 'Flous Flow',
    'website': 'https://flousflow.com',
    'license': 'LGPL-3',
    'depends': [
        'flousflow_distribution_dashboard',
        'flousflow_distribution_vehicle_route',
        'stock',
    ],
    'data': [
        'security/security.xml',
        'views/vehicle_analysis_views.xml',
    ],
        'images': [
        'static/description/index.html',
        'static/description/thumbnail.png',
        'static/description/cover.png',
        'static/description/banner.png',
        'static/description/icon.png',
    ],
'installable': True,
    'application': False,
    # Auto-merge: as soon as the dashboard + vehicle-route modules co-exist,
    # the vehicle analytics section installs itself — no manual step.
    'auto_install': True,
}
