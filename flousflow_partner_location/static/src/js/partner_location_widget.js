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
            await this._persist();
            this.notification.add(_t("Location saved successfully."), { type: "success" });
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

    onOpenLocation() {
        if (!this._requireCoords()) {
            return;
        }
        const { partner_latitude: lat, partner_longitude: lng } = this.record.data;
        this._open(`https://www.google.com/maps/search/?api=1&query=${lat},${lng}`);
    }

    onGetDirections() {
        if (!this._requireCoords()) {
            return;
        }
        const { partner_latitude: lat, partner_longitude: lng } = this.record.data;
        this._open(`https://www.google.com/maps/dir/?api=1&destination=${lat},${lng}`);
    }

    async onFillAddress() {
        if (!this._requireCoords()) {
            return;
        }
        const { partner_latitude: lat, partner_longitude: lng } = this.record.data;
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
