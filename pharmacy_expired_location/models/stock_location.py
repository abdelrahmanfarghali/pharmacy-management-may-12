# -*- coding: utf-8 -*-
"""
INV-UC-01 — Stock Location Extension
Adds "expired" as a new location type and enforces all related business rules.
"""
from odoo import api, fields, models, _
from odoo.exceptions import UserError, ValidationError


class StockLocation(models.Model):
    _inherit = 'stock.location'

    # ─────────────────────────────────────────────
    # Field: extend the existing usage selection
    # ─────────────────────────────────────────────
    usage = fields.Selection(
        selection_add=[('expired', 'Expired')],
        ondelete={'expired': 'set default'},
    )

    # ─────────────────────────────────────────────
    # Field: mandatory transfer reason/note
    # (populated when a picking targets this location)
    # ─────────────────────────────────────────────
    expired_transfer_note = fields.Text(
        string='Transfer Reason',
        help='Mandatory note explaining why stock is being moved to/from this Expired location.',
    )

    # ─────────────────────────────────────────────
    # Computed helper — is this location "expired"?
    # ─────────────────────────────────────────────
    is_expired_location = fields.Boolean(
        string='Is Expired Location',
        compute='_compute_is_expired_location',
        store=True,
        help='True when this location or any of its parents has usage == expired.',
    )

    @api.depends('usage', 'location_id', 'location_id.is_expired_location')
    def _compute_is_expired_location(self):
        for loc in self:
            loc.is_expired_location = (
                loc.usage == 'expired'
                or (loc.location_id and loc.location_id.is_expired_location)
            )

    # ─────────────────────────────────────────────
    # Guard: prevent deletion when stock exists
    # ─────────────────────────────────────────────
    def unlink(self):
        for loc in self:
            if loc.usage == 'expired':
                quants = self.env['stock.quant'].search([
                    ('location_id', 'child_of', loc.id),
                    ('quantity', '>', 0),
                ])
                if quants:
                    raise UserError(
                        _(
                            'Cannot delete the Expired location "%s" because it still '
                            'contains stock. Please move or write off all quantities first.'
                        ) % loc.complete_name
                    )
                # Also block if child locations of type expired exist under this location
                child_expired = self.search([
                    ('id', 'child_of', loc.id),
                    ('id', '!=', loc.id),
                    ('usage', '=', 'expired'),
                ])
                if child_expired:
                    raise UserError(
                        _(
                            'Cannot delete the Expired location "%s" because it has '
                            'child locations of type Expired. Remove child locations first.'
                        ) % loc.complete_name
                    )
        return super().unlink()

    # ─────────────────────────────────────────────
    # Override: prevent changing type away from
    # "expired" while stock still sits there
    # ─────────────────────────────────────────────
    @api.constrains('usage')
    def _check_usage_change(self):
        for loc in self:
            # If usage was 'expired' and is now something else — check quants
            # We compare against the DB value via a fresh read
            loc_db = loc.read(['usage'])[0]
            # Constrain fires after write, so check quant safety differently:
            # If the location now has usage != expired but IS flagged as expired via parent, skip.
            # The real guard is: if location previously had stock in expired type and someone
            # changes it — we cannot easily detect "previous" in constrains, so we leave the
            # unlink guard as the primary gate and rely on write override below.
            pass

    def write(self, vals):
        if 'usage' in vals and vals['usage'] != 'expired':
            for loc in self:
                if loc.usage == 'expired':
                    quants = self.env['stock.quant'].search([
                        ('location_id', 'child_of', loc.id),
                        ('quantity', '>', 0),
                    ])
                    if quants:
                        raise UserError(
                            _(
                                'Cannot change the type of Expired location "%s" because '
                                'it still contains stock. Move or write off all quantities first.'
                            ) % loc.complete_name
                        )
        return super().write(vals)

    # ─────────────────────────────────────────────
    # Helper: return all expired location IDs
    # (used by quant / POS overrides)
    # ─────────────────────────────────────────────
    @api.model
    def get_expired_location_ids(self):
        """Return a flat list of all location IDs that are of type Expired
        or whose parent chain contains an Expired location."""
        expired_roots = self.search([('usage', '=', 'expired')])
        if not expired_roots:
            return []
        all_ids = set()
        for root in expired_roots:
            children = self.search([('id', 'child_of', root.id)])
            all_ids.update(children.ids)
        return list(all_ids)
