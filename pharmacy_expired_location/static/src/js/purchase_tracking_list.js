/** @odoo-module **/

/**
 * Purchase Order Tracking — Custom List View (Odoo 18)
 *
 * Registers the `purchase_tracking_list` js_class referenced in
 * purchase_order_tracking_views.xml.
 *
 * Two sub-templates are overridden with `t-inherit-mode="primary"`:
 *   1. pharmacy_expired_location.PurchaseTrackingListRenderer
 *      (inherits web.ListRenderer — main wrapper)
 *   2. pharmacy_expired_location.PurchaseTrackingGroupRow
 *      (inherits web.ListRenderer.GroupRow — injects the reception badge)
 *
 * Badge logic (driven by the aggregated qty_not_received from read_group):
 *   qty_not_received === 0  →  "✔ Fully Received"   (green pill)
 *   qty_not_received  >  0  →  "⏳ N Not Received"  (amber pill)
 */

import { ListRenderer } from "@web/views/list/list_renderer";
import { listView } from "@web/views/list/list_view";
import { registry } from "@web/core/registry";

// ─────────────────────────────────────────────────────────────────────────────
// Custom renderer
// ─────────────────────────────────────────────────────────────────────────────

export class PurchaseTrackingListRenderer extends ListRenderer {
    /**
     * Returns the CSS class for the group badge.
     *
     * @param {Object} group  List-view group descriptor from the ORM layer.
     * @returns {string}
     */
    getGroupBadgeClass(group) {
        const remaining = group.aggregates?.qty_not_received ?? 0;
        return remaining <= 0
            ? "badge rounded-pill ms-2 po-tracking-badge text-bg-success"
            : "badge rounded-pill ms-2 po-tracking-badge text-bg-warning";
    }

    /**
     * Returns the human-readable label for the group badge.
     *
     * @param {Object} group  List-view group descriptor.
     * @returns {string}
     */
    getGroupBadgeLabel(group) {
        const remaining = Math.max(0, group.aggregates?.qty_not_received ?? 0);
        return remaining <= 0
            ? `\u00A0\u00A0\u00A0\u2714\u00A0\u00A0\u00A0`
            : `${remaining} Not Received`;
    }

    /**
     * Whether to show the badge at all (only when the group has records).
     *
     * @param {Object} group
     * @returns {boolean}
     */
    showGroupBadge(group) {
        return group.count > 0;
    }
}

// Point the renderer at our primary (standalone) template override.
// The template inherits web.ListRenderer.GroupRow via t-inherit-mode="primary".
PurchaseTrackingListRenderer.groupRowTemplate =
    "pharmacy_expired_location.PurchaseTrackingGroupRow";

// ─────────────────────────────────────────────────────────────────────────────
// View registration
// ─────────────────────────────────────────────────────────────────────────────

export const purchaseTrackingListView = {
    ...listView,
    Renderer: PurchaseTrackingListRenderer,
};

registry
    .category("views")
    .add("purchase_tracking_list", purchaseTrackingListView);
