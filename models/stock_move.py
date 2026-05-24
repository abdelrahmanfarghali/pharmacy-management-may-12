# -*- coding: utf-8 -*-
"""
INV-UC-01 — Stock Move Extension
Blocks adding expired locations as destination in sale orders.
"""
from odoo import api, fields, models, _
from odoo.exceptions import UserError


class StockMove(models.Model):
    _inherit = 'stock.move'

    @api.constrains('location_dest_id')
    def _check_sale_dest_not_expired(self):
        """
        Block any sale-order-linked move that targets an Expired location.
        Expired locations must never appear as source/destination in sales flows.
        """
        for move in self:
            if (
                move.location_dest_id.is_expired_location
                and move.sale_line_id
            ):
                raise UserError(
                    _(
                        'Cannot deliver to an Expired location via a sale order.\n'
                        'Expired locations are quarantine zones — use an internal transfer instead.'
                    )
                )
