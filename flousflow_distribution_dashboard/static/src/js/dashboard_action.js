/** @odoo-module **/
/* Distribution Performance Dashboard — read-only client action (Odoo 19 OWL).
 * All figures come from a single RPC to distribution.dashboard.data.
 * Every card/table cell drills down through the SAME server domain builder
 * used for aggregation, so card numbers always equal list counts. */
import { registry } from "@web/core/registry";
import { useService } from "@web/core/utils/hooks";
import { Component, useState, onWillStart } from "@odoo/owl";

const PERIODS = [
    ["today", "Today"],
    ["yesterday", "Yesterday"],
    ["this_week", "This Week"],
    ["last_week", "Last Week"],
    ["this_month", "This Month"],
    ["last_month", "Last Month"],
    ["custom", "Custom Period"],
];

function pct(value) {
    return (value === undefined || value === null) ? "0.00" : value.toFixed(2);
}
function num1(value) {
    return (value === undefined || value === null) ? "0.0" : value.toFixed(1);
}

export class DistributionDashboard extends Component {
    setup() {
        this.orm = useService("orm");
        this.action = useService("action");
        this.notificationService = useService("notification");
        this.periods = PERIODS;
        this.state = useState({
            loading: true,
            error: false,
            data: null,
            filters: {
                period: "today",
                date_from: "",
                date_to: "",
                employee_id: 0,
                supervisor_id: 0,
                area_id: 0,
                visit_type_id: 0,
                result_id: 0,
                route_state: "",
            },
        });
        onWillStart(async () => {
            await this.load();
        });
    }

    cleanFilters() {
        const f = this.state.filters;
        const clean = { period: f.period };
        for (const key of ["employee_id", "supervisor_id", "area_id",
            "visit_type_id", "result_id", "vehicle_id"]) {
            if (f[key]) {
                clean[key] = Number(f[key]);
            }
        }
        if (f.route_state) {
            clean.route_state = f.route_state;
        }
        if (f.period === "custom" && f.date_from && f.date_to) {
            clean.date_from = f.date_from;
            clean.date_to = f.date_to;
        }
        return clean;
    }

    async load() {
        this.state.loading = true;
        try {
            this.state.data = await this.orm.call(
                "distribution.dashboard.data",
                "get_dashboard_data",
                [this.cleanFilters()],
            );
            this.state.error = false;
        } catch (error) {
            console.error("distribution dashboard load failed:", error);
            this.state.error = true;
        }
        this.state.loading = false;
    }

    async setPeriod(period) {
        this.state.filters.period = period;
        if (period !== "custom") {
            this.state.filters.date_from = "";
            this.state.filters.date_to = "";
        }
        await this.load();
    }

    async setFilter(key, value) {
        this.state.filters[key] = value;
        await this.load();
    }

    async drill(target, resId) {
        try {
            const action = await this.orm.call(
                "distribution.dashboard.data",
                "get_drill_down",
                [this.cleanFilters(), target, resId || 0],
            );
            await this.action.doAction(action);
        } catch (error) {
            console.error("drill-down failed:", error);
            this.notificationService.add(
                "Could not open the records behind this KPI.", {
                    type: "warning",
                });
        }
    }

    openRecord(model, resId) {
        this.action.doAction({
            type: "ir.actions.act_window",
            res_model: model,
            res_id: resId,
            views: [[false, "form"]],
            target: "current",
        });
    }

    hasData(data) {
        const k = data && data.kpi;
        return Boolean(k && (k.routes.planned || k.visits.planned));
    }

    pct(value) {
        return pct(value);
    }

    num1(value) {
        return num1(value);
    }
}

DistributionDashboard.template =
    "flousflow_distribution_dashboard.Dashboard";

registry.category("actions").add(
    "distribution.dashboard", DistributionDashboard);
