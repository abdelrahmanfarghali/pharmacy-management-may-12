from odoo import models, fields, api
from odoo.exceptions import ValidationError
import logging

_logger = logging.getLogger(__name__)


# ═══════════════════════════════════════════════════════════════════
# UC-09: Commission % on product.template
# ═══════════════════════════════════════════════════════════════════
class ProductTemplateCommission(models.Model):
    _inherit = 'product.template'

    commission_rate = fields.Float(
        string='Commission (%)',
        default=0.0,
        digits=(5, 2),
        tracking=True,
        help='Commission percentage applied to sales of this product.',
    )


# ═══════════════════════════════════════════════════════════════════
# UC-09: Commission calculation on sale.order.line
# ═══════════════════════════════════════════════════════════════════
class SaleOrderLine(models.Model):
    _inherit = 'sale.order.line'

    commission_rate = fields.Float(
        string='Commission (%)',
        digits=(5, 2),
        compute='_compute_commission',
        store=False,
        readonly=False,
        help='Commission % pulled from product. Can be overridden manually.',
    )

    commission_amount = fields.Float(
        string='Commission Amount',
        digits='Product Price',
        compute='_compute_commission',
        store=False,
        readonly=True,
        help='Commission = Net Price (after discount) × Commission %',
    )

    # ── Compute commission rate + amount ────────────────────────────────────

    @api.depends(
        'product_id',
        'price_unit',
        'product_uom_qty',
        'discount',
        'price_subtotal',
    )
    def _compute_commission(self):
        use_commission = self.env['ir.config_parameter'].sudo().get_param(
            'pharmacy_product.use_commission', default='True'
        )
        for line in self:
            # UC-09: Company-level enable/disable
            if use_commission != 'True':
                line.commission_rate   = 0.0
                line.commission_amount = 0.0
                continue

            rate = line.product_id.product_tmpl_id.commission_rate or 0.0
            line.commission_rate = rate

            # UC-09: Zero commission on free items
            if line.price_unit == 0 or line.product_uom_qty == 0:
                line.commission_amount = 0.0
                continue

            # UC-09: Discount-aware — use net price (price_subtotal already has discount)
            net_total = line.price_subtotal  # = qty × unit_price × (1 - discount/100)
            line.commission_amount = net_total * (rate / 100.0)

    # ── Constraint: commission rate 0–100 ───────────────────────────────────

    @api.constrains('commission_rate')
    def _check_commission_rate(self):
        for line in self:
            if not (0.0 <= line.commission_rate <= 100.0):
                raise ValidationError(
                    "Commission rate must be between 0% and 100%."
                )


# ═══════════════════════════════════════════════════════════════════
# UC-09: Reverse commission on returns (account.move.line)
# ═══════════════════════════════════════════════════════════════════
class AccountMoveLine(models.Model):
    _inherit = 'account.move.line'

    commission_amount = fields.Float(
        string='Commission Amount',
        digits='Product Price',
        compute='_compute_commission_reversal',
        store=False,
    )

    @api.depends('move_id.move_type', 'price_subtotal', 'product_id')
    def _compute_commission_reversal(self):
        use_commission = self.env['ir.config_parameter'].sudo().get_param(
            'pharmacy_product.use_commission', default='True'
        )
        for line in self:
            if use_commission != 'True':
                line.commission_amount = 0.0
                continue

            rate = line.product_id.product_tmpl_id.commission_rate or 0.0

            # UC-09: Reverse commission on credit notes (returns)
            if line.move_id.move_type == 'out_refund':
                line.commission_amount = -(abs(line.price_subtotal) * rate / 100.0)
            elif line.move_id.move_type == 'out_invoice':
                line.commission_amount = line.price_subtotal * rate / 100.0
            else:
                line.commission_amount = 0.0


# ═══════════════════════════════════════════════════════════════════
# UC-09: Commission Report model
# ═══════════════════════════════════════════════════════════════════
class PharmacyCommissionReport(models.Model):
    _name        = 'pharmacy.commission.report'
    _description = 'Pharmacy Commission Report'
    _auto        = False  # SQL view — no physical table
    _rec_name    = 'product_name'
    _order       = 'order_date desc'

    order_id       = fields.Many2one('sale.order',     string='Sales Order',  readonly=True)
    order_date     = fields.Datetime(                  string='Order Date',   readonly=True)
    partner_id     = fields.Many2one('res.partner',    string='Customer',     readonly=True)
    product_id     = fields.Many2one('product.product',string='Product',      readonly=True)
    product_name   = fields.Char(                      string='Product Name', readonly=True)
    commission_rate   = fields.Float(string='Commission %',      readonly=True, digits=(5,2))
    price_subtotal    = fields.Float(string='Net Amount',        readonly=True, digits='Product Price')
    commission_amount = fields.Float(string='Commission Amount', readonly=True, digits='Product Price')
    state          = fields.Selection([
        ('draft',  'Draft'),
        ('sale',   'Sales Order'),
        ('done',   'Done'),
        ('cancel', 'Cancelled'),
    ], string='Order Status', readonly=True)

    def init(self):
        self.env.cr.execute("""
            DROP VIEW IF EXISTS pharmacy_commission_report;
            CREATE OR REPLACE VIEW pharmacy_commission_report AS (
                SELECT
                    sol.id                                              AS id,
                    so.id                                               AS order_id,
                    so.date_order                                       AS order_date,
                    so.partner_id                                       AS partner_id,
                    sol.product_id                                      AS product_id,
                    COALESCE(pt.name->>'en_US', pt.name::text)          AS product_name,
                    pt.commission_rate                                  AS commission_rate,
                    sol.price_subtotal                                  AS price_subtotal,
                    sol.price_subtotal * pt.commission_rate / 100.0    AS commission_amount,
                    so.state                                            AS state
                FROM sale_order_line sol
                JOIN sale_order      so  ON so.id  = sol.order_id
                JOIN product_product pp  ON pp.id  = sol.product_id
                JOIN product_template pt ON pt.id  = pp.product_tmpl_id
                WHERE pt.commission_rate > 0
                  AND so.state IN ('sale', 'done')
            )
        """)
