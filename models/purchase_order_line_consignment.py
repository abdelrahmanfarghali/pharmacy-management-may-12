# -*- coding: utf-8 -*-
from odoo import models, fields, api, _


class PurchaseOrderLineConsignmentPayment(models.Model):
    """
    Tracks cumulative paid quantities per consignment PO line.
    One record per purchase.order.line (created on demand).
    """
    _name = 'purchase.order.line.consignment.payment'
    _description = 'Consignment PO Line Payment Tracking'
    _rec_name = 'purchase_order_line_id'

    purchase_order_line_id = fields.Many2one(
        'purchase.order.line',
        string='PO Line',
        required=True,
        ondelete='cascade',
        index=True,
    )
    purchase_order_id = fields.Many2one(
        'purchase.order',
        string='Purchase Order',
        related='purchase_order_line_id.order_id',
        store=True,
        index=True,
    )
    product_id = fields.Many2one(
        'product.product',
        string='Product',
        related='purchase_order_line_id.product_id',
        store=True,
    )
    already_paid_qty = fields.Float(
        string='Already Paid Quantity',
        digits='Product Unit of Measure',
        default=0.0,
        help='Total units already invoiced and paid through previous Payment actions on this PO.',
    )
    currency_id = fields.Many2one(
        related='purchase_order_line_id.currency_id',
        store=True,
    )

    def _add_paid_qty(self, qty):
        """Increment the already_paid_qty by qty."""
        self.ensure_one()
        self.already_paid_qty += qty

    # @api.model
    # def get_or_create_for_line(self, po_line):
    #     """Return or create the consignment payment record for a given PO line."""
    #     record = self.search([('purchase_order_line_id', '=', po_line.id)], limit=1)
    #     if not record:
    #         record = self.create({'purchase_order_line_id': po_line.id})
    #     return record

     # ── إضافة جديدة ──────────────────────────────────────────────────────
    vendor_id = fields.Many2one(
        'res.partner',
        string='Vendor',
        index=True,
        help='الـ vendor المرتبط بهذا الـ PO line (من supplierinfo أو PO partner)',
    )

    @api.model
    def get_or_create_for_line(self, po_line):
        """Return or create the consignment payment record for a given PO line."""
        record = self.search([('purchase_order_line_id', '=', po_line.id)], limit=1)
        if not record:
            vendor = po_line._get_line_vendor()
            record = self.create({
                'purchase_order_line_id': po_line.id,
                'vendor_id': vendor.id if vendor else False,
            })
        return record