# -*- coding: utf-8 -*-
"""
SC2-UC-05 — Expired Medicines Page
Provides:
  1. A read-only list of all medicine lots that have expired (today > last day of
     expiry month) and are NOT yet in an Expired-type location.
  2. Bulk transfer action: creates a single internal stock.picking (auto-validated)
     that moves all selected lots to the warehouse's Expired location.
  3. Near-expiry filter tabs (30 / 60 / 90 days) — awareness only, no transfer.
  4. Sales / POS expired warning override on sale.order.line.

SC2-UC-01 provides the Expired location type.
SC2-UC-02 provides the expiration_date stored as last day of month.
"""
import calendar
import logging
from datetime import date, timedelta

from odoo import api, fields, models, _
from odoo.exceptions import UserError

_logger = logging.getLogger(__name__)


# ═══════════════════════════════════════════════════════════════════════════
# EXPIRED MEDICINES PAGE — virtual model (reads stock.quant live)
# ═══════════════════════════════════════════════════════════════════════════
#نزود هنا زر بيحول المنتج اللي منتهي الصلاحيه من  المخزن الى المخزن الجديد المنتهي الصلاحيه
#نزود فلتر اختار الادويه اللي فاضل عليها 30-60-90 يوم وافلتر بيهم
class ExpiredMedicinesLine(models.TransientModel):
    """
    Transient model: one row per (product, lot, location) combination
    where the lot has expired and stock is not yet in an Expired location.
    Used by the Expired Medicines Page list view.
    """
    _name = 'pharmacy.expired.medicines.line'
    _description = 'Expired Medicines Page — Row (SC2-UC-05)'
    _order = 'expiration_date asc, product_name asc'

    wizard_id = fields.Many2one(
        'pharmacy.expired.medicines.wizard',
        string='Wizard',
        ondelete='cascade',
    )

    # ── Display columns ──────────────────────────────────────────
    barcode = fields.Char(string='Barcode', readonly=True)
    product_id = fields.Many2one('product.product', string='اسم الدواء', readonly=True)
    product_name = fields.Char(string='Medicine Name', readonly=True)
    lot_id = fields.Many2one('stock.lot', string='Lot / Serial', readonly=True)
    expiration_date = fields.Date(string='Raw Expiry Date', readonly=True)
    expiry_display = fields.Char(string='تاريخ الصالحية (MM/YYYY)', readonly=True)
    qty_boxes = fields.Float(string='عدد العلب', readonly=True, digits='Product Unit of Measure')
    qty_units = fields.Float(string='عدد الوحدات', readonly=True, digits='Product Unit of Measure')
    location_id = fields.Many2one('stock.location', string='المخزن', readonly=True)
    quant_id = fields.Many2one('stock.quant', string='Quant', readonly=True)

    # ── Near-expiry category ─────────────────────────────────────
    expiry_category = fields.Selection([
        ('expired', 'Expired'),
        ('near_30', 'Expiring in 30 days'),
        ('near_60', 'Expiring in 60 days'),
        ('near_90', 'Expiring in 90 days'),
    ], string='Expiry Category', readonly=True)

    # ── Transfer selection ───────────────────────────────────────
    selected = fields.Boolean(
        string='تحويل',
        default=False,
        help='Select this lot for bulk transfer to the Expired location.',
    )

    @api.onchange('selected')
    def _onchange_selected(self):
        """Prevent selection of near-expiry rows (not yet expired)."""
        for line in self:
            if line.selected and line.expiry_category != 'expired':
                line.selected = False
                return {
                    'warning': {
                        'title': _('Cannot Select'),
                        'message': _('Cannot transfer — this medicine has not yet expired.'),
                    }
                }


# ═══════════════════════════════════════════════════════════════════════════
# EXPIRED MEDICINES WIZARD — the controller/page
# ═══════════════════════════════════════════════════════════════════════════

