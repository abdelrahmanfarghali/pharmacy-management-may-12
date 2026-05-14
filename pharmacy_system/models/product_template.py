# -*- coding: utf-8 -*-
from odoo import _, api, fields, models
from odoo.osv import expression


class ProductTemplate(models.Model):
    """Extends product.template with an optional generic / scientific name.

    The ``generic_name`` field is free-text and intentionally unconstrained so
    it accommodates INN (International Nonproprietary Names), IUPAC names,
    common scientific binomials, or any other naming convention the business
    requires.

    ``display_name_full`` is a *computed, non-stored* helper that downstream
    reports and integrations can reference without additional Python logic.
    """

    _inherit = 'product.template'

    generic_name = fields.Char(
        string='Generic / Scientific Name',
        index=True,
        translate=True,
        help=(
            'Optional free-text field for the generic, INN, or scientific name '
            'of the product.  Displayed alongside the brand name on receipts '
            'and reports when provided.'
        ),
    )

    display_name_full = fields.Char(
        string='Full Display Name',
        compute='_compute_display_name_full',
        store=False,
        help='Returns "Brand Name (Generic Name)" when a generic name exists, '
             'otherwise falls back to the standard product name.',
    )

    # ------------------------------------------------------------------
    # Compute
    # ------------------------------------------------------------------

    @api.depends('name', 'generic_name')
    def _compute_display_name_full(self):
        for rec in self:
            if rec.generic_name:
                rec.display_name_full = f'{rec.name} ({rec.generic_name})'
            else:
                rec.display_name_full = rec.name

    # ------------------------------------------------------------------
    # Search
    # ------------------------------------------------------------------

    @api.model
    def _name_search(self, name='', domain=None, operator='ilike', limit=100, order=None):
        """Extend the default name search to also match ``generic_name``.

        Odoo's base implementation only searches ``_rec_name`` (``name``).
        We union the standard domain with a ``generic_name`` clause so that
        typing "paracetamol" in any Many2one / search-bar that targets
        ``product.template`` will surface products whose brand name differs.

        The ``expression`` helper is used (rather than raw string domains) to
        correctly handle all operators including ``not ilike``, ``=``, etc.
        """
        domain = domain or []
        if not name:
            return super()._name_search(name, domain, operator, limit, order)

        # Build parallel domain branches and OR them together
        name_domain = [('name', operator, name)]
        generic_domain = [('generic_name', operator, name)]
        combined = expression.AND([
            domain,
            expression.OR([name_domain, generic_domain]),
        ])
        return self._search(combined, limit=limit, order=order)

    @api.onchange('name', 'generic_name')
    def _onchange_warn_generic_name_similarity(self):
        """Soft warning – does NOT block save.

        Checks for:
        1. Similarity between brand name and generic name (potential user error).
        2. Name redundancy (existing product with the same name).
        """
        if not self.name:
            return

        warnings = []

        # 1. Similarity check
        if self.generic_name:
            brand = self.name.strip().lower()
            generic = self.generic_name.strip().lower()

            if brand == generic or brand in generic or generic in brand:
                warnings.append(_(
                    'The generic/scientific name "%s" appears very similar to the product name "%s".\n'
                    'The generic name should reflect the INN, IUPAC, or scientific name — not repeat the brand name.'
                ) % (self.generic_name, self.name))

        # 2. Redundancy (duplicate name) check
        # We use =ilike for case-insensitive exact match
        domain = [('name', '=ilike', self.name.strip())]
        if self._origin.id:
            domain.append(('id', '!=', self._origin.id))

        existing = self.env['product.template'].search(domain, limit=1)
        if existing:
            warnings.append(_(
                'A product with the name "%s" already exists in the system. '
                'Please verify if this is a duplicate entry.'
            ) % self.name)

        if warnings:
            return {
                'warning': {
                    'title': _('Product Validation Warning'),
                    'message': "\n\n".join(warnings),
                    'type': 'dialog',
                }
            }