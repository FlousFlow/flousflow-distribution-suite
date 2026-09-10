import { Component } from "@odoo/owl";
import { registry } from "@web/core/registry";
import { useService } from "@web/core/utils/hooks";
import { _t } from "@web/core/l10n/translation";

const GEOLOCATION_OPTIONS = [
    { enableHighAccuracy: true, timeout: 8000, maximumAge: 0 },
    { enableHighAccuracy: false, timeout: 15000, maximumAge: 0 },
];

function getPosition() {
    return new Promise((resolve, reject) => {
        if (!navigator.geolocation) {
            reject({ code: "UNSUPPORTED" });
            return;
        }
        // Try high accuracy first; if the fix is unavailable or times out,
        // retry once with network-based location (works on laptops/desktops
        // without GPS hardware).
        const attempt = (index) => {
            if (index >= GEOLOCATION_OPTIONS.length) {
                reject({ code: 3 });
                return;
            }
            navigator.geolocation.getCurrentPosition(
                resolve,
                (err) => {
                    if (index === 0 && err && (err.code === 2 || err.code === 3)) {
                        attempt(index + 1);
                    } else {
                        reject(err);
                    }
                },
                GEOLOCATION_OPTIONS[index]
            );
        };
        attempt(0);
    });
}

function geolocationErrorMessage(err) {
    if (err && err.code === "UNSUPPORTED") {
        return _t("Geolocation is not supported by this browser, or the page is not served over HTTPS.");
    }
    if (err && err.code === 1) {
        return _t("Location permission was denied.");
    }
    if (err && err.code === 2) {
        return _t("Unable to determine the current location.");
    }
    if (err && err.code === 3) {
        return _t("Location request timed out. Try again or paste a Google Maps link instead.");
    }
    return _t("Unable to determine the current location.");
}

export class PartnerLocationButtons extends Component {
    static template = "flousflow_partner_location.PartnerLocationButtons";

    setup() {
        this.orm = useService("orm");
        this.notification = useService("notification");
        this.dialog = useService("dialog");
    }

    get record() {
        return this.props.record;
    }

    get hasCoords() {
        const data = this.record.data;
        return Boolean(data.partner_latitude) || Boolean(data.partner_longitude);
    }

    async _persist() {
        // Save immediately for already-saved records; leave new records to the
        // normal Save action so we never create partial records.
        if (this.record.resId) {
            await this.record.save();
        }
    }

    /**
     * Reverse-geocode the given coords and fill the (still unsaved) form's
     * address card. Best-effort: a geocoder outage must not block the
     * capture flow — the server backfills on save.
     */
    async _applyAddressFromCoords(latitude, longitude) {
        let address;
        try {
            address = await this.orm.silent.call(
                "res.partner", "get_address_from_location",
                [latitude, longitude],
            );
        } catch {
            // geocoder outage: keep the captured coords, server backfills
            return;
        }
        // Update field by field: a failure on one field (e.g. a many2one
        // whose value is not accepted by the form) must not discard the
        // rest of the address — the country/city fill is exactly what lets
        // the user pass required-field rules on a new contact.
        const charVals = {};
        for (const fname of ["street", "street2", "city", "zip"]) {
            if (address[fname]) {
                charVals[fname] = address[fname];
            }
        }
        try {
            await this.record.update(charVals);
        } catch (e) {
            this.notification.add(
                _t("Address fields could not be filled automatically."),
                { type: "warning" },
            );
        }
        for (const [fname, value] of [["country_id", address.country_id], ["state_id", address.state_id]]) {
            if (!value) {
                continue;
            }
            try {
                await this.record.update({ [fname]: [value[0], value[1]] });
            } catch {
                this.notification.add(
                    _t("Could not set %(field)s automatically.", { field: fname }),
                    { type: "warning" },
                );
            }
        }
    }

    async onGetCurrentLocation() {
        try {
            const position = await getPosition();
            const coords = position.coords;
            await this.record.update({
                partner_latitude: coords.latitude,
                partner_longitude: coords.longitude,
                location_accuracy: coords.accuracy !== undefined ? coords.accuracy : false,
                location_source: "gps",
            });
            await this._applyAddressFromCoords(coords.latitude, coords.longitude);
            await this._persist();
            const acc = coords.accuracy !== undefined ? Math.round(coords.accuracy) : null;
            if (acc !== null && acc > 500) {
                // Browser location on desktops comes from WiFi/IP and can be
                // kilometers off. Tell the user instead of silently saving.
                this.notification.add(
                    _t("Location saved, but accuracy is %(acc)s m — it may be "
                       + "inaccurate (desktop WiFi/IP location). Prefer a "
                       + "mobile device or paste a Maps link.", { acc }),
                    { type: "warning", sticky: true },
                );
            } else {
                this.notification.add(
                    _t("Location saved successfully (accuracy ±%(acc)s m).", { acc: acc === null ? "?" : acc }),
                    { type: "success" },
                );
            }
        } catch (err) {
            this.notification.add(geolocationErrorMessage(err), { type: "danger" });
        }
    }

