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

    Related fields (for search-view group-bys):
        partner_id  — relay from order_id.partner_id  (Group By Vendor)
        date_order  — relay from order_id.date_order   (Group By Date)
    """

    _inherit = 'purchase.order.line'

    # ── Related fields for Search-View Group Bys ─────────────────────────────
    #
    # purchase.order.line does NOT expose partner_id or date_order directly.
    # Declaring them as `related` lets the ORM filter / group on them without
    # adding extra DB columns (store=False).

    partner_id = fields.Many2one(
        related='order_id.partner_id',
        string='Vendor',
        store=False,
        readonly=True,
        help='Vendor of the parent purchase order — used for the "By Vendor" group-by.',
    )
    date_order = fields.Datetime(
        related='order_id.date_order',
        string='Order Date',
        store=False,
        readonly=True,
        help='Confirmation date of the parent PO — used for the "By Date" group-by.',
    )

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

    list_name = fields.Char(
        string="Product", 
        compute="_compute_list_name"
    )

    @api.depends('product_id.default_code', 'product_id.name')
    def _compute_list_name(self):
        for line in self:
            if line.product_id.default_code:
                line.list_name = f"[{line.product_id.default_code}] {line.product_id.name}"
            else:
                line.list_name = line.product_id.name or ""

    @api.depends('product_qty', 'qty_received')
    def _compute_qty_not_received(self):
        for line in self:
            line.qty_not_received = max(0.0, line.product_qty - line.qty_received)
