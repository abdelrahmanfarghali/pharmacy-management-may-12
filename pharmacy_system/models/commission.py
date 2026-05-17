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
        compute='_compute_commission_rate',
        store=True,
        readonly=False,
        help='Commission % pulled from product. Can be overridden manually.',
    )

    commission_amount = fields.Float(
        string='Commission Amount',
        digits='Product Price',
        compute='_compute_commission_amount',
        store=True,
        readonly=True,
        help='Commission = Net Price (after discount) × Commission %',
    )

    # ── Compute commission rate + amount ────────────────────────────────────

    @api.depends('product_id')
    def _compute_commission_rate(self):
        use_commission = self.env['ir.config_parameter'].sudo().get_param(
            'pharmacy_system.use_commission', default='True'
        )
        for line in self:
            if use_commission != 'True':
                line.commission_rate = 0.0
            elif line.product_id:
                line.commission_rate = line.product_id.product_tmpl_id.commission_rate or 0.0
            else:
                line.commission_rate = 0.0

    @api.depends('price_subtotal', 'commission_rate')
    def _compute_commission_amount(self):
        use_commission = self.env['ir.config_parameter'].sudo().get_param(
            'pharmacy_system.use_commission', default='True'
        )
        for line in self:
            if use_commission != 'True' or line.price_unit == 0 or line.product_uom_qty == 0:
                line.commission_amount = 0.0
            else:
                # Commission = Net Price (after discount) × Commission %
                line.commission_amount = line.price_subtotal * (line.commission_rate / 100.0)

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
            'pharmacy_system.use_commission', default='True'
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
    _name        = 'pharmacy.commission.ledger'
    _description = 'Pharmacy Commission Report'
    _rec_name    = 'product_name'
    _order       = 'order_date desc'

    sale_line_id   = fields.Many2one('sale.order.line', string='Sale Line', readonly=True, ondelete='cascade')
    pos_line_id    = fields.Many2one('pos.order.line', string='PoS Line', readonly=True, ondelete='cascade')

    order_id       = fields.Many2one('sale.order',     string='Sales Order',  readonly=True)
    pos_order_id   = fields.Many2one('pos.order',      string='PoS Order',    readonly=True)
    order_ref      = fields.Char(                      string='Order Ref',    readonly=True)
    order_date     = fields.Datetime(                  string='Order Date',   readonly=True)
    partner_id     = fields.Many2one('res.partner',    string='Customer',     readonly=True)
    product_id     = fields.Many2one('product.product',string='Product',      readonly=True)
    product_name   = fields.Char(                      string='Product Name', readonly=True)
    commission_rate   = fields.Float(string='Commission %',      readonly=True, digits=(5,2))
    price_subtotal    = fields.Float(string='Net Amount',        readonly=True, digits='Product Price')
    commission_amount = fields.Float(string='Commission Amount', readonly=True, digits='Product Price')
    
    source_type    = fields.Selection([
        ('sale', 'Sales Order'),
        ('pos', 'PoS Order')
    ], string='Source', readonly=True)
    
    is_processed   = fields.Boolean(string='Processed/Flagged', default=False,
                                  help='Flag for future features to mark this commission as paid/processed.')

    state          = fields.Selection([
        ('draft',  'Draft'),
        ('sale',   'Sales Order'),
        ('done',   'Done'),
        ('cancel', 'Cancelled'),
        ('paid',   'Paid'),
        ('invoiced', 'Invoiced')
    ], string='Order Status', readonly=True)

    _sql_constraints = [
        ('unique_sale_line', 'UNIQUE(sale_line_id)', 'Commission record for this Sale Line already exists!'),
        ('unique_pos_line', 'UNIQUE(pos_line_id)', 'Commission record for this PoS Line already exists!'),
    ]

    def action_sync_historical_commissions(self):
        """ Fetch and create commission records for previously sold orders/pos orders. """
        # Sync Sales Orders
        sale_lines = self.env['sale.order.line'].search([
            ('order_id.state', 'in', ('sale', 'done')),
            '|', ('commission_amount', '>', 0), ('product_id.product_tmpl_id.commission_rate', '>', 0)
        ])
        for line in sale_lines:
            rate = line.commission_rate or line.product_id.product_tmpl_id.commission_rate
            amt = line.commission_amount or (line.price_subtotal * rate / 100.0)
            if amt > 0 and not self.search_count([('sale_line_id', '=', line.id)]):
                self.create({
                    'sale_line_id': line.id,
                    'order_id': line.order_id.id,
                    'order_ref': line.order_id.name,
                    'order_date': line.order_id.date_order,
                    'partner_id': line.order_id.partner_id.id,
                    'product_id': line.product_id.id,
                    'product_name': line.product_id.product_tmpl_id.name,
                    'commission_rate': rate,
                    'price_subtotal': line.price_subtotal,
                    'commission_amount': amt,
                    'source_type': 'sale',
                    'state': line.order_id.state,
                })

        # Sync PoS Orders
        pos_lines = self.env['pos.order.line'].search([
            ('order_id.state', 'in', ('paid', 'done', 'invoiced')),
            ('product_id.product_tmpl_id.commission_rate', '>', 0)
        ])
        for line in pos_lines:
            if not self.search_count([('pos_line_id', '=', line.id)]):
                rate = line.product_id.product_tmpl_id.commission_rate
                amt = line.price_subtotal * (rate / 100.0)
                if amt > 0:
                    self.create({
                        'pos_line_id': line.id,
                        'pos_order_id': line.order_id.id,
                        'order_ref': line.order_id.name,
                        'order_date': line.order_id.date_order,
                        'partner_id': line.order_id.partner_id.id,
                        'product_id': line.product_id.id,
                        'product_name': line.product_id.product_tmpl_id.name,
                        'commission_rate': rate,
                        'price_subtotal': line.price_subtotal,
                        'commission_amount': amt,
                        'source_type': 'pos',
                        'state': line.order_id.state,
                    })

