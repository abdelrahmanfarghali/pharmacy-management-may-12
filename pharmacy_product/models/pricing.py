from odoo import models, fields, api
from odoo.exceptions import ValidationError, UserError
import logging

_logger = logging.getLogger(__name__)


# ═══════════════════════════════════════════════════════════════════
# UC-07: Public Price (Selling Price) + Price History + Validations
# UC-08: Avg Purchase Cost (AVCO) — visibility + hide if no purchase
# ═══════════════════════════════════════════════════════════════════
class ProductTemplatePricing(models.Model):
    _inherit = 'product.template'

    # ── UC-07: Price > 0 validation ─────────────────────────────────────────
    @api.constrains('list_price')
    def _check_list_price_positive(self):
        for rec in self:
            if rec.list_price < 0:
                raise ValidationError(
                    f"Public Price for '{rec.name}' cannot be negative."
                )

    # ── UC-07: Warning if selling price < cost (below cost) ─────────────────
    @api.onchange('list_price')
    def _onchange_list_price_below_cost(self):
        for rec in self:
            if (
                rec.list_price
                and rec.standard_price
                and rec.list_price < rec.standard_price
            ):
                return {
                    'warning': {
                        'title': 'Price Below Cost!',
                        'message': (
                            f"The selling price ({rec.list_price:.2f}) is lower than "
                            f"the cost price ({rec.standard_price:.2f}). "
                            "You will be selling at a loss."
                        ),
                    }
                }

    # ── UC-07: Government Price Lock ────────────────────────────────────────
    is_price_locked = fields.Boolean(
        string='Government Price Lock',
        default=False,
        tracking=True,
        help='When enabled, the public price cannot be changed except by managers.',
    )

    # ── UC-08: Hide cost if product has no purchase moves ───────────────────
    has_purchase_history = fields.Boolean(
        string='Has Purchase History',
        compute='_compute_has_purchase_history',
        store=False,
    )

    # ── UC-07: Price History Relation ───────────────────────────────────────
    price_history_ids = fields.One2many(
        'pharmacy.price.history',
        'product_id',
        string='Price History',
        readonly=True,
    )

    price_history_count = fields.Integer(
        string='Price Changes',
        compute='_compute_price_history_count',
    )

    # ── Compute Purchase History ────────────────────────────────────────────
    @api.depends('product_variant_ids')
    def _compute_has_purchase_history(self):
        for rec in self:
            move_count = self.env['stock.move'].search_count([
                ('product_id.product_tmpl_id', '=', rec.id),
                ('picking_id.picking_type_id.code', '=', 'incoming'),
                ('state', '=', 'done'),
            ])

            rec.has_purchase_history = move_count > 0

    # ── Compute Price History Count ─────────────────────────────────────────
    @api.depends('price_history_ids')
    def _compute_price_history_count(self):
        for rec in self:
            rec.price_history_count = len(rec.price_history_ids)

    # ── Override Write ──────────────────────────────────────────────────────
    def write(self, vals):

        # Government Price Lock
        if 'list_price' in vals:
            for rec in self:

                # Check locked price
                if rec.is_price_locked:
                    if not self.env.user.has_group(
                        'sales_team.group_sale_manager'
                    ):
                        raise UserError(
                            f"The price of '{rec.name}' is locked by government regulation.\n"
                            "Only a Sales Manager can change it."
                        )

                # Log price history
                old_price = rec.list_price
                new_price = vals['list_price']

                if old_price != new_price:
                    self.env['pharmacy.price.history'].create({
                        'product_id': rec.id,
                        'old_price': old_price,
                        'new_price': new_price,
                        'changed_by': self.env.user.id,
                    })

        return super(ProductTemplatePricing, self).write(vals)


# ═══════════════════════════════════════════════════════════════════
# UC-07: Price History Log
# ═══════════════════════════════════════════════════════════════════
class ProductPriceHistory(models.Model):
    _name = 'pharmacy.price.history'
    _description = 'Product Price History'
    _order = 'change_date desc'
    _rec_name = 'product_id'

    product_id = fields.Many2one(
        'product.template',
        string='Product',
        required=True,
        ondelete='cascade',
        index=True
    )

    old_price = fields.Float(
        string='Old Price',
        digits='Product Price'
    )

    new_price = fields.Float(
        string='New Price',
        digits='Product Price'
    )

    change_date = fields.Datetime(
        string='Changed On',
        default=fields.Datetime.now
    )

    changed_by = fields.Many2one(
        'res.users',
        string='Changed By',
        default=lambda self: self.env.user
    )

    note = fields.Char(string='Reason / Note')