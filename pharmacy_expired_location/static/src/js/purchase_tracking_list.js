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
import { ListController } from "@web/views/list/list_controller";
import { listView } from "@web/views/list/list_view";
import { registry } from "@web/core/registry";
import { download } from "@web/core/network/download";

// ─────────────────────────────────────────────────────────────────────────────
// Custom controller
// ─────────────────────────────────────────────────────────────────────────────
export class PurchaseTrackingListController extends ListController {
    /**
     * Toggles all groups recursively. If at least one group is folded, it expands all.
     * Otherwise, it collapses all groups.
     */
    async toggleAllGroups() {
        const rootList = this.model.root;
        if (!rootList || !rootList.isGrouped || !rootList.groups) {
            return;
        }
        const hasFolded = rootList.groups.some((group) => group.isFolded);
        const expand = hasFolded;
        // Store the target state so the UI can reflect it.
        this._allExpanded = expand;

        const toggleGroupRecursive = async (list) => {
            if (!list || !list.isGrouped || !list.groups) {
                return;
            }
            const promises = [];
            for (const group of list.groups) {
                if (expand) {
                    if (group.isFolded) {
                        promises.push(group.toggle().then(() => toggleGroupRecursive(group.list)));
                    } else {
                        promises.push(toggleGroupRecursive(group.list));
                    }
                } else {
                    if (!group.isFolded) {
                        promises.push(group.toggle());
                    }
                    promises.push(toggleGroupRecursive(group.list));
                }
            }
            await Promise.all(promises);
        };
        await toggleGroupRecursive(rootList);
    }

    /**
     * Exports the filtered list records directly to an Excel sheet.
     */
    async exportToExcel() {
        await download({
            data: {
                domain: JSON.stringify(this.model.root.domain),
                groupby: JSON.stringify(this.model.root.groupBy),
            },
            url: `/web/purchase_tracking/export_xlsx`,
        });
    }
}

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

    /**
     * @override
     */
    getCellClass(column, record) {
        let classes = super.getCellClass(column, record);
        if (column.name === "date_planned" && record.data.date_planned) {
            const qtyNotReceived = record.data.qty_not_received !== undefined ? record.data.qty_not_received : 1.0;
            if (qtyNotReceived > 0) {
                const val = record.data.date_planned;
                const datePlanned = typeof val.toJSDate === "function" ? val.toJSDate() : new Date(val);
                if (!isNaN(datePlanned.getTime()) && datePlanned < new Date()) {
                    classes += " o_po_overdue_date";
                }
            }
        }
        return classes;
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
    Controller: PurchaseTrackingListController,
    Renderer: PurchaseTrackingListRenderer,
    buttonTemplate: "pharmacy_expired_location.PurchaseTrackingListButtons",
};

registry
    .category("views")
    .add("purchase_tracking_list", purchaseTrackingListView);
