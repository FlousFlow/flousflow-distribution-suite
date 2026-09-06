# Distribution Route Base

**FlousFlow Distribution Management — Foundation Module** for Odoo 19 Community.

This module is the **core master data layer** of the FlousFlow Distribution
Management suite. It provides the foundation that all future distribution
modules (Route Planning, Visits, GPS Tracking, Vehicle/Warehouse integration)
will build upon.

> ⚠️ This module intentionally contains **no** route plans, visits, GPS,
> check-in/out, sales orders, collections or tracking. Those come in separate
> extension modules.

## Purpose

Provide clean, reusable master data and configuration:

- **Distribution Areas** — hierarchical areas (e.g. Cairo → Maadi → Zahraa Maadi)
  with a manager, employees and sub-areas.
- **Visit Types** — configurable visit categories (Sales, Collection,
  Follow-up…) used later by route/visit modules.
- **Employee Distribution Configuration** — mark employees as distribution
  staff, assign their areas and supervisor.
- **Customer Distribution Area** — link customers to a distribution area.
- **Settings** — foundation policies (default area, multi-area employees,
  required area policies).

## Installation

1. Add the module folder to your `addons_path`.
2. Update the apps list, then install **Distribution Route Base**.

```bash
odoo -i flousflow_distribution_route_base -d YOUR_DB --stop-after-init
```

## Configuration

Open **Distribution → Configuration → Settings**:

| Setting | Effect |
|---|---|
| Default Distribution Area | Area proposed by default on new customer records |
| Allow Multiple Areas per Employee | Allow/disable several areas per distribution employee |
| Require Area on Customer | Block saving customers without a distribution area |
| Require Areas on Distribution Employees | Block saving distribution employees without at least one area |

## Security Groups

| Group | Access |
|---|---|
| **Distribution Route User** (`group_distribution_route_user`) | Read-only on Distribution Areas and Visit Types |
| **Distribution Route Manager** (`group_distribution_route_manager`) | Full CRUD on all master data + settings (inherits User) |

All master data is **multi-company** isolated (record rules per company).

## Distribution Areas

Create hierarchies under **Distribution → Configuration → Distribution Areas**:

- `Cairo`
  - `Maadi`
    - `Zahraa Maadi`
- `Giza`
  - `Dokki`

Circular hierarchies are blocked (an area cannot be its own parent or
ancestor). Area codes are unique per company.

## Visit Types

Default visit types are created (editable, deletable): Sales Visit, Collection,
Follow-up, New Customer, Complaint, Merchandising, Delivery Follow-up, Other.
**No business logic depends on these records** — they are master data only.

## Employee Configuration

On each employee form (**Employees → open employee → Distribution tab**):

- **Distribution Employee** — marks the employee as distribution staff.
- **Distribution Areas** — the areas where the employee operates.
- **Distribution Supervisor** — the employee's supervisor.
- **Distribution Active** — active flag for distribution operations.

The link `Current User → Employee → Distribution Areas` follows the standard
Odoo `hr.employee` / `res.users` relationship (no duplicated user fields).

## Customer Configuration

On any contact (**Contacts → open contact → Distribution Information tab**):

- **Distribution Area** — the distribution area of the customer.

The Contacts search view gains filters (*Has / No Distribution Area*) and a
*Group By Distribution Area*.

## Future Modules (Planned)

This foundation will be consumed by, among others:

- **Route Planning** — route plans per employee/area/customer/visit type.
- **Customer Visits** — visit execution, check-in/check-out, visit results.
- **GPS Tracking / Geofencing** — location services per area and visit.
- **Vehicle / Warehouse Integration** — vehicle and warehouse assignment.
- **Distribution Dashboards** — KPIs over areas, visits and sales.

## Technical Notes

- Models: `distribution.area`, `distribution.visit.type` + extensions of
  `res.partner`, `hr.employee`, `res.config.settings`.
- Dependencies kept minimal: `base`, `hr`.
- No core modifications, no monkey patching, no hardcoded IDs.
- Tests: `odoo --test-enable -u flousflow_distribution_route_base -d DB --stop-after-init`

## License

LGPL-3 — © Flous Flow — https://flousflow.com
