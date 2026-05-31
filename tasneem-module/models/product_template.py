# -*- coding: utf-8 -*-
"""
INV-UC-01 — Product Template / Product Product Extension
Action method for the "Expired Stock" stat button on product form.
"""
from odoo import api, fields, models, _


class ProductTemplate(models.Model):
    _inherit = 'product.template'

    qty_expired = fields.Float(
        string='Expired Stock Qty',
        compute='_compute_qty_expired_template',
        digits='Product Unit of Measure',
        help='Total on-hand quantity in Expired-type locations across all variants.',
    )

    @api.depends('product_variant_ids', 'product_variant_ids.qty_expired')
    def _compute_qty_expired_template(self):
        for tmpl in self:
            tmpl.qty_expired = sum(tmpl.product_variant_ids.mapped('qty_expired'))

    def action_open_expired_quants(self):
        self.ensure_one()
        expired_location_ids = self.env['stock.location'].get_expired_location_ids()
        return {
            'type': 'ir.actions.act_window',
            'name': _('Expired Stock — %s') % self.name,
            'res_model': 'stock.quant',
            'view_mode': 'tree,form',
            'domain': [
                ('product_id.product_tmpl_id', '=', self.id),
                ('location_id', 'in', expired_location_ids),
            ],
            'context': {
                'search_default_expired_stock': 1,
            },
        }
