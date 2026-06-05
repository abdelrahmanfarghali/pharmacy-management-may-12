from odoo import models, fields, api
from odoo.exceptions import UserError
import logging

_logger = logging.getLogger(__name__)


class PharmacyWishlist(models.Model):
    """
    SC5-UC-01: Wishlist — Out-of-Stock Customer Request Management
    قائمة الأمنيات: تسجيل طلبات العملاء للمنتجات غير المتوفرة
    """
    _name        = 'pharmacy.wishlist'
    _description = 'Pharmacy Wishlist — Customer Out-of-Stock Requests'
    _inherit     = ['mail.thread', 'mail.activity.mixin']
    _order       = 'create_date desc'
    _rec_name    = 'product_id'

    # ── Core fields ──────────────────────────────────────────────────────────
    partner_id = fields.Many2one(
        'res.partner',
        string='Customer',
        required=True,
        tracking=True,
        index=True,
    )

    product_id = fields.Many2one(
        'product.product',
        string='Product Requested',
        required=True,
        tracking=True,
        index=True,
    )

    qty_requested = fields.Float(
        string='Qty Requested',
        default=1.0,
        required=True,
        tracking=True,
    )

    uom_id = fields.Many2one(
        'uom.uom',
        string='Unit of Measure',
        related='product_id.uom_id',
        readonly=True,
    )

    note = fields.Text(
        string='Customer Notes',
        help='Any special instructions from the customer.',
    )

    # ── Status ───────────────────────────────────────────────────────────────
    state = fields.Selection(
        selection=[
            ('pending',    'Pending'),
            ('available',  'Available — Notify Customer'),
            ('notified',   'Customer Notified'),
            ('converted',  'Converted to Sale'),
            ('cancelled',  'Cancelled'),
        ],
        string='Status',
        default='pending',
        tracking=True,
        index=True,
    )

    # ── Stock info ───────────────────────────────────────────────────────────
    qty_on_hand = fields.Float(
        string='Current Stock',
        compute='_compute_qty_on_hand',
        store=False,
    )

    is_available = fields.Boolean(
        string='In Stock Now',
        compute='_compute_qty_on_hand',
        store=False,
    )

    @api.depends('product_id', 'qty_requested')
    def _compute_qty_on_hand(self):
        for rec in self:
            if rec.product_id:
                rec.qty_on_hand  = rec.product_id.qty_available
                rec.is_available = rec.product_id.qty_available >= rec.qty_requested
            else:
                rec.qty_on_hand  = 0.0
                rec.is_available = False

    # ── Linked Sale Order ────────────────────────────────────────────────────
    sale_order_id = fields.Many2one(
        'sale.order',
        string='Sale Order',
        readonly=True,
        tracking=True,
    )

    # ── Dates ────────────────────────────────────────────────────────────────
    request_date  = fields.Date(string='Request Date',  default=fields.Date.today)
    notified_date = fields.Date(string='Notified Date', readonly=True)
    fulfilled_date= fields.Date(string='Fulfilled Date',readonly=True)

    # ── Actions ──────────────────────────────────────────────────────────────

    def action_notify_customer(self):
        """SC5-UC-01: Send notification to customer that product is available."""
        for rec in self:
            if rec.state not in ('pending', 'available'):
                continue
            # Send email/chatter message
            rec.message_post(
                body=f"""
                    <p>Dear <strong>{rec.partner_id.name}</strong>,</p>
                    <p>Great news! The product you requested is now available:</p>
                    <ul>
                        <li><strong>{rec.product_id.display_name}</strong>
                            — {rec.qty_on_hand} {rec.uom_id.name} in stock</li>
                    </ul>
                    <p>Please visit us or contact us to place your order.</p>
                """,
                message_type='email',
                partner_ids=[rec.partner_id.id],
                subject=f"Product Available: {rec.product_id.display_name}",
            )
            rec.write({
                'state':         'notified',
                'notified_date': fields.Date.today(),
            })
        return True

    def action_convert_to_sale(self):
        """SC5-UC-01: Create a Sale Order from this wishlist entry."""
        self.ensure_one()
        if self.state == 'converted':
            raise UserError('Already converted to a Sale Order.')

        sale_order = self.env['sale.order'].create({
            'partner_id': self.partner_id.id,
            'origin':     f'Wishlist Request — {self.product_id.display_name}',
            'order_line': [(0, 0, {
                'product_id':    self.product_id.id,
                'product_uom_qty': self.qty_requested,
                'product_uom':   self.uom_id.id,
                'price_unit':    self.product_id.lst_price,
            })],
        })

        self.write({
            'state':          'converted',
            'sale_order_id':  sale_order.id,
            'fulfilled_date': fields.Date.today(),
        })

        _logger.info(
            'pharmacy_wishlist: Converted wishlist %d → SO %s',
            self.id, sale_order.name
        )

        return {
            'type': 'ir.actions.act_window',
            'name': 'Sale Order',
            'res_model': 'sale.order',
            'res_id': sale_order.id,
            'view_mode': 'form',
            'target': 'current',
        }

    def action_cancel(self):
        for rec in self:
            rec.state = 'cancelled'

    def action_reset_pending(self):
        for rec in self:
            rec.state = 'pending'

    # ── Cron: auto-detect when product becomes available ────────────────────
    @api.model
    def action_check_stock_and_notify(self):
        """
        SC5-UC-01: Cron — daily check.
        If a pending wishlist item's product is now in stock,
        auto-update state to 'available' for staff review.
        """
        pending = self.search([('state', '=', 'pending')])
        newly_available = pending.filtered(
            lambda r: r.product_id.qty_available >= r.qty_requested
        )
        if newly_available:
            newly_available.write({'state': 'available'})
            _logger.info(
                'pharmacy_wishlist: %d wishlist items now available.',
                len(newly_available)
            )
