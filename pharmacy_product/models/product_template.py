from odoo import models, fields, api
from odoo.exceptions import ValidationError, UserError


class ProductTemplate(models.Model):
    _inherit = 'product.template'

    # ─────────────────────────────────────────────
    # UC-01: Generic / Scientific Name
    # ─────────────────────────────────────────────

    generic_name = fields.Char(
        string='Generic / Scientific Name',
        required=False,
        tracking=True,
        help='Optional scientific or generic name of the product (e.g. Paracetamol).'
    )

    # ─────────────────────────────────────────────
    # UC-02: Product Type — Unit or Package
    # ─────────────────────────────────────────────

    pharmacy_product_type = fields.Selection(
        selection=[
            ('unit',    'Unit'),
            ('package', 'Package'),
        ],
        string='Sell As',
        required=True,
        default='unit',
        tracking=True,
        help='Unit = sold individually. Package = sold as a box/pack containing multiple units.',
    )

    units_per_package = fields.Integer(
        string='Units per Package',
        default=1,
        tracking=True,
        help='How many units are inside one package. Used to auto-configure UoM ratio.',
    )

    # Computed display field: shows stock as "X packages + Y units"
    stock_display = fields.Char(
        string='Stock Display',
        compute='_compute_stock_display',
        store=False,
    )

    # ── Onchange: auto-show/hide units_per_package ──────────────────────────

    @api.onchange('pharmacy_product_type')
    def _onchange_pharmacy_product_type(self):
        if self.pharmacy_product_type == 'unit':
            self.units_per_package = 1

    # ── Compute: real-time display of qty in packages + remaining units ──────

    @api.depends('qty_available', 'units_per_package', 'pharmacy_product_type')
    def _compute_stock_display(self):
        for rec in self:
            if rec.pharmacy_product_type == 'package' and rec.units_per_package > 1:
                total_units = int(rec.qty_available)
                packages    = total_units // rec.units_per_package
                remainder   = total_units  % rec.units_per_package
                rec.stock_display = f"{packages} package(s) + {remainder} unit(s)"
            else:
                rec.stock_display = f"{rec.qty_available} unit(s)"

    # ── Constraint: units_per_package must be > 0 for packages ──────────────

    @api.constrains('pharmacy_product_type', 'units_per_package')
    def _check_units_per_package(self):
        for rec in self:
            if rec.pharmacy_product_type == 'package' and rec.units_per_package < 1:
                raise ValidationError(
                    "Units per Package must be at least 1 for Package-type products."
                )

    # ── Constraint: prevent changing type after stock moves exist ────────────

    @api.constrains('pharmacy_product_type')
    def _check_type_change_after_moves(self):
        for rec in self:
            # Check if any confirmed/done stock moves exist for this product
            move_exists = self.env['stock.move'].search_count([
                ('product_id.product_tmpl_id', '=', rec.id),
                ('state', 'in', ('done', 'assigned', 'waiting', 'confirmed')),
            ])
            if move_exists:
                raise ValidationError(
                    f"Cannot change 'Sell As' type for '{rec.name}' "
                    "because stock moves already exist for this product.\n"
                    "Archive and recreate the product if a type change is needed."
                )

    # ── Override _name_search: UC-01 — search by generic name too ────────────

    @api.model
    def _name_search(self, name='', domain=None, operator='ilike', limit=100, order=None):
        domain = domain or []
        if name:
            # Search in both product name AND generic_name
            domain = [
                '|',
                ('name',         operator, name),
                ('generic_name', operator, name),
            ] + domain
            return self._search(domain, limit=limit, order=order)
        return super()._name_search(name, domain, operator, limit, order)
