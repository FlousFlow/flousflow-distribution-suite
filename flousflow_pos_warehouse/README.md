# POS Warehouse Assignment

Connect every Point of Sale to the right warehouse.

Each Point of Sale configuration is assigned to a **warehouse**. Every sale made
at that POS is deducted from the assigned warehouse's stock — through Odoo's
standard `stock.picking` / `stock.move` flow — and every return goes back to
that same warehouse. The warehouse belongs to the **POS configuration**, not to
the cashier, so any cashier working at the same POS uses the same warehouse.

> **Odoo 19 · Community Edition**
> No core files are modified. No parallel inventory engine: the module reuses
> the standard `pos.config.warehouse_id`, `stock.warehouse.pos_type_id` and
> Odoo's normal picking architecture.

---

## Architecture

```text
Point of Sale  →  pos.config
                      ↓  assigned warehouse
                  stock.warehouse
                      ↓  pos_type_id (auto-created "PoS Orders")
                  stock.picking.type  (outgoing)
                      ↓  default_location_src_id
                  warehouse stock location  (e.g. CAI/Stock)
                      ↓
                  POS order → stock.picking → assigned warehouse stock
```

Odoo 19 already routes every POS order through `pos.config.picking_type_id`:
an outgoing operation type whose **source location is the warehouse's stock
location**. This module makes the **warehouse** the primary, user-facing
setting and derives the operation type automatically.

### Sale flow

```text
POS sale  →  pos.order
                ↓  config.picking_type_id
            outgoing picking
                ↓  source = warehouse stock location
            warehouse inventory decreases
```

### Return flow

```text
POS return  →  pos.order (negative lines)
                    ↓  same picking type
                return picking
                    ↓  destination = warehouse stock location
                warehouse inventory increases
```

---

## Installation

1. Install the **Point of Sale** and **Inventory** applications.
2. Install this module: `Apps → Update Apps List → POS Warehouse Assignment`.

Or from the command line:

```bash
docker exec odoo_clean_web odoo \
  --db_host=db --db_user=odoo --db_password=odoo \
  -i flousflow_pos_warehouse -d aaa --stop-after-init
```

## Configuration

1. Create your warehouses: **Inventory → Configuration → Warehouses**
   (e.g. *Cairo* `CAI`, *Giza* `GIZ`, *Alexandria* `ALX`).
2. Open each Point of Sale:
   **Point of Sale → Configuration → Point of Sale → [POS] → Inventory** tab.
3. Set **POS Warehouse** and save.

The **Operation Type** and **Source Location** are derived automatically
(e.g. `Cairo: PoS Orders` / `CAI/Stock`). You never need to touch Odoo's
logistics configuration manually.

## Usage

- Open a POS session at a Point of Sale and sell as usual — the stock is
  deducted from the assigned warehouse only.
- Returns (full or partial) go back into the same warehouse.
- Several Point of Sale configurations can share one warehouse.
- The assigned warehouse **cannot be changed while a session is open** — close
  the session first (prevents a session from consuming two warehouses).

## Multi-company behaviour

A Point of Sale can only use a warehouse of **its own company**. Selecting
another company's warehouse raises a clear validation error, so company A's
POS can never consume company B's inventory. Standard record rules and
`allowed_company_ids` are respected.

## Dependencies

- `point_of_sale`
- `stock` (already a dependency of `point_of_sale`)

## Known limitations

- **No "prevent out-of-stock" validation.** The module intentionally does not
  block a sale when the assigned warehouse has insufficient stock, because
  real-time stock checks would break the offline POS workflow. Availability is
  still *displayed* per warehouse by the standard POS product info popup.
- **Warehouse is set on the POS configuration**, never per cashier — this is
  the intended design.

## Testing

```bash
# Refresh the test DB, then run the module tests
docker exec odoo_clean_web odoo \
  --db_host=db --db_user=odoo --db_password=odoo \
  --test-enable -u flousflow_pos_warehouse -d test --stop-after-init
```

Covered scenarios:

- Warehouse drives operation type and source location.
- Sale deducts from the assigned warehouse only (other warehouses untouched).
- Partial and full returns go back to the same warehouse.
- Multiple POS share one warehouse.
- Multi-company mismatch is blocked.
- Warehouse / operation type change is blocked while a session is open.
- Service products create no stock picking.
- Lot-tracked products are sold from the assigned warehouse.

## Support

- Author: **Flous Flow**
- Website: <https://flousflow.com>
- License: LGPL-3
