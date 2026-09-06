<div align="center">

# FlousFlow Distribution Management Suite

**9 integrated modules** for Odoo 19 Community — routes & visits, GPS geofencing,
vehicle warehouses & POS, commercial sales & collections with a full
operational-to-accounting workflow.

</div>

## Modules

| Module | Purpose |
|---|---|
| `flousflow_distribution_route_base` | Master data foundation: areas, visit types, employees & customers |
| `flousflow_distribution_route_management` | Route planning & visit execution |
| `flousflow_distribution_route_gps` | GPS capture, distance & geofence validation |
| `flousflow_distribution_vehicle` | Dedicated warehouse & POS per vehicle, loading/unloading |
| `flousflow_distribution_vehicle_route` | Binds routes to the assigned vehicle (historical snapshot) |
| `flousflow_distribution_dashboard` | Management dashboard & analytics (read-only) |
| `flousflow_distribution_dashboard_gps` | Dashboard GPS analytics (auto-installs with GPS module) |
| `flousflow_distribution_dashboard_vehicle` | Dashboard vehicle analytics (auto-installs with vehicles) |
| `flousflow_distribution_commercial` | Visits ↔ Sales Orders ↔ POS ↔ Collections ↔ Accounting |

## Installation

1. Add this repository to your Odoo `addons_path`.
2. Update the apps list and install **Distribution Route Management** (core modules
   install automatically via dependencies).
3. Install the optional modules you need (Vehicle, GPS, Dashboard, Commercial).

## Test

```bash
odoo -d <db> -u flousflow_distribution_commercial --test-enable \
  --test-tags /flousflow_distribution_commercial --stop-after-init
```

## License

LGPL-3 — see [LICENSE](LICENSE).

© FlousFlow — [flousflow.com](https://flousflow.com)
