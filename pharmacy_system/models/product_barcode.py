from odoo import models, fields, api, _
from odoo.exceptions import ValidationError
import re


BARCODE_FORMAT = [
    ('ean8',    'EAN-8'),
    ('ean13',   'EAN-13'),
    ('upca',    'UPC-A'),
    ('upce',    'UPC-E'),
    ('code128', 'Code 128'),
    ('internal','Internal / Pharmacy'),
]

BARCODE_UNIT = [
    ('unit',    'Unit'),
    ('package', 'Package'),
]

# Format validation patterns
_FORMAT_PATTERNS = {
    'ean8':    (r'^\d{8}$',    'EAN-8 must be exactly 8 digits.'),
    'ean13':   (r'^\d{13}$',   'EAN-13 must be exactly 13 digits.'),
    'upca':    (r'^\d{12}$',   'UPC-A must be exactly 12 digits.'),
    'upce':    (r'^\d{6,8}$',  'UPC-E must be 6–8 digits.'),
    'code128': (r'^[\x00-\x7F]{1,48}$', 'Code 128 must be 1–48 ASCII characters.'),
    'internal':(r'^[A-Za-z0-9]{1,20}$', 'Internal barcodes must be 1–20 alphanumeric characters.'),
}


class ProductBarcode(models.Model):
    """
    Represents a single barcode entry for a product.template.
    Each product may have exactly one primary barcode and N secondary barcodes.
    """
    _name = 'product.barcode.line'
    _description = 'Product Barcode Line'
    _order = 'is_primary DESC, sequence ASC, id ASC'

    product_tmpl_id = fields.Many2one(
        comodel_name='product.template',
        string='Product Template',
        required=True,
        ondelete='cascade',
        index=True,
    )
    name = fields.Char(
        string='Title / Reference',
        help='Internal reference for this barcode (e.g. PH0000001).',
    )
    barcode = fields.Char(
        string='Barcode Value',
        required=True,
        index=True,
        help='Scan or type the barcode value. Must be unique across all products.',
    )
    barcode_format = fields.Selection(
        selection=BARCODE_FORMAT,
        string='Format',
        required=True,
        default='ean13',
        help='Barcode symbology / format.',
    )
    unit = fields.Selection(
        selection=BARCODE_UNIT,
        string='Unit',
        required=True,
        default='unit',
    )
    notes = fields.Char(
        string='Notes',
        size=256,
    )
    is_primary = fields.Boolean(
        string='Primary',
        default=False,
        help='Only one barcode per product may be primary. Used as the default scan target in PoS.',
    )
    sequence = fields.Integer(
        string='Sequence',
        default=10,
    )

    # ──────────────────────────────────────────────
    # Constraints
    # ──────────────────────────────────────────────

    _sql_constraints = [
        (
            'barcode_global_unique',
            'UNIQUE(barcode)',
            'This barcode already exists on another product. Barcodes must be globally unique.',
        ),
    ]

    @api.constrains('barcode', 'barcode_format')
    def _check_barcode_format(self):
        for rec in self:
            if not rec.barcode or not rec.barcode_format:
                continue
            pattern, message = _FORMAT_PATTERNS.get(rec.barcode_format, (None, None))
            if pattern and not re.match(pattern, rec.barcode):
                raise ValidationError(_(message + '\nGot: "%s"') % rec.barcode)

    @api.constrains('is_primary', 'product_tmpl_id')
    def _check_single_primary(self):
        """Enforce exactly one primary barcode per product template."""
        for rec in self:
            if rec.is_primary:
                domain = [
                    ('product_tmpl_id', '=', rec.product_tmpl_id.id),
                    ('is_primary', '=', True),
                    ('id', '!=', rec.id),
                ]
                if self.search_count(domain) > 0:
                    raise ValidationError(
                        _('Product "%s" already has a primary barcode. '
                          'Please demote the existing primary first.')
                        % rec.product_tmpl_id.name
                    )

    # ──────────────────────────────────────────────
    # Business logic
    # ──────────────────────────────────────────────

    def action_set_as_primary(self):
        """
        Demote all siblings, promote self.
        Called from the tree view button in the barcode tab.
        """
        self.ensure_one()
        siblings = self.search([
            ('product_tmpl_id', '=', self.product_tmpl_id.id),
            ('id', '!=', self.id),
        ])
        siblings.write({'is_primary': False})
        self.write({'is_primary': True})
        # Sync Odoo's native barcode field on product.template
        self.product_tmpl_id.write({'barcode': self.barcode})
        return True

    @api.model
    def _calculate_ean_check_digit(self, barcode_base, length):
        """Calculates GS1 check digit for EAN-8 (7 digits) or EAN-13 (12 digits)."""
        if not barcode_base.isdigit() or len(barcode_base) not in (7, 12):
            return 0
        digits = [int(d) for d in barcode_base]
        # EAN-13: 1, 3, 1, 3... (odd indices weight 3)
        # EAN-8:  3, 1, 3, 1... (even indices weight 3)
        if length == 13:
            total = sum(d * (3 if i % 2 == 1 else 1) for i, d in enumerate(digits))
        else:
            total = sum(d * (1 if i % 2 == 1 else 3) for i, d in enumerate(digits))
        return (10 - (total % 10)) % 10

    @api.model
    def _validate_ean_check_digit(self, barcode, length):
        """Validates EAN-8/13 check digit. Raises ValidationError if invalid."""
        if not barcode or len(barcode) != length or not barcode.isdigit():
            return
        base = barcode[:-1]
        expected = self._calculate_ean_check_digit(base, length)
        if int(barcode[-1]) != expected:
            raise ValidationError(
                _('Invalid check digit for %s barcode "%s". Expected %d.')
                % ('EAN-13' if length == 13 else 'EAN-8', barcode, expected)
            )

    @api.constrains('barcode', 'barcode_format')
    def _check_ean_check_digits(self):
        for rec in self:
            if rec.barcode_format == 'ean13':
                self._validate_ean_check_digit(rec.barcode, 13)
            elif rec.barcode_format == 'ean8':
                self._validate_ean_check_digit(rec.barcode, 8)