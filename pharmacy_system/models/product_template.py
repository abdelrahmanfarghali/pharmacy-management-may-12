# -*- coding: utf-8 -*-
from odoo import _, api, fields, models
from odoo.exceptions import ValidationError, UserError
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

    barcode_line_ids = fields.One2many(
        comodel_name='product.barcode.line',
        inverse_name='product_tmpl_id',
        string='Barcodes',
        copy=True,
    )
    barcode_count = fields.Integer(
        string='# Barcodes',
        compute='_compute_barcode_count',
        store=True,
    )
    primary_barcode_id = fields.Many2one(
        comodel_name='product.barcode.line',
        string='Primary Barcode',
        compute='_compute_primary_barcode',
        store=True,
        help='Computed from the barcode_line_ids. Read-only; use "Set as Primary" button.',
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

    @api.depends('barcode_line_ids')
    def _compute_barcode_count(self):
        for tmpl in self:
            tmpl.barcode_count = len(tmpl.barcode_line_ids)

    @api.depends('barcode_line_ids.is_primary')
    def _compute_primary_barcode(self):
        for tmpl in self:
            primary = tmpl.barcode_line_ids.filtered('is_primary')[:1]
            tmpl.primary_barcode_id = primary

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


    # ──────────────────────────────────────────────
    # ORM overrides
    # ──────────────────────────────────────────────

    @api.model_create_multi
    def create(self, vals_list):
        records = super().create(vals_list)
        for tmpl in records:
            # If the native `barcode` field was set at creation and no
            # barcode_line_ids were provided, auto-create the primary line.
            if tmpl.barcode and not tmpl.barcode_line_ids:
                self.env['product.barcode.line'].create({
                    'product_tmpl_id': tmpl.id,
                    'barcode': tmpl.barcode,
                    'barcode_format': 'ean13',
                    'unit': 'unit',
                    'is_primary': True,
                })
            elif tmpl.barcode_line_ids and not tmpl.barcode_line_ids.filtered('is_primary'):
                # Promote first line to primary if none set
                tmpl.barcode_line_ids[0].write({'is_primary': True})
            self._sync_native_barcode(tmpl)
        return records

    def write(self, vals):
        res = super().write(vals)
        for tmpl in self:
            self._sync_native_barcode(tmpl)
        return res

    # ──────────────────────────────────────────────
    # Helpers
    # ──────────────────────────────────────────────

    def _sync_native_barcode(self, tmpl):
        """Keep Odoo's built-in barcode field in sync with the primary barcode line."""
        primary = tmpl.barcode_line_ids.filtered('is_primary')[:1]
        if primary and tmpl.barcode != primary.barcode:
            # Use SQL write on product_product to avoid recursion through write()
            self.env.cr.execute(
                "UPDATE product_product SET barcode = %s WHERE product_tmpl_id = %s",
                (primary.barcode, tmpl.id)
            )
            tmpl.invalidate_recordset(['barcode'])

    # ──────────────────────────────────────────────
    # Actions (called from view buttons)
    # ──────────────────────────────────────────────

    def action_generate_pharmacy_barcode(self):
        """
        Wizard-less generation: fetches the active pharmacy sequence
        and creates or replaces a primary/generated barcode line with a valid numeric code
        and an internal title (e.g. PH0000001).
        """
        self.ensure_one()
        sequence = self.env['pharmacy.barcode.sequence'].search(
            [('active', '=', True)], limit=1, order='id asc'
        )
        if not sequence:
            raise UserError(
                _('No active pharmacy barcode sequence found. '
                  'Please configure one under Configuration → Barcode Sequences.')
            )
        data = sequence.generate_next_barcode()
        new_barcode = data['barcode']
        new_title = data['title']
        new_format = data['format']
        
        # Replace Strategy: If the record has a previously generated barcode which is primary,
        # replace it instead of creating a duplicate line!
        generated_primary_lines = self.barcode_line_ids.filtered(
            lambda l: l.is_primary and l.barcode and (l.barcode.startswith('29') or l.barcode.startswith(sequence.prefix))
        )
        if generated_primary_lines:
            line_to_replace = generated_primary_lines[0]
            line_to_replace.write({
                'name': new_title,
                'barcode': new_barcode,
                'barcode_format': new_format,
            })
            self.write({'barcode': new_barcode})
        else:
            has_primary = bool(self.barcode_line_ids.filtered('is_primary'))
            self.env['product.barcode.line'].create({
                'product_tmpl_id': self.id,
                'name': new_title,
                'barcode': new_barcode,
                'barcode_format': new_format,
                'unit': 'unit',
                'is_primary': not has_primary,
            })
            
        return {
            'type': 'ir.actions.client',
            'tag': 'display_notification',
            'params': {
                'title': _('Barcode Generated'),
                'message': _('New barcode %s (%s) has been created.') % (new_barcode, new_title),
                'type': 'success',
                'sticky': False,
            },
        }

    def action_open_batch_label_layout(self):
        """Opens the label layout wizard with the batch print flag enabled."""
        self.ensure_one()
        action = self.env['ir.actions.act_window']._for_xml_id('product.action_open_label_layout')
        action.update({
            'name': _('Batch Print Labels'),
            'context': {
                'default_product_tmpl_ids': self.ids,
                'default_print_all_barcodes': True,
            },
        })
        return action

    def action_open_barcodes_pos(self):
        """Smart-button action: opens the barcodes tab in a modal from PoS context."""
        self.ensure_one()
        return {
            'type': 'ir.actions.act_window',
            'name': _('Barcodes — %s') % self.name,
            'res_model': 'product.barcode.line',
            'view_mode': 'list,form',
            'domain': [('product_tmpl_id', '=', self.id)],
            'context': {'default_product_tmpl_id': self.id},
            'target': 'new',
        }