# ═══════════════════════════════════════════════════════════════════
# UC-09: Order Workflow Hooks (Auto-Generate Commissions)
# ═══════════════════════════════════════════════════════════════════
class SaleOrder(models.Model):
    _inherit = 'sale.order'

    def _action_confirm(self):
        res = super()._action_confirm()
        for order in self:
            for line in order.order_line:
                if line.commission_amount > 0 and not self.env['pharmacy.commission.ledger'].search_count([('sale_line_id', '=', line.id)]):
                    self.env['pharmacy.commission.ledger'].create({
                        'sale_line_id': line.id,
                        'order_id': order.id,
                        'order_ref': order.name,
                        'order_date': order.date_order,
                        'partner_id': order.partner_id.id,
                        'product_id': line.product_id.id,
                        'product_name': line.product_id.product_tmpl_id.name,
                        'commission_rate': line.commission_rate,
                        'price_subtotal': line.price_subtotal,
                        'commission_amount': line.commission_amount,
                        'source_type': 'sale',
                        'state': order.state,
                    })
        return res

    def _action_cancel(self):
        res = super()._action_cancel()
        for order in self:
            self.env['pharmacy.commission.ledger'].search([('order_id', '=', order.id)]).unlink()
        return res

class PosOrder(models.Model):
    _inherit = 'pos.order'

    @api.model_create_multi
    def create(self, vals_list):
        orders = super().create(vals_list)
        orders._generate_commission_records()
        return orders

    def write(self, vals):
        res = super().write(vals)
        if 'state' in vals and vals['state'] in ('paid', 'done', 'invoiced'):
            self._generate_commission_records()
        elif 'state' in vals and vals['state'] == 'cancel':
            self.env['pharmacy.commission.ledger'].search([('pos_order_id', 'in', self.ids)]).unlink()
        return res

    def _generate_commission_records(self):
        for order in self:
            if order.state in ('paid', 'done', 'invoiced'):
                for line in order.lines:
                    rate = line.product_id.product_tmpl_id.commission_rate
                    if rate > 0:
                        amt = line.price_subtotal * (rate / 100.0)
                        if amt > 0 and not self.env['pharmacy.commission.ledger'].search_count([('pos_line_id', '=', line.id)]):
                            self.env['pharmacy.commission.ledger'].create({
                                'pos_line_id': line.id,
                                'pos_order_id': order.id,
                                'order_ref': order.name,
                                'order_date': order.date_order,
                                'partner_id': order.partner_id.id,
                                'product_id': line.product_id.id,
                                'product_name': line.product_id.product_tmpl_id.name,
                                'commission_rate': rate,
                                'price_subtotal': line.price_subtotal,
                                'commission_amount': amt,
                                'source_type': 'pos',
                                'state': order.state,
                            })
