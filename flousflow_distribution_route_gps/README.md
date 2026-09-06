# Distribution Route GPS & Geofence (FlousFlow)

**Technical name:** `flousflow_distribution_route_gps`
**Version:** 19.0.1.0.0 · **Odoo:** 19.0 Community · **License:** LGPL-3
**Author:** Flous Flow — https://flousflow.com

Extension module for the FlousFlow Distribution Management suite. Adds
point-in-time GPS capture, distance calculation, geofence validation and a
GPS audit log to the existing Route Visits — **without modifying** the
route management module (pure inheritance + `super()`).

> ⚠️ **HTTPS requirement:** browser Geolocation only works in a *secure
> context*. Production deployments must be served via **HTTPS** (or
> `localhost` for testing). A missing GPS capture on plain HTTP is a
> browser restriction, not a business-logic failure.

## Purpose

When a representative starts/finishes a customer visit, the system records:

- Check-in / check-out time (server time — the authoritative clock)
- Latitude / Longitude / GPS accuracy (meters)
- Customer location snapshot (frozen at check-in)
- Distance from the customer (server-side Haversine, meters)
- Inside / Outside / Unknown geofence status

Plus a full **immutable GPS event log** for audit purposes.

## Requirements

- `flousflow_distribution_route_management` (+ its dependencies)
- `web`
- No external Python dependencies, no paid APIs.

## Architecture

- `distribution.route.visit` — extended with check-in/check-out GPS fields,
  customer location snapshots, manager override fields and indicators.
- `res.partner` — customer GPS coordinates, accuracy, source, geofence
  radius and capture/open-location actions.
- `distribution.visit.type` — `require_gps_checkin` (default True) /
  `require_gps_checkout` (default False) flags.
- `distribution.area` — optional `default_geofence_radius`.
- `res.config.settings` — all policies (see below).
- `distribution.visit.gps.event` — **immutable audit log** (write-once).
- `distribution.gps.override.wizard` — manager override with mandatory
  reason.
- Frontend: OWL client actions (`distribution_gps.visit_action`,
  `distribution_gps.capture_location`) using the `@web/core/browser/browser`
  abstraction (`browser.navigator.geolocation`) — no raw globals, no
  `watchPosition`.

## Customer GPS Setup

1. Open the contact → *Distribution Information* tab → **Capture Current
   Location** (or the button-box button).
2. The browser asks for permission → coordinates + accuracy + user + time
   are saved with `source = device_gps` and a `customer_location_capture`
   audit event.
3. Managers may also type coordinates by hand — such writes are
   automatically stamped `source = manual`.
4. **Open Location** opens the coordinates on OpenStreetMap (no API key).

`has_distribution_location` is a computed flag that correctly treats
`(0, 0)` as a valid coordinate (an explicit `location_set` flag is
maintained — not a truthiness check).

## Geofence Settings (Settings → Distribution Route → GPS & Geofence)

| Setting | Default | Meaning |
|---|---|---|
| Enable GPS Validation | True | Off = module never blocks anything |
| Geofence Validation Mode | warning | disabled / warning / strict |
| Default Geofence Radius (m) | 100 | Used by the hierarchy below |
| Missing Customer Location Policy | warn | allow / warn / block |
| Maximum GPS Accuracy (m) | 100 | Worse accuracy → policy below |
| GPS Accuracy Validation Mode | warning | disabled / warning / strict |
| Maximum GPS Position Age (s) | 30 | Older positions are rejected |
| Validate Check-Out Geofence | False | Off: rep may leave before checkout |

**Effective radius priority:** Partner radius → Area radius → Global
default (`_get_effective_geofence_radius()`).

## Validation Modes

- **Disabled** — GPS recorded when available, nothing is ever blocked.
- **Warning** — outside-geofence check-ins are allowed but recorded as
  `outside` with an audit event and a user warning.
- **Strict** — outside-geofence check-ins are **blocked** (`checkin_rejected`
  event). A Distribution Route Manager may **Override** via the wizard with
  a **mandatory reason** (`manager_override` event + fields on the visit).
  GPS accuracy has the same three modes independently.

Distance, geofence status, accuracy policy and position age are **always
computed server-side** — the frontend only captures and sends coordinates.

## Check-In / Check-Out Flow

```
Start Visit button (GPS version)
  → OWL client action asks the browser for GPS
  → coordinates sent to gps_submit_checkin()
  → server: permissions, state, accuracy, position age, customer
    location policy, distance (Haversine), geofence mode
  → allowed: check-in + snapshots + event + super().action_start_visit()
  → blocked: clean message; manager gets the override wizard
```

Check-out works the same way (`gps_submit_checkout`) and then opens the
normal Complete Visit wizard. Coordinates are never reused from check-in.

## GPS Event Log

`distribution.visit.gps.event` records: `customer_location_capture`,
`checkin`, `checkout`, `checkin_rejected`, `checkout_rejected`, `gps_error`
(permission_denied / timeout / position_unavailable / low_accuracy /
stale_position / missing_customer_location) and `manager_override` — with
coordinates, customer snapshot, distance, radius, status, device and server
timestamps and a message.

- Created **only** by business logic (no user group has create access).
- **Immutable**: write/unlink raise for everyone except the system.
- Users read only their own events (record rule); managers read all events
  in their companies.

## Privacy & Limitations

- **No continuous tracking** — no `watchPosition`, no background location.
  Only three point-in-time captures: customer setup, check-in, check-out.
- GPS is an **operational control, not cryptographic proof** — browser GPS
  can be spoofed. The log stores accuracy, device timestamps and server
  timestamps to support review. The event model is designed for future
  anti-fraud fields (mock-location detection, device id, ip, risk score) —
  intentionally not implemented yet.

## Known GPS Limitations

- Requires HTTPS in production (browser restriction).
- Indoor / bad-signal positions have poor accuracy — configure
  `Maximum GPS Accuracy` + accuracy mode accordingly.
- Stale positions are rejected (device timestamp vs server time).

## Backward Compatibility

Old visits keep their empty GPS fields (status unknown) and are never
recomputed. Routes already in progress keep working; only new captures
record GPS. `distribution_gps.enabled = False` makes the whole module
behave exactly as before it was installed.

## Testing

```bash
odoo -d DB -u flousflow_distribution_route_management,flousflow_distribution_route_gps \
     --test-enable --stop-after-init
```

50 automated tests: Haversine against independent references (equator
degree, quarter circumference, known city pair), coordinate constraints,
radius hierarchy (partner → area → global), inside/outside/boundary,
all three geofence modes, missing-location policies, accuracy modes,
stale position, double check-in, checkout flow + checkout geofence,
manager override (reason required, non-manager blocked), event creation
and immutability, user/manager record rules, multi-company isolation,
old-visit compatibility and the GPS-disabled mode.

Mobile / real-device testing: open Odoo over HTTPS on the phone, log in as
a distribution user, open today's visit and press Start Visit — the browser
permission prompt appears once, then check-in/check-out capture real GPS.
