{
    'name': 'POS Warehouse Assignment',
    'version': '19.0.1.3.0',
    'category': 'Sales/Point of Sale',
    'sequence': 10,
    'summary': 'Assign each Point of Sale to a specific warehouse so POS sales deduct from that warehouse only.',
    'description': """
POS Warehouse Assignment
========================

Connect every Point of Sale to the right warehouse. Each POS configuration is
assigned to a warehouse; every sale made at that POS is deducted from the
assigned warehouse's stock (through the standard Odoo ``stock.picking`` /
``stock.move`` flow), and every return goes back to that same warehouse.

The warehouse belongs to the **POS configuration**, not to the cashier: any
cashier working at the same Point of Sale uses the same assigned warehouse.

Key features
============

* **POS → Warehouse assignment** — a dedicated *Inventory* section on each
  Point of Sale configuration. Pick the warehouse; the operation type and the
  source stock location are derived automatically.
* **Correct stock deduction** — POS sales create the standard Odoo outgoing
  picking whose source location is the assigned warehouse's stock location
  (e.g. ``CAI/Stock``), so other warehouses are never touched.
* **Warehouse-based returns** — returns go back into the assigned warehouse's
  stock, never into the company's default warehouse.
* **Multiple POS per warehouse** — several Point of Sale configurations can
  share the same warehouse.
* **Cashier independent** — the warehouse is tied to the POS configuration,
  not to the logged-in user or employee.
* **Session safety** — the assigned warehouse (and its operation type) cannot
  be changed while a POS session is open, so one session never creates stock
  moves from two different warehouses.
* **Multi-company safe** — a POS can only use a warehouse of its own company;
  selecting another company's warehouse is blocked with a clear error.
* **Native integration** — no parallel inventory engine: the module reuses the
  standard ``pos.config.warehouse_id``, ``stock.warehouse.pos_type_id`` and
  Odoo's normal picking architecture. Stock valuation, lots/serials, services
  and the POS product availability display behave exactly as in standard Odoo.

No core files are modified. Everything is done through standard inheritance.

Configuration
=============

1. Create your warehouses (Inventory -> Configuration -> Warehouses).
2. Point of Sale -> Configuration -> Point of Sale -> open a POS -> *Inventory*
   tab -> set *POS Warehouse*.
3. Save. The *Operation Type* and *Source Location* are derived automatically.

Compatibility
=============

Verified against Odoo 19 (Community Edition).
""",
    'author': 'Flous Flow',
    'website': 'https://flousflow.com',
    'icon': '/flousflow_pos_warehouse/static/description/icon.png',
    'images': [
        'static/description/thumbnail.png',
        'static/description/banner.png',
        'static/description/cover.png',
        'static/description/icon.png',
    ],
    'license': 'LGPL-3',
    'depends': ['point_of_sale', 'stock'],
    'data': [
        'views/pos_config_views.xml',
    ],
    'installable': True,
    'application': False,
    'auto_install': False,
}
