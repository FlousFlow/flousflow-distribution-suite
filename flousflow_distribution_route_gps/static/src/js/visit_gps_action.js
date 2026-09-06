/** Client action: GPS check-in / check-out on a route visit.
 *
 * Flow: browser GPS capture -> server-side validation (distance,
 * geofence, accuracy, age) -> visit start / completion wizard.
 * All business decisions are made server-side; this component only
 * captures coordinates and renders feedback.
 */
import { Component, onWillStart, useState } from "@odoo/owl";
import { registry } from "@web/core/registry";
import { useService } from "@web/core/utils/hooks";
import { _t } from "@web/core/l10n/translation";

import { getGPSPosition, GPS_ERROR_MESSAGES } from "./gps_service";

export class VisitGpsAction extends Component {
    static template = "flousflow_distribution_route_gps.GpsFlowDialog";

    setup() {
        this.orm = useService("orm");
        this.action = useService("action");
        this.notification = useService("notification");
        this.state = useState({
            message: _t("Getting your location..."),
            busy: true,
        });
        this.visitId = this.props.action.params.visit_id;
        this.operation = this.props.action.params.operation; // checkin | checkout
        onWillStart(() => this.run());
    }

    get modelName() {
        return "distribution.route.visit";
    }

    get methodName() {
        return this.operation === "checkin"
            ? "gps_submit_checkin"
            : "gps_submit_checkout";
    }

    close() {
        if (this.props.close) {
            this.props.close();
        } else {
            // Restore the visit form (client action replaced it).
            this.action.doAction(this.refreshAction());
        }
    }

    refreshAction() {
        return {
            type: "ir.actions.act_window",
            res_model: "distribution.route.visit",
            res_id: this.visitId,
            views: [[false, "form"]],
            target: "current",
        };
    }

    notify(type, message) {
        this.notification.add(message, { type, title: _t("GPS") });
    }

    async run() {
        let position;
        try {
            position = await getGPSPosition();
        } catch (error) {
            await this.reportError(error && error.type);
            this.notify(
                "danger",
                GPS_ERROR_MESSAGES[(error && error.type)] ||
                    GPS_ERROR_MESSAGES.position_unavailable,
            );
            this.close();
            return;
        }

        this.state.message = _t("Validating your location...");
        let result;
        try {
            result = await this.orm.call(this.modelName, this.methodName, [
                [this.visitId],
            ], {
                latitude: position.latitude,
                longitude: position.longitude,
                accuracy: position.accuracy,
                gps_timestamp: position.timestamp,
            });
        } catch (error) {
            // Server rejections (UserError) — record the reason in the GPS
            // audit log, then close silently (the web client shows the
            // error message dialog).
            const reason = (error && error.data && error.data.message)
                ? String(error.data.message).slice(0, 200)
                : "submit_error";
            await this.reportError(reason);
            this.close();
            return;
        }
        this.handleResult(result, position);
    }

    async reportError(reason) {
        try {
            await this.orm.call(this.modelName, "gps_log_frontend_error", [
                [this.visitId],
            ], { message: reason || "gps_error" });
        } catch {
            // best effort — never block the UI on audit failures
        }
    }

    handleResult(result) {
        if (result.warning) {
            this.notify(
                "warning",
                _t("You are outside the customer geofence. The visit was allowed and the event was recorded."),
            );
        }
        if (result.status === "blocked") {
            this.notify("danger", result.message);
            this.close();
            if (result.override_allowed && result.override_action) {
                this.action.doAction(result.override_action);
            } else if (result.refresh_action) {
                this.action.doAction(result.refresh_action);
            }
            return;
        }
        this.notify(
            "success",
            this.operation === "checkin"
                ? _t("Check-in recorded at the customer location.")
                : _t("Check-out recorded."),
        );
        this.close();
        if (result.next_action) {
            if (result.refresh_action) {
                this.action.doAction(result.refresh_action);
            }
            this.action.doAction(result.next_action);
        } else if (result.refresh_action) {
            this.action.doAction(result.refresh_action);
        }
    }
}

registry.category("actions").add(
    "distribution_gps.visit_action",
    VisitGpsAction,
);
