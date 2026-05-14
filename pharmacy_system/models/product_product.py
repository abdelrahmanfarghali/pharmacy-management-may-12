# -*- coding: utf-8 -*-
from odoo import api, fields, models
from odoo.osv import expression


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
