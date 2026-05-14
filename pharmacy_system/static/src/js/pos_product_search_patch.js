/** @odoo-module **/

/**
 * Patch the POS ProductsWidget search predicate so that the live
 * keystroke filter matches against `generic_name` in addition to the
 * standard product name, barcode, and reference fields.
 *
 * Odoo 18 POS uses `ProductModel.searchString` (a getter that returns a
 * pre-built lowercase string) as the haystack for the search predicate.
 * We override that getter to append the generic_name value so no changes
 * to the filter function itself are required.
 *
 * Coverage:
 *  - POS product browser / search bar
 *  - POS order line product picker (via the same underlying model)
 */

import { patch } from "@web/core/utils/patch";
import { Product } from "@point_of_sale/app/store/models";

patch(Product.prototype, {
    /**
     * Extends the base searchString getter.
     * Base returns: `${name}|${internalRef}|${barcode}` (all lowercase).
     * We append `|${generic_name}` when present.
     */
    get searchString() {
        const base = super.searchString;
        const generic = (this.generic_name || "").trim().toLowerCase();
        return generic ? `${base}|${generic}` : base;
    },
});
