# -*- coding: utf-8 -*-
from odoo import api, fields, models
from odoo.osv import expression
from odoo.exceptions import ValidationError


class ProductProduct(models.Model):
    """Exposes ``generic_name`` and ``display_name_full`` on the variant model.

    Both fields are delegated / related to the template so that:
    * All variants of a template share the same generic name by default.
    * The related field is *not* stored – it always mirrors the template value
      without duplicating data.

    If per-variant generic names are required in a future iteration, replace
    ``related`` with a standalone ``Char`` field and adjust the template
    compute accordingly.
    """

    _inherit = 'product.product'

    generic_name = fields.Char(
        related='product_tmpl_id.generic_name',
        string='Generic / Scientific Name',
        readonly=False,
        store=False,
    )

    display_name_full = fields.Char(
        related='product_tmpl_id.display_name_full',
        string='Full Display Name',
        readonly=True,
        store=False,
    )

    # ------------------------------------------------------------------
    # Search
    # ------------------------------------------------------------------

    @api.model
    def _name_search(self, name='', domain=None, operator='ilike', limit=100, order=None):
        """Mirror the template _name_search so that variant-level Many2one
        widgets (POS product picker, purchase/stock order lines) also match
        on ``generic_name``.

        ``generic_name`` on this model is a non-stored related field, so we
        traverse to the template column via ``product_tmpl_id.generic_name``
        which the ORM resolves correctly in SQL through the JOIN.
        """
        domain = domain or []
        if not name:
            return super()._name_search(name, domain, operator, limit, order)

        name_domain = [('name', operator, name)]
        generic_domain = [('product_tmpl_id.generic_name', operator, name)]
        combined = expression.AND([
            domain,
            expression.OR([name_domain, generic_domain]),
        ])
        return self._search(combined, limit=limit, order=order)

    # ------------------------------------------------------------------
    # Actions
    # ------------------------------------------------------------------

    def action_generate_pharmacy_barcode(self):
        """Action: delegates to the template action."""
        self.ensure_one()
        return self.product_tmpl_id.action_generate_pharmacy_barcode()

    def action_open_batch_label_layout(self):
        """Delegate batch print to the template."""
        return self.product_tmpl_id.action_open_batch_label_layout()

    def action_open_barcodes_pos(self):
        """Smart-button action: delegates to the template action."""
        self.ensure_one()
        return self.product_tmpl_id.action_open_barcodes_pos()

    # ─────────────────────────────────────────────
    # UC-02: Product Type — Unit or Package
    # ─────────────────────────────────────────────

    pharmacy_product_type = fields.Selection(
        related='product_tmpl_id.pharmacy_product_type',
        string='Sell As',
        readonly=False,
        store=False,
    )

    units_per_package = fields.Integer(
        related='product_tmpl_id.units_per_package',
        string='Units per Package',
        readonly=False,
        store=False,
    )

    price_per_unit = fields.Float(
        related='product_tmpl_id.price_per_unit',
        string='Price per Unit',
        readonly=True,
        store=False,
    )

    is_medicine = fields.Boolean(
        related='product_tmpl_id.is_medicine',
        string='Is Medicine',
        readonly=False,
        store=False,
    )

    max_qty_per_invoice = fields.Float(
        related='product_tmpl_id.max_qty_per_invoice',
        string='Max Qty per Invoice',
        readonly=False,
        store=False,
    )

    stock_display = fields.Char(
        string='Stock Display',
        compute='_compute_stock_display',
        store=False,
    )

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

    # ─────────────────────────────────────────────
    # Odoo 18 POS Field Loading Integration
    # ─────────────────────────────────────────────

    @api.model
    def _load_pos_data_fields(self, config_id):
        """Extend standard POS product fields with custom pharmacy fields."""
        fields = super()._load_pos_data_fields(config_id)
        # Add custom pharmacy fields to POS loaded fields list
        fields += [
            'generic_name',
            'pharmacy_product_type',
            'units_per_package',
            'price_per_unit',
            'stock_display',
            'is_medicine',
            'max_qty_per_invoice',
        ]
        return fields