class ExpiredMedicinesWizard(models.TransientModel):
    """
    Wizard that backs the Expired Medicines Page.
    On creation it auto-loads all expired lots.
    The user selects rows and clicks 'Transfer Selected'.
    """
    _name = 'pharmacy.expired.medicines.wizard'
    _description = 'Expired Medicines Page — SC2-UC-05'

    line_ids = fields.One2many(
        'pharmacy.expired.medicines.line',
        'wizard_id',
        string='Expired Medicines',
    )

    # ── Summary counters (display only) ─────────────────────────
    total_expired = fields.Integer(
        string='Total Expired Lots',
        compute='_compute_counters',
    )
    total_near_30 = fields.Integer(
        string='Expiring in 30 days',
        compute='_compute_counters',
    )
    total_near_60 = fields.Integer(
        string='Expiring in 60 days',
        compute='_compute_counters',
    )
    total_near_90 = fields.Integer(
        string='Expiring in 90 days',
        compute='_compute_counters',
    )
    selected_count = fields.Integer(
        string='Selected for Transfer',
        compute='_compute_counters',
    )
    filter_category = fields.Selection([
    ('all', 'All'),
    ('expired', 'Expired'),
    ('near_30', '30 Days'),
    ('near_60', '60 Days'),
    ('near_90', '90 Days'),
    ], default='all')
    # def action_show_all(self):
    #     self.filter_category = 'all'
    #     return self._reopen()

    # def action_show_expired(self):
    #     self.filter_category = 'expired'
    #     return self._reopen()

    # def action_show_30(self):
    #     self.filter_category = 'near_30'
    #     return self._reopen()

    # def action_show_60(self):
    #     self.filter_category = 'near_60'
    #     return self._reopen()

    # def action_show_90(self):
    #     self.filter_category = 'near_90'
    #     return self._reopen()
    
    @api.depends('line_ids.expiry_category', 'line_ids.selected')
    def _compute_counters(self):
        for wiz in self:
            wiz.total_expired = len(wiz.line_ids.filtered(lambda l: l.expiry_category == 'expired'))
            wiz.total_near_30 = len(wiz.line_ids.filtered(lambda l: l.expiry_category == 'near_30'))
            wiz.total_near_60 = len(wiz.line_ids.filtered(lambda l: l.expiry_category == 'near_60'))
            wiz.total_near_90 = len(wiz.line_ids.filtered(lambda l: l.expiry_category == 'near_90'))
            wiz.selected_count = len(wiz.line_ids.filtered('selected'))

    # Active filter tab
    active_tab = fields.Selection([
        ('expired', 'All Expired'),
        ('near_30', 'Expiring in 30 days'),
        ('near_60', 'Expiring in 60 days'),
        ('near_90', 'Expiring in 90 days'),
    ], string='Active Tab', default='expired')

    # ── Load lines on creation ───────────────────────────────────
    @api.model
    def default_get(self, fields_list):
        vals = super().default_get(fields_list)
        return vals

    def action_load_lines(self):
        """(Re)load all expired & near-expiry lots into line_ids."""
        self.ensure_one()
        self.line_ids.unlink()
        lines = self._build_lines()
        self.line_ids = [(0, 0, l) for l in lines]
        return self._reopen()

    @api.model
    def create(self, vals):
        """Auto-load lines when wizard is opened."""
        wiz = super().create(vals)
        lines = wiz._build_lines()
        wiz.line_ids = [(0, 0, l) for l in lines]
        return wiz

    # ── Core: build line data ────────────────────────────────────
    def _build_lines(self):
        """
        Query stock.quant for:
        - Lots with expiration_date set
        - qty > 0
        - Location is NOT Expired-type
        - Location IS Internal-type
        Then classify each as expired / near_30 / near_60 / near_90.
        """
        today = date.today()
        expired_location_ids = self.env['stock.location'].get_expired_location_ids()
        
        
    
        domain = [
            ('lot_id', '!=', False),
            ('lot_id.expiration_date', '!=', False),
            ('quantity', '>', 0),
            ('location_id.usage', '=', 'internal'),
        ]
        if expired_location_ids:
            domain.append(('location_id', 'not in', expired_location_ids))

        quants = self.env['stock.quant'].search(domain)

        lines = []
        for quant in quants:
            lot = quant.lot_id
            exp = lot.expiration_date
            if hasattr(exp, 'date'):
                exp = exp.date()
            

            # Last day of expiry month
            last_day = self._last_day_of_month(exp)
            days_remaining = (last_day - today).days

            # Classify
            if days_remaining < 0:
                category = 'expired'
            elif days_remaining <= 30:
                category = 'near_30'
            elif days_remaining <= 60:
                category = 'near_60'
            elif days_remaining <= 90:
                category = 'near_90'
            else:
                continue  # more than 90 days: skip
            # Apply filter AFTER category is assigned
            selected_filter = self.filter_category or 'all'

            if selected_filter != 'all' and category != selected_filter:
                continue
            
            product = quant.product_id

            # Boxes vs units
            # If product has a 'units per box' custom field, use it; otherwise qty = boxes
            units_per_box = getattr(product.product_tmpl_id, 'units_per_box', False) or 1.0
            qty_boxes = quant.quantity
            qty_units = quant.quantity * units_per_box

            lines.append({
                'barcode': product.barcode or '',
                'product_id': product.id,
                'product_name': product.display_name,
                'lot_id': lot.id,
                'expiration_date': last_day,
                'expiry_display': exp.strftime('%m/%Y'),
                'qty_boxes': qty_boxes,
                'qty_units': qty_units,
                'location_id': quant.location_id.id,
                'quant_id': quant.id,
                'expiry_category': category,
                'selected': False,
            })

        # Sort: expired first (oldest first), then near-expiry ascending
        lines.sort(key=lambda l: (
            0 if l['expiry_category'] == 'expired' else
            1 if l['expiry_category'] == 'near_30' else
            2 if l['expiry_category'] == 'near_60' else 3,
            l['expiration_date'],
        ))
        return lines
    def _apply_filter(self, filter_name):
        self.ensure_one()

        self.filter_category = filter_name

        self.line_ids.unlink()

        lines = self._build_lines()

        self.line_ids = [(0, 0, vals) for vals in lines]

        return self._reopen()
    
    def action_show_expired(self):
        return self._apply_filter('expired')


    def action_show_30(self):
        return self._apply_filter('near_30')


    def action_show_60(self):
        return self._apply_filter('near_60')


    def action_show_90(self):
        return self._apply_filter('near_90')


    def action_show_all(self):
        return self._apply_filter('all')
    @staticmethod
    def _last_day_of_month(d):
        last = calendar.monthrange(d.year, d.month)[1]
        return date(d.year, d.month, last)

    # ── Select All / Deselect All ────────────────────────────────
    def action_select_all(self):
        """Select all EXPIRED rows (near-expiry cannot be selected)."""
        self.ensure_one()
        for line in self.line_ids:
            if line.expiry_category == 'expired':
                line.selected = True
        return self._reopen()

    def action_deselect_all(self):
        self.ensure_one()
        self.line_ids.write({'selected': False})
        return self._reopen()

    # ── Transfer Selected ────────────────────────────────────────
    def action_transfer_selected(self):
        """
        Create internal stock.picking(s) for all selected lots,
        force-validate them to state=done, and return a notification.
        """
        self.ensure_one()
        selected_lines = self.line_ids.filtered(
            lambda l: l.selected and l.expiry_category == 'expired'
        )
        if not selected_lines:
            raise UserError(_(
                'No lots selected for transfer. '
                'Please select at least one expired medicine lot.'
            ))

        picking_data = self._prepare_picking_data(selected_lines)

        created_pickings = self.env['stock.picking']
        for picking_vals, move_vals_list in picking_data:

            # 1. Create picking
            picking = self.env['stock.picking'].create(picking_vals)

            # 2. Create moves (بدون lot_ids — هيتحط على move.line بعدين)
            for mv in move_vals_list:
                mv['picking_id'] = picking.id
                mv.pop('lot_ids', None)  # شيل lot_ids من move_vals لأنه مش field صح
                self.env['stock.move'].create(mv)

            # 3. Confirm → assign (skip reason check على كل الخطوات)
            ctx = {'skip_expired_reason_check': True}
            picking.with_context(**ctx).action_confirm()
            picking.with_context(**ctx).action_assign()

            # 4. Force done quantities على move lines
            for move in picking.move_ids:
                # جيب الـ wizard line المقابلة للمنتج ده
                wiz_line = selected_lines.filtered(
                    lambda l, m=move: l.product_id.id == m.product_id.id
                )[:1]

                lot_id = wiz_line.lot_id.id if wiz_line and wiz_line.lot_id else False

                if move.move_line_ids:
                    # حدّث الـ move lines الموجودة
                    for ml in move.move_line_ids:
                        ml.write({
                            'lot_id': lot_id,
                            'quantity': move.product_uom_qty,
                        })
                else:
                    # أنشئ move line لو مفيش
                    self.env['stock.move.line'].create({
                        'move_id': move.id,
                        'picking_id': picking.id,
                        'product_id': move.product_id.id,
                        'product_uom_id': move.product_uom.id,
                        'lot_id': lot_id,
                        'quantity': move.product_uom_qty,
                        'location_id': move.location_id.id,
                        'location_dest_id': move.location_dest_id.id,
                    })

            # 5. Validate
            try:
                picking.with_context(
                    skip_expired_reason_check=True,
                    skip_backorder=True,
                    immediate_transfer=True,
                ).button_validate()
                created_pickings |= picking
                if picking.state != 'done':
                    picking.with_context(
                        skip_expired_reason_check=True,
                        skip_backorder=True,
                    )._action_done()

            except Exception as e:
                _logger.error(
                    'SC2-UC-05: Failed to validate picking %s: %s',
                    picking.name, str(e)
                )
                raise UserError(
                    _('Transfer failed for picking %s: %s') % (picking.name, str(e))
                )

            # 6. تأكد من الـ state
            _logger.warning(
                'SC2-UC-05: Picking %s state after validate = %s',
                picking.name, picking.state
            )

            # 7. ضيف للـ created_pickings جوه الـ loop
            created_pickings |= picking

        count = len(selected_lines)
        _logger.info(
            'SC2-UC-05: Bulk transferred %d expired lots — picking IDs: %s',
            count, created_pickings.ids
        )

        # Reload wizard lines بعد التحويل
        self.line_ids.unlink()
        lines = self._build_lines()
        self.line_ids = [(0, 0, l) for l in lines]

        # return {
        #     'type': 'ir.actions.client',
        #     'tag': 'display_notification',
        #     'params': {
        #         'title': _('Transfer Complete'),
        #         'message': _(
        #             '%d medicine lot(s) successfully transferred to Expired stock.\n'
        #             'Transfer(s): %s'
        #         ) % (count, ', '.join(created_pickings.mapped('name'))),
        #         'type': 'success',
        #         'sticky': False,
        #         'next': self._reopen(),
        #     },
        # }
        return self._reopen()
    def _prepare_picking_data(self, lines):
        """
        Group selected lines by source location.
        Returns list of (picking_vals, [move_vals]) tuples.
        move_vals does NOT include lot_ids (handled on move.line after assign).
        """
        groups = {}
        for line in lines:
            key = line.location_id.id
            if key not in groups:
                groups[key] = []
            groups[key].append(line)

        result = []
        stock_picking_type = self._get_internal_picking_type()

        for location_id, group_lines in groups.items():
            source_location = self.env['stock.location'].browse(location_id)
            dest_location = self._find_expired_destination(source_location)

            if not dest_location:
                product_names = ', '.join(set(l.product_name for l in group_lines))
                raise UserError(_(
                    'No Expired-type location found for warehouse containing "%s".\n'
                    'Please configure an Expired location (Inventory > Configuration > Locations).'
                ) % product_names)

            picking_vals = {
                'picking_type_id': stock_picking_type.id,
                'location_id': source_location.id,
                'location_dest_id': dest_location.id,
                'origin': 'Expired Medicines Page — SC2-UC-05',
                'note': _('Expired Medicines Bulk Transfer'),
                'expired_transfer_reason': _(
                    'Bulk transfer of expired medicines via Expired Medicines Page. '
                    'Auto-generated by SC2-UC-05.'
                ),
            }

            move_vals_list = []
            for line in group_lines:
                move_vals_list.append({
                    'name': line.product_name or line.product_id.display_name,
                    'product_id': line.product_id.id,
                    'product_uom_qty': line.qty_boxes,
                    'product_uom': line.product_id.uom_id.id,
                    'location_id': source_location.id,
                    'location_dest_id': dest_location.id,
                    # lot_ids شيلناها — بتتحط على move.line بعد action_assign
                    'description_picking': _(
                        'Expired lot: %s — Expiry: %s'
                    ) % (
                        line.lot_id.name if line.lot_id else '',
                        line.expiry_display
                    ),
                })

            result.append((picking_vals, move_vals_list))

        return result
    def _get_internal_picking_type(self):
        """Find the internal picking type for the current company."""
        picking_type = self.env['stock.picking.type'].search([
            ('code', '=', 'internal'),
            ('company_id', '=', self.env.company.id),
        ], limit=1)
        if not picking_type:
            raise UserError(_(
                'No internal transfer operation type found. '
                'Please check your warehouse configuration.'
            ))
        return picking_type

    def _find_expired_destination(self, source_location):
        """
        Find the nearest Expired-type location in the same warehouse
        as the source_location.
        Fallback: any active Expired-type location in the company.
        """
        # Try to find within the same warehouse
        warehouses = self.env['stock.warehouse'].search([
            ('company_id', '=', self.env.company.id),
        ])
        for wh in warehouses:
            parent_ids = self.env['stock.location'].search([
                ('id', 'parent_of', source_location.id),
            ]).ids
            wh_root_id = wh.lot_stock_id.location_id.id
            if wh_root_id in parent_ids or wh.lot_stock_id.id in parent_ids:
                # Found the warehouse — look for Expired location under it
                expired_loc = self.env['stock.location'].search([
                    ('usage', '=', 'expired'),
                    ('active', '=', True),
                    ('location_id', 'child_of', wh_root_id),
                ], limit=1)
                if expired_loc:
                    return expired_loc

        # Fallback: any Expired location in the company
        return self.env['stock.location'].search([
            ('usage', '=', 'expired'),
            ('active', '=', True),
        ], limit=1)

    # ── Refresh ──────────────────────────────────────────────────
    def action_refresh(self):
        """Reload expired lots from database."""
        self.ensure_one()
        self.line_ids.unlink()
        lines = self._build_lines()
        self.line_ids = [(0, 0, l) for l in lines]
        return self._reopen()

    def _reopen(self):
        """Return action to reopen this wizard (keeps state)."""
        return {
            'type': 'ir.actions.act_window',
            'name': _('Expired Medicines'),
            'res_model': self._name,
            'res_id': self.id,
            'view_mode': 'form',
            'target': 'current',
            'context': self.env.context,
        }


