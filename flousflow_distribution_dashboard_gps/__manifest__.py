# -*- coding: utf-8 -*-
{
    'name': 'Distribution Dashboard — GPS Analytics',
    'version': '19.0.1.0.0',
    'category': 'Sales/Distribution',
    'summary': 'GPS compliance section and GPS analysis reporting for the '
               'distribution dashboard',
    'description': """
Optional add-on for flousflow_distribution_dashboard (requires
flousflow_distribution_route_gps):

* Dashboard section: Inside / Outside / Unknown geofence, Outside Rate,
  GPS overrides and GPS errors, average check-in distance and accuracy
* GPS columns in the dashboard employee performance table
* GPS Customer Analysis (customers with consistently large distances may
  have a wrong location on file)
* GPS Analysis reporting menu (pivot + graph + dedicated search filters)

Read-only — adds no workflow and writes no GPS data.
""",
    'author': 'Flous Flow',
    'website': 'https://flousflow.com',
    'license': 'LGPL-3',
    'depends': [
        'flousflow_distribution_dashboard',
        'flousflow_distribution_route_gps',
    ],
    'data': [
        'security/security.xml',
        'views/gps_analysis_views.xml',
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
    # Auto-merge: as soon as the dashboard + GPS modules co-exist, the GPS
    # analytics section installs itself — no manual step for the user.
    'auto_install': True,
}
