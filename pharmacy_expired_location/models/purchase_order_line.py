from odoo import models, fields, api


class PurchaseOrderLine(models.Model):
    """
    Extends purchase.order.line with five placeholder tracking columns and
    a stored computed field for the not-yet-received quantity.

    Placeholder fields (columns 2–6):
        tracking_ref, tracking_origin, tracking_carrier, tracking_eta,
        tracking_status — replace / rename as business requirements evolve.

    Computed field (column 7):
        qty_not_received  = max(0, product_qty − qty_received)
        Stored so that read_group can aggregate it for the group-header badges.
    """

    _inherit = 'purchase.order.line'

    # ── Placeholder Tracking Columns (2–6) ───────────────────────────────────

    tracking_ref = fields.Char(
        string='Tracking Ref.',
        index=True,
        copy=False,
        help='Internal tracking or shipment reference for this line.',
    )
    tracking_origin = fields.Char(
        string='Origin',
        help='Source document, requisition, or project reference.',
    )
    tracking_carrier = fields.Char(
        string='Carrier',
        help='Logistics / freight carrier responsible for this shipment.',
    )
    tracking_eta = fields.Date(
        string='ETA',
        help='Estimated Time of Arrival at the receiving warehouse.',
    )
    tracking_status = fields.Selection(
        selection=[
            ('pending',    'Pending'),
            ('in_transit', 'In Transit'),
            ('partial',    'Partial'),
            ('received',   'Received'),
        ],
        string='Track Status',
        default='pending',
        index=True,
        help='Current logistic / reception tracking status for this line.',
    )

    # ── Column 7: Computed Not-Received Quantity ─────────────────────────────

    qty_not_received = fields.Float(
        string='Qty. Not Received',
        compute='_compute_qty_not_received',
        digits='Product Unit of Measure',
        store=True,   # stored → read_group aggregation works for group-header badges
        help='Remaining undelivered quantity: ordered − already received (≥ 0).',
    )

    @api.depends('product_qty', 'qty_received')
    def _compute_qty_not_received(self):
        for line in self:
            line.qty_not_received = max(0.0, line.product_qty - line.qty_received)