# ═══════════════════════════════════════════════════════════════════════════
# STOCK MOVE LINE — expired lot warning on sale deliveries
# ═══════════════════════════════════════════════════════════════════════════
# Note: lot assignment in Odoo happens on stock.move.line (not sale.order.line).
# We hook into stock.move.line write/create to detect expired lots being
# dispatched on a sale-linked move and log a warning on the sale order chatter.

class StockMoveLine(models.Model):
    _inherit = 'stock.move.line'

    def _log_expired_lot_warning_on_sale(self):
        """
        If this move line is linked to a sale order and has an expired lot,
        log a chatter warning on the sale order.
        Called on create and when lot_id changes.
        """
        today = date.today()
        for line in self:
            lot = line.lot_id
            if not lot or not lot.expiration_date:
                continue

            exp = lot.expiration_date
            if hasattr(exp, 'date'):
                exp = exp.date()

            last_day_dt = date(
                exp.year, exp.month,
                calendar.monthrange(exp.year, exp.month)[1],
            )
            if today <= last_day_dt:
                continue  # not expired

            # Find the linked sale order via move → sale_line_id → order_id
            sale_order = (
                line.move_id.sale_line_id.order_id
                if line.move_id and line.move_id.sale_line_id
                else False
            )
            if not sale_order:
                continue

            msg = _(
                '⚠ <b>Expired product warning overridden</b>: '
                '<b>%(product)s</b> — Lot <b>%(lot)s</b> — '
                'Expiry <b>%(expiry)s</b> has expired. '
                'Dispatched by: <b>%(user)s</b> on %(date)s.'
            ) % {
                'product': line.product_id.display_name,
                'lot': lot.name,
                'expiry': exp.strftime('%m/%Y'),
                'user': self.env.user.name,
                'date': fields.Datetime.now(),
            }
            sale_order.message_post(
                body=msg,
                subtype_xmlid='mail.mt_note',
            )

    @api.model_create_multi
    def create(self, vals_list):
        lines = super().create(vals_list)
        lines._log_expired_lot_warning_on_sale()
        return lines

    def write(self, vals):
        result = super().write(vals)
        if 'lot_id' in vals:
            self._log_expired_lot_warning_on_sale()
        return result
