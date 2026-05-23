from odoo import models, fields, api
from odoo.exceptions import ValidationError


class ProductTemplate(models.Model):
    _inherit = 'product.template'

    # ─────────────────────────────────────────────
    # UC-01: Generic / Scientific Name
    # ─────────────────────────────────────────────

    generic_name = fields.Char(
        string='Generic / Scientific Name',
        required=False,
        tracking=True,
        help='Optional scientific or generic name of the product (e.g. Paracetamol).',
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
        help='How many units are inside one package.',
    )

    # UC-02: Auto price per unit  (list_price / units_per_package)
    price_per_unit = fields.Float(
        string='Price per Unit',
        compute='_compute_price_per_unit',
        store=False,
        digits='Product Price',
        help='Auto-calculated: Public Price ÷ Units per Package.',
    )

    # UC-02: Real-time stock display  "X package(s) + Y unit(s)"
    stock_display = fields.Char(
        string='Stock Display',
        compute='_compute_stock_display',
        store=False,
    )

    # ── Onchange: reset units when switching back to Unit ────────────────────

    @api.onchange('pharmacy_product_type')
    def _onchange_pharmacy_product_type(self):
        if self.pharmacy_product_type == 'unit':
            self.units_per_package = 1

    # ── Onchange: UC-02 Auto-create UoM when type = Package ─────────────────

    @api.onchange('pharmacy_product_type', 'units_per_package')
    def _onchange_auto_create_uom(self):
        """
        UC-02: Auto-create Sales & Purchase UoM when Sell As = Package.
        Creates  'Box of N'  UoM under the Units category if not yet present,
        then assigns it to uom_id and uom_po_id automatically.
        """
        if (
            self.pharmacy_product_type != 'package'
            or not self.units_per_package
            or self.units_per_package < 2
        ):
            return

        UoM      = self.env['uom.uom']
        UoMCateg = self.env['uom.category']

        uom_name   = f"Box of {self.units_per_package}"
        unit_categ = UoMCateg.search([('name', 'ilike', 'Unit')], limit=1)
        if not unit_categ:
            return  # uom module not ready

        existing = UoM.search([
            ('name',        '=', uom_name),
            ('category_id', '=', unit_categ.id),
        ], limit=1)

        if not existing:
            existing = UoM.create({
                'name':        uom_name,
                'category_id': unit_categ.id,
                'factor_inv':  self.units_per_package,  # 1 Box = N units
                'uom_type':    'bigger',
                'rounding':    1.0,
            })

        self.uom_id    = existing
        self.uom_po_id = existing

    # ── Compute: price per unit ──────────────────────────────────────────────

    @api.depends('list_price', 'units_per_package', 'pharmacy_product_type')
    def _compute_price_per_unit(self):
        for rec in self:
            if (
                rec.pharmacy_product_type == 'package'
                and rec.units_per_package > 1
            ):
                rec.price_per_unit = rec.list_price / rec.units_per_package
            else:
                rec.price_per_unit = rec.list_price

    # ── Compute: stock display ───────────────────────────────────────────────

    @api.depends('qty_available', 'units_per_package', 'pharmacy_product_type')
    def _compute_stock_display(self):
        for rec in self:
            if rec.pharmacy_product_type == 'package' and rec.units_per_package > 1:
                total    = int(rec.qty_available)
                packages = total // rec.units_per_package
                units    = total  % rec.units_per_package
                rec.stock_display = f"{packages} package(s) + {units} unit(s)"
            else:
                rec.stock_display = f"{rec.qty_available} unit(s)"

    # ── Constraint: units_per_package >= 1 for packages ─────────────────────

    @api.constrains('pharmacy_product_type', 'units_per_package')
    def _check_units_per_package(self):
        for rec in self:
            if rec.pharmacy_product_type == 'package' and rec.units_per_package < 1:
                raise ValidationError(
                    "Units per Package must be at least 1 for Package-type products."
                )

    # ── Constraint: prevent type change after stock moves ───────────────────

    @api.constrains('pharmacy_product_type')
    def _check_type_change_after_moves(self):
        for rec in self:
            if not rec._origin.id:
                continue  # new record — skip
            old_type = rec._origin.pharmacy_product_type
            if old_type and old_type != rec.pharmacy_product_type:
                move_exists = self.env['stock.move'].search_count([
                    ('product_id.product_tmpl_id', '=', rec.id),
                    ('state', 'in', ('done', 'assigned', 'waiting', 'confirmed')),
                ])
                if move_exists:
                    raise ValidationError(
                        f"Cannot change 'Sell As' type for '{rec.name}' "
                        "because stock moves already exist.\n"
                        "Archive and recreate the product if a type change is needed."
                    )

    # ── UC-01: Search by generic name ───────────────────────────────────────

    @api.model
    def _name_search(self, name='', domain=None, operator='ilike', limit=100, order=None):
        domain = domain or []
        if name:
            domain = [
                '|',
                ('name',         operator, name),
                ('generic_name', operator, name),
            ] + domain
            return self._search(domain, limit=limit, order=order)
