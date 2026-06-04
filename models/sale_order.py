from odoo import fields,models
class SaleOrderLineConsignment(models.Model):
    _inherit = 'sale.order.line'

    consignment_po_line_id = fields.Many2one(
        'purchase.order.line',
        string='Consignment PO Line',
        copy=False,
        index=True,
        help='ربط يدوي بـ PO line الخاص بهذا المنتج في الـ Consignment',
    )