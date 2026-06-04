from odoo import models, fields, api
from datetime import date


class ProductProduct(models.Model):
    _inherit = "product.product"

    has_expired_lot = fields.Boolean(
        compute="_compute_has_expired_lot"
    )

    @api.depends()
    def _compute_has_expired_lot(self):
        today = date.today()

        for product in self:

            lot = self.env['stock.lot'].search([
                ('product_id', '=', product.id),
                ('expiration_date', '<=', today)
            ], limit=1)

            product.has_expired_lot = bool(lot)