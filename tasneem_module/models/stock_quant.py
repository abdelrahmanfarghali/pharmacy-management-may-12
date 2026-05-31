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

    # ─────────────────────────────────────────────
    # Custom Reporting Method for Expired Medicine
    # ─────────────────────────────────────────────
    @api.model
    def get_expired_report_data(self, month=None, year=None, location_ids=None):
        """Fetch and aggregate data for the Expired Medicines Report."""
        domain = [('location_id.is_expired_location', '=', True)]
        if location_ids:
            domain.append(('location_id', 'in', location_ids))

        # Include expiration_date filtering if month/year are provided
        if month and year:
            from datetime import datetime
            start_date = datetime(int(year), int(month), 1)
            if int(month) == 12:
                end_date = datetime(int(year) + 1, 1, 1)
            else:
                end_date = datetime(int(year), int(month) + 1, 1)
            domain.append(('lot_id.expiration_date', '>=', start_date))
            domain.append(('lot_id.expiration_date', '<', end_date))

        quants = self.search(domain)

        # Aggregate data by product and lot
        grouped = {}
        for quant in quants:
            key = (quant.product_id.id, quant.lot_id.id)
            if key not in grouped:
                grouped[key] = {
                    'medicine_name': f"{quant.product_id.display_name} [{quant.lot_id.name}]" if quant.lot_id else quant.product_id.display_name,
                    'expiry_date': quant.lot_id.expiration_date.strftime('%Y-%m-%d') if quant.lot_id and quant.lot_id.expiration_date else '',
                    'price': quant.product_id.standard_price,
                    'quantity': 0.0,
                }
            grouped[key]['quantity'] += quant.quantity

        result = []
        for key, val in grouped.items():
            val['total_price'] = val['price'] * val['quantity']
            result.append(val)

        return result


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
