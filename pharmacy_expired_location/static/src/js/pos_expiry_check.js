/** @odoo-module **/

import { Order } from "@point_of_sale/app/store/models";
import { patch } from "@web/core/utils/patch";

patch(Order.prototype, {

    async addProduct(product, options = {}) {

        const expired = product.has_expired_lot;

        if (expired) {
            await this.env.services.dialog.add(
                this.env.services.dialog,
                {
                    title: "Expired Product",
                    body: "This medicine is expired and cannot be sold."
                }
            );
            return;
        }

        return super.addProduct(product, options);
    }

});