# -*- coding: utf-8 -*-
{
    'name': 'Distribution Route GPS & Geofence',
    'version': '19.0.1.1.0',
    'category': 'Sales/Distribution',
    'summary': 'GPS capture, distance and geofence validation for route visits',
    'description': """
FlousFlow Distribution Management - GPS & Geofence Extension
============================================================
Extends the route planning / visit execution modules with:

* Customer GPS location (capture from the browser or manual entry)
* Point-in-time GPS Check-In / Check-Out on route visits
* Server-side Haversine distance calculation
* Geofence validation (Disabled / Warning / Strict modes)
* GPS accuracy and position-age policies
* Immutable GPS event audit log
* Manager override with mandatory reason
* Customer location snapshot on every check-in

This module does NO continuous tracking, NO background location,
NO external paid APIs. Browser Geolocation requires a Secure
Context (HTTPS) in production.
""",
    'author': 'Flous Flow',
    'website': 'https://flousflow.com',
    'license': 'LGPL-3',
    'depends': [
        'flousflow_distribution_route_management',
        'web', 'flousflow_partner_location',],
    'data': [
        'security/ir.model.access.csv',
        'security/security.xml',
        'views/distribution_visit_type_views.xml',
        'views/distribution_area_views.xml',
        'views/res_partner_views.xml',
        'views/res_config_settings_views.xml',
        'views/distribution_visit_gps_event_views.xml',
        'views/gps_analysis_views.xml',
        'views/distribution_route_visit_views.xml',
        'views/wizard/gps_override_wizard_views.xml',
    ],
    'assets': {
        'web.assets_backend': [
            'flousflow_distribution_route_gps/static/src/js/gps_service.js',
            'flousflow_distribution_route_gps/static/src/js/customer_location_action.js',
            'flousflow_distribution_route_gps/static/src/js/visit_gps_action.js',
            'flousflow_distribution_route_gps/static/src/xml/gps_templates.xml',
        ],
    },
    'images': [
        'static/description/icon.png',
    ],
    'installable': True,
    'application': False,
    'auto_install': False,
}
