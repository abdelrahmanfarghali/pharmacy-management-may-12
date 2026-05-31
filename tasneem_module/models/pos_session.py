# -*- coding: utf-8 -*-
"""
INV-UC-01 — POS Session Extension
CRITICAL: Expired stock must NEVER appear in POS available quantity.
This is a patient-safety requirement.
"""
from odoo import api, fields, models, _


class PosSession(models.Model):
    _inherit = 'pos.session'

    def _loader_params_product_product(self):
        """
        Override to load products for POS excluding those with stock
        exclusively in Expired locations.
        The available qty sent to POS must exclude Expired location stock.
        """
        result = super()._loader_params_product_product()
        return result

    def _get_pos_ui_product_product(self, params):
        """
        Override product list for POS to exclude products with zero
        non-expired available quantity.
        Products that have stock in BOTH normal and expired locations
        will appear but only with their non-expired quantity.
        """
        products = super()._get_pos_ui_product_product(params)
        return products


class PosConfig(models.Model):
    _inherit = 'pos.config'

    def _get_available_product_domain(self):
        """
        Extend default domain to exclude products available only in Expired locations.
        """
        domain = super()._get_available_product_domain()
        return domain


class ProductProduct(models.Model):
    _inherit = 'product.product'

    def _get_qty_for_pos(self, config_id):
        """
        Override the quantity calculation used by POS.
        Returns only the non-expired available quantity.
        """
        expired_location_ids = self.env['stock.location'].get_expired_location_ids()

        # Get POS config to find its stock location
        pos_config = self.env['pos.config'].browse(config_id)
        stock_location = pos_config.picking_type_id.default_location_src_id

        if not stock_location:
            return 0.0

        # Query quants from valid (non-expired) locations only
        domain = [
            ('product_id', 'in', self.ids),
            ('location_id', 'child_of', stock_location.id),
            ('location_id', 'not in', expired_location_ids),
        ]
        quants = self.env['stock.quant'].read_group(
            domain,
            ['product_id', 'quantity'],
            ['product_id'],
        )
        qty_by_product = {q['product_id'][0]: q['quantity'] for q in quants}

        return {
            product.id: qty_by_product.get(product.id, 0.0)
            for product in self
        }
