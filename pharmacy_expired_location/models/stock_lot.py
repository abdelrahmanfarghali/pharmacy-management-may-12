# -*- coding: utf-8 -*-
"""
SC2-UC-02 — Stock Lot Extension
Adds MM/YYYY expiry date display/input helpers on stock.lot.
- expiry_month_year: Char field displayed as MM/YYYY (computed from expiration_date)
- _set_expiry_from_mmyyyy(): setter that stores last day of entered month
- All expiry calculations continue to use the standard expiration_date field
"""
import calendar
from datetime import date

from odoo import api, fields, models, _
from odoo.exceptions import ValidationError


class StockLot(models.Model):
    _inherit = 'stock.lot'

    # ─────────────────────────────────────────────────────────────
    # MM/YYYY display field (computed + inverse for write-back)
    # ─────────────────────────────────────────────────────────────
    expiry_month_year = fields.Char(
        string='Expiry Date (MM/YYYY)',
        compute='_compute_expiry_month_year',
        inverse='_inverse_expiry_month_year',
        store=False,
        help='Enter expiry as MM/YYYY (e.g. 03/2027). '
             'The system stores the last day of that month internally.',
    )

    @api.depends('expiration_date')
    def _compute_expiry_month_year(self):
        for lot in self:
            if lot.expiration_date:
                d = lot.expiration_date
                if hasattr(d, 'date'):
                    d = d.date()
                lot.expiry_month_year = d.strftime('%m/%Y')
            else:
                lot.expiry_month_year = ''

    def _inverse_expiry_month_year(self):
        for lot in self:
            raw = (lot.expiry_month_year or '').strip()
            if not raw:
                lot.expiration_date = False
                continue
            lot.expiration_date = self._parse_mmyyyy_to_last_day(raw)

    # ─────────────────────────────────────────────────────────────
    # Validation constraint
    # ─────────────────────────────────────────────────────────────
    @api.constrains('expiry_month_year')
    def _check_expiry_month_year(self):
        for lot in self:
            raw = (lot.expiry_month_year or '').strip()
            if raw:
                self._parse_mmyyyy_to_last_day(raw)  # raises if invalid

    # ─────────────────────────────────────────────────────────────
    # Static helper: parse MM/YYYY → last day of month (date)
    # ─────────────────────────────────────────────────────────────
    @staticmethod
    def _parse_mmyyyy_to_last_day(raw):
        """
        Parse a MM/YYYY or M/YYYY string and return the last calendar day
        of that month as a Python date.

        Raises ValidationError on invalid input.
        """
        raw = raw.strip()
        parts = raw.split('/')
        if len(parts) != 2:
            raise ValidationError(
                _('Invalid expiry date "%s". Please enter as MM/YYYY (e.g. 03/2027).') % raw
            )
        try:
            month = int(parts[0])
            year = int(parts[1])
        except ValueError:
            raise ValidationError(
                _('Invalid expiry date "%s". Month and year must be numbers.') % raw
            )

        if not (1 <= month <= 12):
            raise ValidationError(
                _('Invalid month %d in expiry date "%s". Month must be between 01 and 12.') % (month, raw)
            )
        if year < date.today().year - 50:
            raise ValidationError(
                _('Invalid year %d in expiry date "%s".') % (year, raw)
            )

        last_day = calendar.monthrange(year, month)[1]
        return date(year, month, last_day)

    # ─────────────────────────────────────────────────────────────
    # Convenience: expiry_month_display (read-only char, always set)
    # used by detection & reports instead of raw date
    # ─────────────────────────────────────────────────────────────
    expiry_display = fields.Char(
        string='Expiry (MM/YYYY)',
        compute='_compute_expiry_display',
        store=True,
        help='Read-only MM/YYYY display of the expiry date. '
             'Always reflects the stored expiration_date.',
    )

    @api.depends('expiration_date')
    def _compute_expiry_display(self):
        for lot in self:
            if lot.expiration_date:
                d = lot.expiration_date
                if hasattr(d, 'date'):
                    d = d.date()
                lot.expiry_display = d.strftime('%m/%Y')
            else:
                lot.expiry_display = ''
