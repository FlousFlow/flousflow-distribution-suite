/** @odoo-module **/

/* Distribution Visit → POS Order integration.
 *
 * When the POS is opened from a distribution visit (Start POS Sale), the
 * backend sets `distribution_visit_context_raw` on the pos.config. New
 * orders copy that visit id and send it in the sync payload
 * (serializeForORM), so the metadata survives OFFLINE creation and sync.
 * The backend then links the order explicitly to the visit — route and
 * employee are derived from the visit server-side (never guessed). */
import { patch } from "@web/core/utils/patch";
import { PosOrder } from "@point_of_sale/app/models/pos_order";

patch(PosOrder.prototype, {
    setup(vals) {
        super.setup(vals);
        if (!vals?.json_flag && !vals?.id) {
            // new (frontend-created) order only: copy the visit context
            const cfg = this.config;
            const raw = cfg && cfg.distribution_visit_context_raw;
            const visitId =
                raw && typeof raw === "object" ? raw.id : Number(raw) || 0;
            if (visitId) {
                this.distribution_visit_id = visitId;
            }
        }
    },

    serializeForORM(opts = {}) {
        const data = super.serializeForORM(opts);
        const visitId = this.distribution_visit_id;
        if (visitId) {
            // keep the id even if the m2o record is not loaded in POS
            data.distribution_visit_id =
                typeof visitId === "object" ? visitId.id : visitId;
        }
        return data;
    },
});
