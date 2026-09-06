# Customer Geo Location

Save the exact geographic location of a customer / contact in Odoo 19, and
reuse it instantly — open it in Google Maps or get turn-by-turn directions.

> Flous Flow — Odoo 19 module. No Google Maps API key required.

## Features

- **Get Current Location** — captures latitude, longitude and accuracy from the
  browser/device Geolocation API (no server-side IP geolocation).
- **Extract Location** — paste a Google Maps / WhatsApp-shared link and extract
  the coordinates. Supports short `maps.app.goo.gl` links (resolved safely).
- **Open Location** — opens Google Maps at the saved coordinates.
- **Get Directions** — opens Google Maps directions to the customer.
- **Fill Address from Location** — reverse-geocodes the saved coordinates
  (OpenStreetMap, no API key) and fills the partner address card. Opt-in: it
  runs only when you click the button.
- **Clear Location** — clears the saved coordinates after confirmation.
- Coordinates are stored on the standard `res.partner` fields
  `partner_latitude` / `partner_longitude` (no duplicate fields).
- Audit: `Last Location Update` + `Updated By` are set automatically.
- Manual editing of coordinates is limited to the *Manage Customer Locations*
  group; other users see the coordinates read-only.

## Installation

1. Copy the `flousflow_partner_location` folder into your addons path.
2. Install the app (Apps → search "Customer Geo Location" → Install), or
   upgrade it after each change with `-u flousflow_partner_location`.

## Usage

### Using the current GPS location

1. Open a contact → **Customer Location** page.
2. Click **Get Current Location**.
3. Allow the browser location permission.
4. The coordinates are filled in; click **Save** if it is a new record.

### Using a WhatsApp / Google Maps link

1. The customer sends their location on WhatsApp → copy the link.
2. Paste it in **Location Link**.
3. Click **Extract Location**.
4. The coordinates are filled in; then use **Open Location** /
   **Get Directions**.

## Supported Google Maps URL patterns

- `https://www.google.com/maps?q=30.0444,31.2357`
- `https://maps.google.com/?q=30.0444,31.2357`
- `https://www.google.com/maps/search/?api=1&query=30.0444,31.2357`
- `https://www.google.com/maps/place/.../@30.0444,31.2357,17z`
- `https://maps.google.com/?ll=30.0444,31.2357`
- `q=30.0444+31.2357` (plus separator) and `q=loc:30.0444,31.2357`
- Short links: `https://maps.app.goo.gl/...` and `https://goo.gl/...`
  (resolved server-side by following redirects).

## HTTPS requirement

Browser geolocation requires a **secure context**. In production, serve Odoo
over **HTTPS**; otherwise `Get Current Location` will report that geolocation
is unavailable.

## Permissions

- Users who can read the contact can view its location.
- Users who can edit the contact can capture/extract/clear the location.
- Only the *Manage Customer Locations* group can type coordinates manually.

## Security (SSRF protection)

The server only resolves short links for an explicit allowlist of Google Maps
hosts (`google.com`, `www.google.com`, `maps.google.com`, `maps.app.goo.gl`,
`goo.gl` and `*.google.com` subdomains). Literal IPs, private/loopback hosts,
`file://` and other schemes are rejected, redirects are limited (5), and a
short timeout (5s) is applied. The response body is never downloaded.

## Known limitations

- Country-specific Google domains (`google.co.uk`, `google.com.eg`, …) are not
  on the allowlist by default; use the canonical `google.com` link.
- GPS accuracy depends on the device; `Accuracy (m)` records the reported value.
- Short-link resolution requires outbound HTTPS access from the Odoo server.
- **Desktop / localhost**: browsers without GPS hardware (or running over
  `localhost` in an embedded/sandboxed browser) may time out or be unable to
  determine the location. The module retries automatically with network-based
  location, but for the most reliable result use the **Get Current Location**
  button on a real device over HTTPS, or paste a Google Maps link instead.

## License

LGPL-3 — Flous Flow (https://flousflow.com)
