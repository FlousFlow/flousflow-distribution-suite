{
    'name': 'Distribution Vehicle Inspection',
    'version': '19.0.1.1.0',
    'category': 'Sales/Distribution',
    'summary': 'Daily and ad hoc vehicle inspections with driver photo evidence and manager review',
    'description': """
FlousFlow Distribution Vehicle Inspection
=========================================
Run consistent vehicle inspections before a route starts and record the
result with traceable driver responses, notes and photos.

* Inspection templates with ordered questions and response types
* Daily tasks generated automatically for assigned drivers
* Ad hoc inspections for exceptional checks
* Required-before-start questions and validation of required notes/photos
* Manager review with approve/reject decision and audit timestamps
* Overdue detection and in-app notifications for missed inspections

Designed for Odoo 19 Community and the FlousFlow Distribution Management
Suite. Uses standard Odoo mail/activity patterns and keeps inspection data
separate from fleet and route master data.
""",
    'author': 'Flous Flow',
    'website': 'https://flousflow.com',
    'license': 'LGPL-3',
    'depends': ['flousflow_distribution_vehicle_route', 'mail'],
    'data': [
        'security/security.xml',
        'security/ir.model.access.csv',
        'data/inspection_template_data.xml',
        'views/inspection_views.xml',
        'views/menu_views.xml',
    ],
    'images': [
        'static/description/icon.png',
        'static/description/cover.png',
        'static/description/thumbnail.png',
    ],
    'installable': True,
    'application': False,
    'auto_install': False,
}
