# -*- coding: utf-8 -*-
"""
INV-UC-01 — Stock Picking Extension
- Blocks transfers FROM Expired to anything except Scrap or another Expired
- Makes transfer note mandatory when Expired location is involved
- Logs traceability messages on the chatter
"""
from odoo import api, fields, models, _
from odoo.exceptions import UserError, ValidationError


class StockPicking(models.Model):
    _inherit = 'stock.picking'

    # ─────────────────────────────────────────────
    # Mandatory reason note for expired transfers
    # ─────────────────────────────────────────────
    expired_transfer_reason = fields.Text(
        string='Expired Transfer Reason',
        help='Mandatory explanation for any transfer involving an Expired location.',
    )

    involves_expired_location = fields.Boolean(
        string='Involves Expired Location',
        compute='_compute_involves_expired_location',
        store=True,
    )

    @api.depends(
        'move_ids.location_id',
        'move_ids.location_dest_id',
        'move_ids.location_id.usage',
        'move_ids.location_dest_id.usage',
        'move_ids.location_id.is_expired_location',
        'move_ids.location_dest_id.is_expired_location',
    )
    def _compute_involves_expired_location(self):
        for picking in self:
            picking.involves_expired_location = any(
                move.location_id.is_expired_location
                or move.location_dest_id.is_expired_location
                for move in picking.move_ids
            )

    # ─────────────────────────────────────────────
    # Validation on confirmation
    # ─────────────────────────────────────────────
    def button_validate(self):
        for picking in self:
            picking._check_expired_transfer_rules()
        return super().button_validate()

    def action_confirm(self):
        for picking in self:
            picking._check_expired_transfer_rules()
        return super().action_confirm()

    def _check_expired_transfer_rules(self):
        """
        Enforce:
        1. Transfers OUT of Expired must go to Scrap or another Expired — never to Internal/Customer.
        2. Expired transfer reason is mandatory when any Expired location is involved.
        """
        for move in self.move_ids:
            src = move.location_id
            dst = move.location_dest_id

            # Rule 1 — Outbound from Expired
            if src.is_expired_location:
                allowed_dest_types = ('expired', 'inventory')   # 'inventory' = scrap in Odoo
                # Also allow locations whose complete_name contains 'Scrap' (scrap locations)
                is_scrap = (
                    dst.scrap_location
                    or dst.usage in allowed_dest_types
                    or dst.is_expired_location
                )
                if not is_scrap:
                    raise UserError(
                        _(
                            'Transfer blocked!\n\n'
                            'Stock in Expired location "%(src)s" can only be moved to a '
                            'Scrap location or another Expired location.\n\n'
                            'Destination "%(dst)s" (type: %(type)s) is not allowed.\n\n'
                            'This is a patient-safety requirement — expired medications '
                            'must never re-enter the supply chain.'
                        ) % {
                            'src': src.complete_name,
                            'dst': dst.complete_name,
                            'type': dst.usage,
                        }
                    )

        # Rule 2 — Mandatory reason note
        if self.involves_expired_location and not (self.expired_transfer_reason or '').strip():
            raise UserError(
                _(
                    'A transfer reason is mandatory for any operation involving an '
                    'Expired location.\n\n'
                    'Please fill in the "Expired Transfer Reason" field before confirming.'
                )
            )

    # ─────────────────────────────────────────────
    # Traceability — log who moved expired stock
    # ─────────────────────────────────────────────
    def _log_activity_default(self, *args, **kwargs):
        return super()._log_activity_default(*args, **kwargs)

    def button_validate(self):  # noqa: F811
        result = None
        for picking in self:
            picking._check_expired_transfer_rules()

        result = super().button_validate()

        # Post traceability message after successful validation
        for picking in self:
            if picking.involves_expired_location:
                expired_moves = picking.move_ids.filtered(
                    lambda m: m.location_id.is_expired_location
                    or m.location_dest_id.is_expired_location
                )
                if expired_moves:
                    lines = []
                    for m in expired_moves:
                        lines.append(
                            '• %s: %s → %s (qty: %s %s)'
                            % (
                                m.product_id.display_name,
                                m.location_id.complete_name,
                                m.location_dest_id.complete_name,
                                m.quantity,
                                m.product_uom.name,
                            )
                        )
                    body = _(
                        '<b>⚠️ Expired Location Transfer — Traceability Log</b><br/>'
                        'Performed by: <b>%(user)s</b><br/>'
                        'Reason: %(reason)s<br/><br/>'
                        '%(lines)s'
                    ) % {
                        'user': self.env.user.name,
                        'reason': picking.expired_transfer_reason or _('(no reason provided)'),
                        'lines': '<br/>'.join(lines),
                    }
                    picking.message_post(body=body, subtype_xmlid='mail.mt_note')
        return result
