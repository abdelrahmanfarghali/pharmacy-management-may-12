from odoo import models, fields, api
from odoo.exceptions import UserError, ValidationError
from datetime import date, timedelta
import logging

_logger = logging.getLogger(__name__)


class StockLot(models.Model):
    _inherit = 'stock.lot'

    # ── SC2-UC-02: Month/Year only expiry input ──────────────────────────────
    expiry_month = fields.Integer(
        string='Expiry Month',
        help='Month of expiry (1–12). Leave 0 to use exact expiry_date.',
    )
    expiry_year = fields.Integer(
        string='Expiry Year',
        help='Year of expiry (e.g. 2026). Leave 0 to use exact expiry_date.',
    )

    @api.onchange('expiry_month', 'expiry_year')
    def _onchange_expiry_month_year(self):
        """Auto-set expiration_date from month/year — last day of the month."""
        if self.expiry_month and self.expiry_year:
            if not (1 <= self.expiry_month <= 12):
                return {'warning': {
                    'title': 'Invalid Month',
                    'message': 'Month must be between 1 and 12.'
                }}
            # Set to last day of the given month
            if self.expiry_month == 12:
                last_day = date(self.expiry_year + 1, 1, 1) - timedelta(days=1)
            else:
                last_day = date(self.expiry_year, self.expiry_month + 1, 1) - timedelta(days=1)
            self.expiration_date = fields.Datetime.to_datetime(
                last_day.strftime('%Y-%m-%d 23:59:59')
            )

    # ── SC2-UC-03: Near-expiry warning threshold ─────────────────────────────
    near_expiry_status = fields.Selection(
        selection=[
            ('ok',          'OK'),
            ('near_expiry', 'Near Expiry'),
            ('expired',     'Expired'),
        ],
        string='Expiry Status',
        compute='_compute_near_expiry_status',
        store=True,
    )

    days_to_expiry = fields.Integer(
        string='Days to Expiry',
        compute='_compute_near_expiry_status',
        store=True,
    )

    @api.depends('expiration_date', 'use_expiration_date', 'use_date', 'removal_date')
    def _compute_near_expiry_status(self):
        """
        SC2-UC-03: Compute expiry status.
        Near-expiry threshold = 90 days (configurable via ir.config_parameter).
        Supports multiple expiry field names across Odoo versions.
        """
        threshold = int(self.env['ir.config_parameter'].sudo().get_param(
            'pharmacy_expiry.near_expiry_days', default=90
        ))
        today = date.today()
        for lot in self:
            # Try multiple possible expiry field names
            exp_dt = (
                getattr(lot, 'expiration_date', None) or
                getattr(lot, 'use_expiration_date', None) or
                getattr(lot, 'use_date', None) or
                getattr(lot, 'removal_date', None)
            )
            if not exp_dt:
                lot.near_expiry_status = 'ok'
                lot.days_to_expiry = 9999
                continue
            exp_date = exp_dt.date() if hasattr(exp_dt, 'date') else exp_dt
            delta = (exp_date - today).days
            lot.days_to_expiry = delta
            if delta < 0:
                lot.near_expiry_status = 'expired'
            elif delta <= threshold:
                lot.near_expiry_status = 'near_expiry'
            else:
                lot.near_expiry_status = 'ok'

    # ── SC2-UC-04: Expired lot detection cron ───────────────────────────────
    @api.model
    def action_detect_and_notify_expired(self):
        """
        SC2-UC-04: Cron job — find expired lots and send notification to
        stock managers. Runs daily via ir.cron.
        """
        today = fields.Datetime.now()
        expired_lots = self.search([
            ('expiration_date', '<=', today),
            ('near_expiry_status', '!=', 'expired'),  # not yet flagged
        ])

        if not expired_lots:
            return

        # Re-compute status
        expired_lots._compute_near_expiry_status()

        # Notify stock managers via internal message
        manager_group = self.env.ref('stock.group_stock_manager', raise_if_not_found=False)
        if manager_group:
            managers = self.env['res.users'].search([
                ('groups_id', 'in', [manager_group.id])
            ])
            partner_ids = managers.mapped('partner_id').ids
            if partner_ids:
                lot_names = ', '.join(expired_lots.mapped('name')[:10])
                if len(expired_lots) > 10:
                    lot_names += f' ... and {len(expired_lots) - 10} more'

                self.env['mail.message'].create({
                    'message_type': 'notification',
                    'subtype_id': self.env.ref('mail.mt_note').id,
                    'body': f"""
                        <p><strong>⚠️ Expired Lots Detected</strong></p>
                        <p>{len(expired_lots)} lot(s) have expired as of today:</p>
                        <p><em>{lot_names}</em></p>
                        <p>Please review the <strong>Expired Medicines</strong> page
                        and transfer them to the expired location.</p>
                    """,
                    'partner_ids': partner_ids,
                    'model': 'stock.lot',
                    'res_id': expired_lots[0].id,
                })

        _logger.info(
            'pharmacy_expiry: %d expired lots detected and notification sent.',
            len(expired_lots)
        )
        return expired_lots

    @api.model
    def action_send_near_expiry_alerts(self):
        """
        SC2-UC-03: Cron job — send near-expiry alerts to stock managers.
        """
        threshold = int(self.env['ir.config_parameter'].sudo().get_param(
            'pharmacy_expiry.near_expiry_days', default=90
        ))
        today = fields.Datetime.now()
        cutoff = fields.Datetime.to_datetime(
            (date.today() + timedelta(days=threshold)).strftime('%Y-%m-%d 23:59:59')
        )
        near_lots = self.search([
            ('expiration_date', '>', today),
            ('expiration_date', '<=', cutoff),
        ])

        if not near_lots:
            return

        manager_group = self.env.ref('stock.group_stock_manager', raise_if_not_found=False)
        if manager_group:
            managers = self.env['res.users'].search([
                ('groups_id', 'in', [manager_group.id])
            ])
            partner_ids = managers.mapped('partner_id').ids
            if partner_ids:
                lot_names = ', '.join(
                    f"{l.name} ({l.days_to_expiry} days)" for l in near_lots[:10]
                )
                self.env['mail.message'].create({
                    'message_type': 'notification',
                    'subtype_id': self.env.ref('mail.mt_note').id,
                    'body': f"""
                        <p><strong>🔔 Near-Expiry Alert</strong></p>
                        <p>{len(near_lots)} lot(s) will expire within {threshold} days:</p>
                        <p><em>{lot_names}</em></p>
                    """,
                    'partner_ids': partner_ids,
                    'model': 'stock.lot',
                    'res_id': near_lots[0].id,
                })

        _logger.info(
            'pharmacy_expiry: %d near-expiry lots alert sent.', len(near_lots)
        )
