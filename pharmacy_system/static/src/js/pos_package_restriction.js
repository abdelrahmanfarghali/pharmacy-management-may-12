/** @odoo-module **/

import { patch } from "@web/core/utils/patch";
import { PosStore } from "@point_of_sale/app/store/pos_store";
import { PosOrderline } from "@point_of_sale/app/models/pos_order_line";
import { AlertDialog } from "@web/core/confirmation_dialog/confirmation_dialog";

// 1. Prevent fractional package quantities and enforce max_qty_per_invoice limits
patch(PosOrderline.prototype, {
    set_quantity(quantity, keep_price) {
        if (this.product_id) {
            const qty = quantity === 'remove' ? 0 : (parseFloat(quantity) || 0);
            
            if (qty > 0) {
                // Check 1: Package fractions
                if (this.product_id.pharmacy_product_type === 'package') {
                    const unitsSize = this.product_id.units_per_package || 1;
                    if (unitsSize > 1) {
                        // We must ensure the cashier doesn't enter a fraction of a package (e.g. 1.5).
                        if (Math.abs(qty - Math.round(qty)) >= 1e-4) {
                            const env = this.env || (this.pos && this.pos.env);
                            if (env && env.services.dialog) {
                                env.services.dialog.add(AlertDialog, {
                                    title: "Invalid Quantity",
                                    body: `Product '${this.product_id.display_name}' is sold as a Package. You cannot sell a fraction of a package. Please enter a whole number (e.g. 1, 2, 3).`,
                                });
                            }
                            return false; 
                        }
                    }
                }

                // Check 2: Max Qty Per Invoice
                if (this.product_id.is_medicine) {
                    const limit = this.product_id.max_qty_per_invoice || 0;
                    if (limit > 0) {
                        const order = this.pos && this.pos.get_order();
                        if (order && order.lines) {
                            let totalQty = qty;
                            for (const line of order.lines) {
                                // Accumulate quantities of OTHER lines with the same product
                                if (line.product_id.id === this.product_id.id && line.uuid !== this.uuid) {
                                    totalQty += line.get_quantity();
                                }
                            }

                            if (totalQty > limit) {
                                const env = this.env || (this.pos && this.pos.env);
                                if (env && env.services.dialog) {
                                    env.services.dialog.add(AlertDialog, {
                                        title: "Limit Exceeded",
                                        body: `Cannot sell more than ${limit} of '${this.product_id.display_name}' in a single transaction. (Requested: ${totalQty})`,
                                    });
                                }
                                return false;
                            }
                        }
                    }
                }
            }
        }
        return super.set_quantity(...arguments);
    }
});
