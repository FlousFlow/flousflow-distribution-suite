/** Client action: capture the customer GPS location from the browser. */
import { Component, onWillStart, useState } from "@odoo/owl";
import { registry } from "@web/core/registry";
import { useService } from "@web/core/utils/hooks";
import { _t } from "@web/core/l10n/translation";

import { getGPSPosition, GPS_ERROR_MESSAGES } from "./gps_service";

export class CustomerLocationAction extends Component {
    static template = "flousflow_distribution_route_gps.GpsFlowDialog";

    setup() {
        this.orm = useService("orm");
        this.action = useService("action");
        this.notification = useService("notification");
        this.state = useState({
            message: _t("Getting your location..."),
            busy: true,
        });
        this.partnerId = this.props.action.params.partner_id;
        onWillStart(() => this.run());
    }

    close() {
        if (this.props.close) {
            this.props.close();
        }
    }

    async run() {
        let position;
        try {
            position = await getGPSPosition();
        } catch (error) {
            this.notify(
                "danger",
                GPS_ERROR_MESSAGES[(error && error.type)] ||
                    GPS_ERROR_MESSAGES.position_unavailable,
            );
            this.close();
            return;
        }

        this.state.message = _t("Saving the location...");
        try {
            await this.orm.call("res.partner", "gps_save_customer_location", [
                [this.partnerId],
            ], {
                latitude: position.latitude,
                longitude: position.longitude,
                accuracy: position.accuracy,
                gps_timestamp: position.timestamp,
                source: "device_gps",
            });
        } catch (error) {
            this.close();
            return;
        }
        this.notify(
            "success",
            _t("Customer location captured (accuracy ±%s m).", Math.round(position.accuracy)),
        );
        this.close();
        this.action.doAction({
            type: "ir.actions.act_window",
            res_model: "res.partner",
            res_id: this.partnerId,
            views: [[false, "form"]],
            target: "current",
        });
    }

    notify(type, message) {
        this.notification.add(message, { type, title: _t("GPS") });
    }
}

registry.category("actions").add(
    "distribution_gps.capture_location",
    CustomerLocationAction,
);