    async onExtractLocation() {
        const url = (this.record.data.location_url || "").trim();
        if (!url) {
            this.notification.add(_t("Please enter a Google Maps location link."), { type: "warning" });
            return;
        }
        try {
            const result = await this.orm.call("res.partner", "extract_coordinates", [url]);
            await this.record.update({
                partner_latitude: result.latitude,
                partner_longitude: result.longitude,
                location_url: url,
                location_source: "google_maps_link",
            });
            await this._applyAddressFromCoords(result.latitude, result.longitude);
            await this._persist();
            this.notification.add(_t("Location saved successfully."), { type: "success" });
        } catch (err) {
            const message =
                err && err.data && err.data.message
                    ? err.data.message
                    : _t("Unable to extract coordinates from this link.");
            this.notification.add(message, { type: "danger" });
        }
    }

    _open(url) {
        window.open(url, "_blank", "noopener,noreferrer");
    }

    _requireCoords() {
        if (!this.hasCoords) {
            this.notification.add(_t("Customer location has not been set yet."), { type: "warning" });
            return false;
        }
        return true;
    }

    /**
     * Address string for map fallbacks when no coordinates were captured.
     */
    _addressQuery() {
        const d = this.record.data;
        const parts = [d.street, d.street2, d.city, d.zip, d.state_id && d.state_id[1], d.country_id && d.country_id[1]]
            .filter((part) => part && String(part).trim());
        return parts.map((part) => encodeURIComponent(String(part).trim())).join(",");
    }

    onOpenLocation() {
        if (this.hasCoords) {
            const { lat, lng } = this._bestCoords();
            this._open(`https://www.google.com/maps/search/?api=1&query=${lat},${lng}`);
            return;
        }
        // No coordinates yet: fall back to the saved address.
        const query = this._addressQuery();
        if (!query) {
            this.notification.add(
                _t("Set a location or fill the address first."),
                { type: "warning" },
            );
            return;
        }
        this._open(`https://www.google.com/maps/search/?api=1&query=${query}`);
    }

    onGetDirections() {
        if (this.hasCoords) {
            const { lat, lng } = this._bestCoords();
            this._open(`https://www.google.com/maps/dir/?api=1&destination=${lat},${lng}`);
            return;
        }
        const query = this._addressQuery();
        if (!query) {
            this.notification.add(
                _t("Set a location or fill the address first."),
                { type: "warning" },
            );
            return;
        }
        this._open(`https://www.google.com/maps/dir/?api=1&destination=${query}`);
    }

    async onFillAddress() {
        if (!this._requireCoords()) {
            return;
        }
        const { lat, lng } = this._bestCoords();
        try {
            const address = await this.orm.call(
                "res.partner", "get_address_from_location", [lat, lng]
            );
            await this.record.update({
                street: address.street,
                street2: address.street2,
                city: address.city,
                zip: address.zip,
                country_id: address.country_id,
                state_id: address.state_id,
            });
            await this._persist();
            this.notification.add(_t("Address filled from location."), { type: "success" });
        } catch (err) {
            const message =
                err && err.data && err.data.message
                    ? err.data.message
                    : _t("Unable to determine the address from this location.");
            this.notification.add(message, { type: "danger" });
        }
    }

    async onClearLocation() {
        if (!this.hasCoords) {
            return;
        }
        const confirmed = await this.dialog.confirm(
            _t("Clear this customer's location?"),
            { confirmLabel: _t("Clear"), cancelLabel: _t("Cancel") }
        );
        if (!confirmed) {
            return;
        }
        await this.record.update({
            partner_latitude: false,
            partner_longitude: false,
            location_accuracy: false,
            location_url: false,
            location_source: false,
        });
        await this._persist();
        this.notification.add(_t("Location cleared."), { type: "success" });
    }
}

registry.category("fields").add("partner_location_buttons", {
    component: PartnerLocationButtons,
    supportedTypes: ["boolean"],
});
