/** GPS capture service — browser Geolocation API via Odoo's browser
 * abstraction (no global window access, mockable in tests). */
import { browser } from "@web/core/browser/browser";

/** Map a browser GeolocationPositionError to a stable reason code. */
function mapError(code) {
    // 1 PERMISSION_DENIED, 2 POSITION_UNAVAILABLE, 3 TIMEOUT
    if (code === 1) return "permission_denied";
    if (code === 2) return "position_unavailable";
    if (code === 3) return "timeout";
    return "position_unavailable";
}

/**
 * Request a single GPS position (point-in-time — never watchPosition).
 *
 * @param {Object} [options]
 * @param {number} [options.timeout=15000] ms before giving up
 * @param {number} [options.maximumAge=0] cached positions are not accepted
 * @returns {Promise<{latitude:number, longitude:number, accuracy:number,
 *   timestamp:number}>} resolves with coordinates, or rejects with
 *   {type: "permission_denied"|"position_unavailable"|"timeout"|"unsupported"}
 */
export function getGPSPosition({ timeout = 15000, maximumAge = 0 } = {}) {
    return new Promise((resolve, reject) => {
        if (!browser.navigator || !browser.navigator.geolocation) {
            reject({ type: "unsupported" });
            return;
        }
        browser.navigator.geolocation.getCurrentPosition(
            (position) => {
                resolve({
                    latitude: position.coords.latitude,
                    longitude: position.coords.longitude,
                    accuracy: position.coords.accuracy,
                    timestamp: position.timestamp,
                });
            },
            (error) => reject({ type: mapError(error.code) }),
            { enableHighAccuracy: true, timeout, maximumAge },
        );
    });
}

/** Human-friendly, non-technical messages per failure type. */
export const GPS_ERROR_MESSAGES = {
    permission_denied:
        "Could not get your location. Please enable the browser location permission and try again.",
    timeout:
        "Getting your location took too long. Please try again, preferably outdoors.",
    position_unavailable:
        "Your location is currently unavailable. Please check that location services are enabled and try again.",
    unsupported:
        "Your browser does not support location capture. Please use a modern browser.",
};
