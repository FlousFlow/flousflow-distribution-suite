{
    "name": "Customer Geo Location",
    "version": "19.0.1.0.0",
    "category": "Sales/CRM",
    "summary": "Save customer GPS locations and open them in Google Maps",
    "description": """
Customer Geo Location (Odoo 19)
===============================

Capture and reuse the exact geographic location of a customer / contact.

Two ways to capture a location:

* **Get Current Location** — uses the browser/device Geolocation API to
  capture latitude and longitude (plus accuracy) at the customer's site.
* **Extract Location** — paste a Google Maps / WhatsApp-shared link and the
  module parses the coordinates out of the URL (including short
  ``maps.app.goo.gl`` links, resolved safely server-side).

The canonical source of truth is the coordinate pair (reusing the standard
``res.partner`` fields ``partner_latitude`` / ``partner_longitude``), not the
URL. Saved coordinates can be reused by any authorized user through:

* **Open Location** — opens Google Maps at the saved coordinates.
* **Get Directions** — opens Google Maps directions to the saved coordinates.
* **Fill Address from Location** — reverse-geocodes the saved coordinates
  (OpenStreetMap, no API key) and fills the partner address card (opt-in).

No Google Maps API key is required.
""",
    "license": "LGPL-3",
    "author": "Flous Flow",
    "website": "https://flousflow.com",
    "depends": [
        "base",
        "web",
    ],
    "data": [
        "security/res_partner_location_security.xml",
        "views/res_partner_views.xml",
    ],
    "assets": {
        "web.assets_backend": [
            "flousflow_partner_location/static/src/js/partner_location_widget.js",
            "flousflow_partner_location/static/src/xml/partner_location_widget.xml",
            "flousflow_partner_location/static/src/scss/partner_location.scss",
        ],
    },
    "images": [
        "static/description/thumbnail.png",
        "static/description/banner.png",
        "static/description/cover.png",
        "static/description/icon.png",
        "static/description/screenshots/01_customer_location.png",
    ],
    "installable": True,
    "application": False,
    "auto_install": False,
}
