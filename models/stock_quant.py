# -*- coding: utf-8 -*-
"""
INV-UC-01 — Stock Quant Extension
- Expired stock visible in reports but excluded from Available/Forecasted qty
- Adds "Expired Stock" filter in stock quant report
"""
from odoo import api, fields, models, _


class StockQuant(models.Model):
    _inherit = 'stock.quant'

    is_expired_stock = fields.Boolean(
        string='Is Expired Stock',
        compute='_compute_is_expired_stock',
        store=True,
        help='True when this quant sits in an Expired-type location.',
    )

    @api.depends('location_id', 'location_id.is_expired_location')
    def _compute_is_expired_stock(self):
        for quant in self:
            quant.is_expired_stock = quant.location_id.is_expired_location

    # ─────────────────────────────────────────────
    # Override available qty to exclude expired stock
    # ─────────────────────────────────────────────
    @api.model
    def _get_available_quantity(
        self,
        product_id,
        location_id,
        lot_id=None,
        package_id=None,
        owner_id=None,
        strict=False,
        allow_negative=False,
    ):
        """Exclude Expired locations from available quantity calculation."""
        # If the requested location itself is Expired — return 0 as available
        if location_id.is_expired_location:
            return 0.0
        return super()._get_available_quantity(
            product_id,
            location_id,
            lot_id=lot_id,
            package_id=package_id,
            owner_id=owner_id,
            strict=strict,
            allow_negative=allow_negative,
        )


class ProductProduct(models.Model):
    _inherit = 'product.product'

    qty_available_not_expired = fields.Float(
        string='Available Qty (excl. Expired)',
        compute='_compute_qty_available_not_expired',
        digits='Product Unit of Measure',
        help='On-hand quantity excluding stock in Expired-type locations.',
    )

    qty_expired = fields.Float(
        string='Expired Stock Qty',
        compute='_compute_qty_expired',
        digits='Product Unit of Measure',
        help='On-hand quantity sitting exclusively in Expired-type locations.',
    )

    @api.depends('stock_quant_ids', 'stock_quant_ids.quantity', 'stock_quant_ids.location_id')
    def _compute_qty_available_not_expired(self):
        expired_location_ids = self.env['stock.location'].get_expired_location_ids()
        for product in self:
            quants = self.env['stock.quant'].search([
                ('product_id', '=', product.id),
                ('location_id', 'not in', expired_location_ids),
                ('location_id.usage', '=', 'internal'),
            ])
            product.qty_available_not_expired = sum(quants.mapped('quantity'))

    @api.depends('stock_quant_ids', 'stock_quant_ids.quantity', 'stock_quant_ids.location_id')
    def _compute_qty_expired(self):
        expired_location_ids = self.env['stock.location'].get_expired_location_ids()
        for product in self:
            quants = self.env['stock.quant'].search([
                ('product_id', '=', product.id),
                ('location_id', 'in', expired_location_ids),
            ])
            product.qty_expired = sum(quants.mapped('quantity'))

    def action_open_expired_quants(self):
        """Action for stat button on product form — opens expired quants."""
        self.ensure_one()
        expired_location_ids = self.env['stock.location'].get_expired_location_ids()
        return {
            'type': 'ir.actions.act_window',
            'name': _('Expired Stock — %s') % self.display_name,
            'res_model': 'stock.quant',
            'view_mode': 'tree,form',
            'domain': [
                ('product_id', '=', self.id),
                ('location_id', 'in', expired_location_ids),
            ],
        }
