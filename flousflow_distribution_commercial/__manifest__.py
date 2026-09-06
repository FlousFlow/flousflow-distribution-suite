# -*- coding: utf-8 -*-
{
    'name': 'Distribution Sales & Collection Integration',
    'version': '19.0.1.0.0',
    'category': 'Sales/Distribution',
    'summary': 'Link Route Visits to Sales Orders, POS Sales and Customer '
               'Collections with an operational-to-accounting workflow',
    'description': """
FlousFlow Distribution Management - Commercial Integration
==========================================================
Answers "what happened commercially during the visit?":

* Quotation / Sale Order explicitly linked to the Visit
  (standard sale.order - no custom sales engine)
* POS Order explicitly linked to the Visit (metadata survives
  offline order sync; historical snapshots)
* Operational Customer Collection model with submit → validate →
  standard account.payment workflow (no salesman posting)
* Partial / multiple-invoice / unallocated / overpayment policies
* Commercial summaries on Visit and Route Plan
* Security: distribution users never gain accounting rights,
  no sudo accounting bypass

Uses standard sale.order / pos.order / account.payment /
account.move models. Linking, validation, workflow, audit only.
""",
    'author': 'Flous Flow',
    'website': 'https://flousflow.com',
    'license': 'LGPL-3',
    'depends': [
        'flousflow_distribution_route_management',
        'flousflow_distribution_vehicle_route',
        'sale_management',
        'point_of_sale',
        'account',
    ],
    'data': [
        'security/security.xml',
        'security/ir.model.access.csv',
        'data/ir_sequence_data.xml',
        'views/distribution_visit_collection_views.xml',
        'views/distribution_route_visit_views.xml',
        'views/distribution_route_plan_views.xml',
        'views/distribution_visit_type_views.xml',
        'views/sale_order_views.xml',
        'views/pos_order_views.xml',
        'views/res_partner_views.xml',
        'views/hr_employee_views.xml',
        'views/res_config_settings_views.xml',
        'views/menu_views.xml',
    ],
    'images': [
        'static/description/icon.png',
    ],
    'assets': {
        # The visit-context patch touches the POS frontend model, which
        # only exists inside the POS asset bundle.
        'point_of_sale._assets_pos': [
            'flousflow_distribution_commercial/static/src/js/pos_visit_patch.js',
        ],
    },
    'installable': True,
    'application': False,
    'auto_install': False,
}
