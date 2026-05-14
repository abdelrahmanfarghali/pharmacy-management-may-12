from odoo import models, fields, api, _
from odoo.exceptions import ValidationError
import re


class PharmacyBarcodeSequence(models.Model):
    """
    Configurable sequence model for pharmacy-internal barcode generation.
    Supports prefix + zero-padded auto-increment.
    """
    _name = 'pharmacy.barcode.sequence'
    _description = 'Pharmacy Barcode Sequence Configuration'
    _rec_name = 'name'

    name = fields.Char(
        string='Configuration Name',
        required=True,
        default='Default Pharmacy Sequence',
    )
    prefix = fields.Char(
        string='Barcode Prefix',
        required=True,
        default='PH',
        size=6,
        help='Alphanumeric prefix prepended to each generated barcode (max 6 chars).',
    )
    next_number = fields.Integer(
        string='Next Number',
        required=True,
        default=1,
        help='Auto-incremented counter. Padded with zeros to fill the remaining barcode length.',
    )
    padding = fields.Integer(
        string='Number Padding',
        required=True,
        default=7,
        help='Total digits for the numeric part (zero-padded). e.g. padding=7 → 0000001',
    )
    target_format = fields.Selection(
        selection=[
            ('ean8', 'EAN-8'),
            ('ean13', 'EAN-13'),
            ('internal', 'Internal / Pharmacy'),
        ],
        string='Target Barcode Format',
        required=True,
        default='ean13',
        help='Determines how the actual numeric barcode is generated.',
    )
    active = fields.Boolean(default=True)

    _sql_constraints = [
        ('name_unique', 'UNIQUE(name)', 'Sequence configuration name must be unique.'),
    ]

    @api.constrains('prefix')
    def _check_prefix(self):
        for rec in self:
            if not re.match(r'^[A-Za-z0-9]{1,6}$', rec.prefix):
                raise ValidationError(
                    _('Prefix must be 1–6 alphanumeric characters. Got: "%s"') % rec.prefix
                )

    @api.constrains('padding')
    def _check_padding(self):
        for rec in self:
            if not (1 <= rec.padding <= 12):
                raise ValidationError(_('Padding must be between 1 and 12.'))

    def generate_next_barcode(self):
        """
        Thread-safe generation of the next barcode entry.
        Returns a dict: {'title': str, 'barcode': str, 'format': str}
        """
        self.ensure_one()
        self.env.cr.execute(
            "SELECT next_number FROM pharmacy_barcode_sequence WHERE id = %s FOR UPDATE",
            (self.id,)
        )
        row = self.env.cr.fetchone()
        current = row[0]
        self.write({'next_number': current + 1})

        # Title: Prefix + Padded number (e.g. PH0000002)
        title = f"{self.prefix}{str(current).zfill(self.padding)}"

        # Barcode Value: Valid numeric based on format
        barcode_value = title  # Default for internal
        if self.target_format == 'ean13':
            # Use '29' internal prefix + padded number to reach 12 digits + check digit
            base = f"29{str(current).zfill(10)}"
            check_digit = self.env['product.barcode.line']._calculate_ean_check_digit(base, 13)
            barcode_value = f"{base}{check_digit}"
        elif self.target_format == 'ean8':
            # Use '29' internal prefix + padded number to reach 7 digits + check digit
            base = f"29{str(current).zfill(5)}"
            check_digit = self.env['product.barcode.line']._calculate_ean_check_digit(base, 8)
            barcode_value = f"{base}{check_digit}"

        return {
            'title': title,
            'barcode': barcode_value,
            'format': self.target_format,
        }