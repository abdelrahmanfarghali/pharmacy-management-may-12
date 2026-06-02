from odoo import models, api

class ProductProduct(models.Model):
    _inherit = 'product.product'

    @api.depends('default_code', 'name')
    def _compute_display_name(self):
        for product in self:
            if product.default_code:
                product.display_name = f"{product.default_code} {product.name}"
            else:
                product.display_name = product.name
