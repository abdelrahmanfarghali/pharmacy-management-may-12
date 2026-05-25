from odoo import models, fields, api


class StockLocation(models.Model):
    _inherit = 'stock.location'

    # ── SC2-UC-01: Mark location as "Expired Products" type ─────────────────
    is_expired_location = fields.Boolean(
        string='Expired Products Location',
        default=False,
        help='Mark this location as the destination for expired medicines. '
             'Products quarantined due to expiry will be transferred here.',
    )

    @api.model
    def get_expired_location(self):
        """Return the first expired location or raise a warning."""
        location = self.search([('is_expired_location', '=', True)], limit=1)
        return location
