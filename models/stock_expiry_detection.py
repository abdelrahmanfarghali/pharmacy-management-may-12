# -*- coding: utf-8 -*-
"""
INV-UC-02 — Automated Expiry Detection Job
Scans all lots/serial numbers with on-hand stock in Internal-type locations,
detects expired ones (today >= last day of expiry month), sends notifications,
and creates Odoo Activities on affected products.

Design note: This model is DETECTION ONLY — no stock movements are created.
All transfers are handled manually via INV-UC-09 (Expired Medicines Page).
"""
import calendar
import logging
from datetime import date, datetime

from odoo import api, fields, models, _
from odoo.exceptions import UserError

_logger = logging.getLogger(__name__)


class StockExpiryDetection(models.Model):
    _name = 'stock.expiry.detection'
    _description = 'Expiry Detection Job — INV-UC-02'
    _inherit = ['mail.thread', 'mail.activity.mixin']
    _rec_name = 'run_date'
    _order = 'run_date desc'

    # ─────────────────────────────────────────────
    # Header fields
    # ─────────────────────────────────────────────
    run_date = fields.Datetime(
        string='Run Date',
        default=fields.Datetime.now,
        readonly=True,
    )
    triggered_by = fields.Many2one(
        'res.users',
        string='Triggered By',
        default=lambda self: self.env.user,
        readonly=True,
    )
    trigger_type = fields.Selection(
        [('scheduled', 'Scheduled (Nightly)'), ('manual', 'Manual (On-Demand)')],
        string='Trigger Type',
        default='scheduled',
        readonly=True,
    )
    company_id = fields.Many2one(
        'res.company',
        string='Company',
        default=lambda self: self.env.company,
        readonly=True,
    )
    warehouse_id = fields.Many2one(
        'stock.warehouse',
        string='Warehouse',
        readonly=True,
        help='If blank, all warehouses in the company were scanned.',
    )

    # ─────────────────────────────────────────────
    # Result summary
    # ─────────────────────────────────────────────
    expired_lot_count = fields.Integer(string='Expired Lots Found', readonly=True)
    state = fields.Selection(
        [
            ('done', 'Completed'),
            ('no_results', 'No Expired Lots Found'),
            ('warning', 'Completed with Warnings'),
        ],
        string='Status',
        default='done',
        readonly=True,
    )
    summary_note = fields.Text(string='Summary', readonly=True)
    configuration_warnings = fields.Text(
        string='Configuration Warnings',
        readonly=True,
        help='Warehouses missing an Expired-type location.',
    )

    # ─────────────────────────────────────────────
    # Detected lot lines
    # ─────────────────────────────────────────────
    line_ids = fields.One2many(
        'stock.expiry.detection.line',
        'detection_id',
        string='Detected Expired Lots',
        readonly=True,
    )

    # ═══════════════════════════════════════════════════════════════
    # CORE DETECTION LOGIC
    # ═══════════════════════════════════════════════════════════════

    @api.model
    def _run_expiry_detection(self, warehouse_id=None, trigger_type='scheduled'):
        """
        Main detection entry-point — called by scheduled action or wizard.

        :param warehouse_id: int | None  — scope to a single warehouse, or None for all.
        :param trigger_type: 'scheduled' | 'manual'
        :returns: stock.expiry.detection record
        """
        today = date.today()
        company = self.env.company

        # ── 1. Determine warehouses in scope ────────────────────
        if warehouse_id:
            warehouses = self.env['stock.warehouse'].browse(warehouse_id)
        else:
            warehouses = self.env['stock.warehouse'].search(
                [('company_id', '=', company.id)]
            )

        if not warehouses:
            _logger.warning('INV-UC-02: No warehouses found for company %s', company.name)

        # ── 2. Find all Internal locations for these warehouses ──
        internal_location_ids = self._get_internal_location_ids(warehouses)

        # ── 3. Query lots with on-hand qty > 0 in those locations ─
        expired_lines_data, config_warnings = self._detect_expired_lots(
            internal_location_ids, warehouses, today
        )

        # ── 4. Create detection record ────────────────────────────
        detection = self.create({
            'trigger_type': trigger_type,
            'triggered_by': self.env.user.id,
            'company_id': company.id,
            'warehouse_id': warehouse_id or False,
            'expired_lot_count': len(expired_lines_data),
            'state': (
                'no_results' if not expired_lines_data and not config_warnings
                else 'warning' if config_warnings
                else 'done'
            ),
            'configuration_warnings': '\n'.join(config_warnings) if config_warnings else False,
            'line_ids': [(0, 0, line) for line in expired_lines_data],
        })

        summary_lines = [
            _('Detection run: %s') % fields.Datetime.now(),
            _('Warehouses scanned: %s') % ', '.join(warehouses.mapped('name')),
            _('Expired lots found: %d') % len(expired_lines_data),
        ]
        if config_warnings:
            summary_lines.append(_('⚠ Configuration warnings: %d') % len(config_warnings))

        detection.summary_note = '\n'.join(summary_lines)

        # ── 5. Notifications & activities ─────────────────────────
        if expired_lines_data:
            detection._send_notification()
            detection._create_activities()

        if config_warnings:
            detection._log_config_warnings(config_warnings)

        _logger.info(
            'INV-UC-02: Detection complete — %d expired lots found (run id=%d)',
            len(expired_lines_data),
            detection.id,
        )
        return detection

    # ── Helpers ─────────────────────────────────────────────────────

    def _get_internal_location_ids(self, warehouses):
        """Return all Internal-usage location IDs under the given warehouses."""
        lot_stock_ids = warehouses.mapped('lot_stock_id')
        if not lot_stock_ids:
            return []
        # child_of covers all sub-locations
        locations = self.env['stock.location'].search([
            ('id', 'child_of', lot_stock_ids.ids),
            ('usage', '=', 'internal'),
            ('active', '=', True),
        ])
        return locations.ids

    def _detect_expired_lots(self, internal_location_ids, warehouses, today):
        """
        Scan stock.quant for lots whose expiry date has passed.
        Expiry rule: today >= last_day_of(lot.expiration_date month).

        Returns:
            expired_lines_data: list of dicts for One2many creation
            config_warnings: list of warning strings
        """
        if not internal_location_ids:
            return [], []

        # Find quants with a lot, non-zero qty, in Internal locations
        quants = self.env['stock.quant'].search([
            ('location_id', 'in', internal_location_ids),
            ('lot_id', '!=', False),
            ('quantity', '>', 0),
        ])

        expired_lines_data = []
        config_warnings = []
        warned_warehouses = set()

        for quant in quants:
            lot = quant.lot_id
            expiry_date = lot.expiration_date  # date or datetime field in Odoo

            if not expiry_date:
                continue

            # Normalise to date
            if isinstance(expiry_date, datetime):
                expiry_date = expiry_date.date()

            # Last day of the expiry month
            last_day = self._last_day_of_month(expiry_date)

            if today < last_day:
                continue  # Not yet expired

            # Find the warehouse for this location
            warehouse = self._get_warehouse_for_location(quant.location_id, warehouses)

            # Config check: does this warehouse have an Expired-type location?
            if warehouse and warehouse.id not in warned_warehouses:
                expired_loc = self.env['stock.location'].search([
                    ('usage', '=', 'expired'),
                    ('location_id', 'child_of', warehouse.lot_stock_id.location_id.id),
                    ('active', '=', True),
                ], limit=1)
                if not expired_loc:
                    msg = _(
                        'Warehouse "%s" has no Expired-type location configured. '
                        'Please configure one before transferring detected lots.'
                    ) % warehouse.name
                    config_warnings.append(msg)
                    _logger.warning('INV-UC-02 config warning: %s', msg)
                    warned_warehouses.add(warehouse.id)

            expired_lines_data.append({
                'lot_id': lot.id,
                'product_id': quant.product_id.id,
                'location_id': quant.location_id.id,
                'quantity': quant.quantity,
                'expiry_date': expiry_date,
                'expiry_month_display': expiry_date.strftime('%m/%Y'),
                'warehouse_id': warehouse.id if warehouse else False,
            })

        return expired_lines_data, config_warnings

    @staticmethod
    def _last_day_of_month(d):
        """Return the last calendar day of the month for date d."""
        last = calendar.monthrange(d.year, d.month)[1]
        return date(d.year, d.month, last)

    def _get_warehouse_for_location(self, location, warehouses):
        """Find which warehouse owns this location (by lot_stock_id parent chain)."""
        for wh in warehouses:
            parent_ids = self.env['stock.location'].search(
                [('id', 'parent_of', location.id)]
            ).ids
            if wh.lot_stock_id.id in parent_ids or wh.lot_stock_id.location_id.id in parent_ids:
                return wh
        return warehouses[:1] if warehouses else self.env['stock.warehouse']

    # ═══════════════════════════════════════════════════════════════
    # NOTIFICATIONS
    # ═══════════════════════════════════════════════════════════════

    def _send_notification(self):
        """
        Send an Odoo internal message (mail.thread) summary to Inventory Managers.
        Includes: count, medicine names, lot numbers, expiry dates, quantities,
        current locations, and a direct link to the Expired Medicines page (INV-UC-09).
        """
        self.ensure_one()

        # Determine recipient Inventory Managers
        manager_group = self.env.ref('stock.group_stock_manager', raise_if_not_found=False)
        recipients = self.env['res.users']
        if manager_group:
            recipients = manager_group.users

        # Build expired medicines page URL (INV-UC-09 action, pre-filtered)
        base_url = self.env['ir.config_parameter'].sudo().get_param('web.base.url', '')
        lot_ids = self.line_ids.mapped('lot_id').ids
        action_url = (
            '%s/odoo/inventory/expired-medicines?lot_ids=%s'
            % (base_url, ','.join(str(i) for i in lot_ids))
        )

        # Build table rows
        rows_html = ''
        for line in self.line_ids:
            rows_html += (
                '<tr>'
                '<td>%(product)s</td>'
                '<td>%(lot)s</td>'
                '<td>%(expiry)s</td>'
                '<td>%(qty)s %(uom)s</td>'
                '<td>%(location)s</td>'
                '<td>%(warehouse)s</td>'
                '</tr>'
            ) % {
                'product': line.product_id.display_name,
                'lot': line.lot_id.name,
                'expiry': line.expiry_month_display,
                'qty': line.quantity,
                'uom': line.product_id.uom_id.name,
                'location': line.location_id.complete_name,
                'warehouse': line.warehouse_id.name if line.warehouse_id else '—',
            }

        warnings_html = ''
        if self.configuration_warnings:
            warnings_html = (
                '<div style="background:#fff3cd;border:1px solid #ffc107;'
                'padding:10px;margin-top:12px;border-radius:4px;">'
                '<b>⚠ Configuration Warnings</b><br/>'
                '%s'
                '</div>'
            ) % self.configuration_warnings.replace('\n', '<br/>')

        body = _(
            '<div style="font-family:sans-serif;">'
            '<h3 style="color:#dc3545;">⚠ Expired Medicines Detected — %(count)d Lot(s)</h3>'
            '<p>The nightly expiry scan has detected <b>%(count)d expired lot(s)</b> '
            'with on-hand stock in Internal locations.</p>'
            '<p><b>No stock has been moved.</b> Please review and transfer manually via '
            'the <a href="%(url)s"><b>Expired Medicines page</b></a>.</p>'
            '<table border="1" cellpadding="6" cellspacing="0" '
            'style="border-collapse:collapse;width:100%%;">'
            '<thead style="background:#dc3545;color:#fff;">'
            '<tr><th>Medicine</th><th>Lot / Serial</th><th>Expiry (MM/YYYY)</th>'
            '<th>Qty</th><th>Current Location</th><th>Warehouse</th></tr>'
            '</thead>'
            '<tbody>%(rows)s</tbody>'
            '</table>'
            '%(warnings)s'
            '<p style="margin-top:16px;">'
            '<a href="%(url)s" style="background:#dc3545;color:#fff;padding:8px 16px;'
            'border-radius:4px;text-decoration:none;font-weight:bold;">'
            '→ Go to Expired Medicines Page</a></p>'
            '</div>'
        ) % {
            'count': self.expired_lot_count,
            'url': action_url,
            'rows': rows_html,
            'warnings': warnings_html,
        }

        # Post as internal note to all inventory managers via mail.thread on this record
        self.message_post(
            body=body,
            subject=_('⚠ [Pharmacy] %d Expired Lot(s) Detected — Action Required') % self.expired_lot_count,
            partner_ids=recipients.mapped('partner_id').ids,
            subtype_xmlid='mail.mt_comment',
        )

    def _create_activities(self):
        """
        Create an Odoo Activity on each affected product.
        Activity type: To-Do / Warning
        Message includes link to Expired Medicines page (INV-UC-09).
        """
        self.ensure_one()
        base_url = self.env['ir.config_parameter'].sudo().get_param('web.base.url', '')
        lot_ids = self.line_ids.mapped('lot_id').ids
        action_url = (
            '%s/odoo/inventory/expired-medicines?lot_ids=%s'
            % (base_url, ','.join(str(i) for i in lot_ids))
        )

        # Use the generic 'To-Do' activity type; fall back to first available
        activity_type = (
            self.env.ref('mail.mail_activity_data_todo', raise_if_not_found=False)
            or self.env['mail.activity.type'].search([], limit=1)
        )
        if not activity_type:
            _logger.warning('INV-UC-02: No activity type found — skipping activity creation.')
            return

        # Group lines by product to avoid duplicate activities
        products_processed = set()
        for line in self.line_ids:
            product = line.product_id.product_tmpl_id
            if product.id in products_processed:
                continue
            products_processed.add(product.id)

            note = _(
                '<b>Expired lot detected</b><br/>'
                'Lot: <b>%(lot)s</b> — Expiry: <b>%(expiry)s</b> — '
                'Qty: %(qty)s %(uom)s — Location: %(loc)s<br/>'
                'Please transfer to the Expired location via '
                '<a href="%(url)s">Inventory → Operations → Expired Medicines</a>.'
            ) % {
                'lot': line.lot_id.name,
                'expiry': line.expiry_month_display,
                'qty': line.quantity,
                'uom': line.product_id.uom_id.name,
                'loc': line.location_id.complete_name,
                'url': action_url,
            }

            product.activity_schedule(
                activity_type_id=activity_type.id,
                summary=_('Expired lot detected — transfer to Expired location via Inventory > Operations > Expired Medicines'),
                note=note,
                date_deadline=fields.Date.today(),
                user_id=self.env.user.id,
            )

    def _log_config_warnings(self, config_warnings):
        """Log configuration warnings to the system log and on the detection record."""
        for warning in config_warnings:
            _logger.warning('INV-UC-02 config warning: %s', warning)

    # ═══════════════════════════════════════════════════════════════
    # SCHEDULED ACTION ENTRY-POINT
    # ═══════════════════════════════════════════════════════════════

    @api.model
    def action_run_scheduled_detection(self):
        """
        Called by the ir.cron nightly scheduled action.
        Runs for all warehouses in all active companies.
        """
        companies = self.env['res.company'].search([])
        for company in companies:
            self_company = self.with_company(company)
            self_company._run_expiry_detection(warehouse_id=None, trigger_type='scheduled')


class StockExpiryDetectionLine(models.Model):
    _name = 'stock.expiry.detection.line'
    _description = 'Expiry Detection — Detected Lot Line'

    detection_id = fields.Many2one(
        'stock.expiry.detection',
        string='Detection Run',
        required=True,
        ondelete='cascade',
    )
    lot_id = fields.Many2one('stock.lot', string='Lot / Serial Number', required=True)
    product_id = fields.Many2one('product.product', string='Medicine', required=True)
    location_id = fields.Many2one('stock.location', string='Current Location', required=True)
    quantity = fields.Float(string='On-Hand Qty', digits='Product Unit of Measure')
    expiry_date = fields.Date(string='Expiry Date (raw)')
    expiry_month_display = fields.Char(string='Expiry (MM/YYYY)', size=7)
    warehouse_id = fields.Many2one('stock.warehouse', string='Warehouse')
