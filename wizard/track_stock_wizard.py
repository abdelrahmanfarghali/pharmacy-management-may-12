# -*- coding: utf-8 -*-
from odoo import models, fields, api, _
from odoo.exceptions import UserError
import logging

_logger = logging.getLogger(__name__)


class ConsignmentTrackStockWizard(models.TransientModel):
    _name = 'consignment.track.stock.wizard'
    _description = 'Consignment Track Stock Wizard'

    # vendor_id = fields.Many2one(
    # 'res.partner',
    # string='Vendor',
    # domain=[('supplier_rank', '>', 0)],
    # required=True,
    #     )
    purchase_order_id = fields.Many2one(
        'purchase.order',
        string='Purchase Order',
        required=True,
        readonly=True,
    )
    line_ids = fields.One2many(
        'consignment.track.stock.wizard.line',
        'wizard_id',
        string='Stock Lines',
    )
    has_payable = fields.Boolean(
        string='Has Payable Quantities',
        compute='_compute_has_payable',
    )
    po_name = fields.Char(
        related='purchase_order_id.name',
        string='PO Reference',
        readonly=True,
    )
    vendor_name = fields.Char(
        string='Vendor',
        compute='_compute_vendor_name',
    )

    # ── NEW: vendor selection for partial payment ─────────────────────────────
    payment_mode = fields.Selection(
        selection=[
            ('all', 'Pay All Vendors'),
            ('single', 'Pay Single Vendor'),
        ],
        string='Payment Mode',
        default='all',
        required=True,
    )
    selected_vendor_id = fields.Many2one(
        'res.partner',
        string='Vendor to Pay',
        domain="[('id', 'in', available_vendor_ids)]",
    )
    available_vendor_ids = fields.Many2many(
        'res.partner',
        compute='_compute_available_vendors',
        string='Available Vendors',
    )
    has_multiple_vendors = fields.Boolean(
        compute='_compute_available_vendors',
        string='Has Multiple Vendors',
    )

    @api.depends('line_ids.vendor_id')
    def _compute_available_vendors(self):
        for rec in self:
            vendor_ids = rec.line_ids.mapped('vendor_id').ids
            rec.available_vendor_ids = [(6, 0, vendor_ids)]
            rec.has_multiple_vendors = len(set(vendor_ids)) > 1

    # @api.depends('purchase_order_id')
    # def _compute_vendor_name(self):
    #     for rec in self:
    #         rec.vendor_name = rec.purchase_order_id.partner_id.name or ''
    @api.depends('purchase_order_id', 'line_ids.vendor_id')
    def _compute_vendor_name(self):
        for rec in self:
            vendors = rec.line_ids.mapped('vendor_id')
            if len(vendors) > 1:
                rec.vendor_name = ', '.join(v.name for v in vendors)
            elif vendors:
                rec.vendor_name = vendors[0].name
            else:
                rec.vendor_name = rec.purchase_order_id.partner_id.name or ''

    @api.depends('line_ids', 'line_ids.payable_now')
    def _compute_has_payable(self):
        for rec in self:
            has = False
            if rec.line_ids:
                has = any(line.payable_now > 0 for line in rec.line_ids)
            if not has and rec.purchase_order_id:
                for po_line in rec.purchase_order_id.order_lines_for_consignment():
                    paid_rec = self.env[
                        'purchase.order.line.consignment.payment'
                    ].search([('purchase_order_line_id', '=', po_line.id)], limit=1)
                    paid = paid_rec.already_paid_qty if paid_rec else 0.0
                    sold = po_line._get_sold_qty()
                    if max(0.0, sold - paid) > 0:
                        has = True
                        break
            rec.has_payable = has

    @api.model
    def default_get(self, fields_list):
        res = super().default_get(fields_list)
        po_id = self.env.context.get('default_purchase_order_id')
        if not po_id:
            return res

        po = self.env['purchase.order'].browse(po_id)
        lines = []
        for po_line in po.order_lines_for_consignment():
            paid_rec = self.env[
                'purchase.order.line.consignment.payment'
            ].search([('purchase_order_line_id', '=', po_line.id)], limit=1)

            received = po_line.qty_received
            sold = po_line._get_sold_qty()
            paid = paid_rec.already_paid_qty if paid_rec else 0.0
            payable = max(0.0, sold - paid)

            # Determine vendor: use supplierinfo if set, else fall back to PO vendor
            vendor = po_line._get_line_vendor()

            _logger.info(
                'Track Stock default_get | PO: %s | Product: %s | Vendor: %s | '
                'received=%s sold=%s paid=%s payable=%s',
                po.name,
                po_line.product_id.display_name,
                vendor.name if vendor else 'N/A',
                received, sold, paid, payable,
            )

            lines.append((0, 0, {
                'po_line_id': po_line.id,
                'product_id': po_line.product_id.id,
                'product_display_name': po_line._get_product_display_name(),
                'vendor_id': vendor.id if vendor else po.partner_id.id,
                'received_qty': received,
                'sold_qty': sold,
                'already_paid_qty': paid,
                'payable_now': payable,
                'uom_id': po_line.product_uom.id,
                'price_unit': po_line.price_unit,
                'consignment_payment_id': paid_rec.id if paid_rec else False,
            }))
        res['line_ids'] = lines
        return res

    def _get_payable_lines(self, vendor_id=None):
        """
        Fetch fresh payable lines from DB, optionally filtered by vendor.
        Returns list of (po_line, paid_rec, payable_qty, vendor).
        """
        po = self.purchase_order_id
        result = []
        for po_line in po.order_lines_for_consignment():
            paid_rec = self.env[
                'purchase.order.line.consignment.payment'
            ].search([('purchase_order_line_id', '=', po_line.id)], limit=1)
            paid = paid_rec.already_paid_qty if paid_rec else 0.0
            sold = po_line._get_sold_qty()
            payable = max(0.0, sold - paid)
            if payable <= 0:
                continue
            vendor = po_line._get_line_vendor() or po.partner_id
            if vendor_id and vendor.id != vendor_id:
                continue
            result.append((po_line, paid_rec, payable, vendor))
        return result

    def _create_bill_for_vendor(self, vendor, payable_items):
        """
        Create a single vendor bill for the given vendor and list of
        (po_line, paid_rec, payable_qty, vendor) tuples.
        """
        po = self.purchase_order_id

        invoice_line_vals = []
        for (po_line, paid_rec, payable_qty, _vendor) in payable_items:
            account_id = self._get_product_account(po_line)
            line_vals = {
                'product_id': po_line.product_id.id,
                'name': po_line.product_id.display_name,
                'quantity': payable_qty,
                'price_unit': po_line.price_unit,
                'purchase_line_id': po_line.id,
            }
            if account_id:
                line_vals['account_id'] = account_id
            if po_line.product_uom:
                line_vals['product_uom_id'] = po_line.product_uom.id
            invoice_line_vals.append((0, 0, line_vals))

        move_vals = {
            'move_type': 'in_invoice',
            'partner_id': vendor.id,
            'invoice_origin': po.name,
            'ref': 'Consignment Payment — %s — %s' % (po.name, vendor.name),
            'invoice_line_ids': invoice_line_vals,
            'consignment_po_id': po.id,
        }

        try:
            bill = self.env['account.move'].create(move_vals)
        except Exception as e:
            _logger.error('Failed to create consignment bill for vendor %s: %s', vendor.name, str(e))
            raise UserError(
                _('Could not create vendor bill for %s. Technical error: %s') % (vendor.name, str(e))
            )

        # Store pending quantities — confirmed when bill is posted
        pending_vals = []
        for (po_line, paid_rec, payable_qty, _vendor) in payable_items:
            pending_vals.append((0, 0, {
                'po_line_id': po_line.id,
                'pending_qty': payable_qty,
            }))
        bill.write({'consignment_pending_line_ids': pending_vals})

        # Chatter log on PO
        paid_summary = ', '.join(
            '%s x %g' % (po_line.product_id.display_name, payable_qty)
            for (po_line, paid_rec, payable_qty, _vendor) in payable_items
        )
        po.message_post(
            body='Consignment bill <b>%s</b> created for vendor <b>%s</b> (pending payment) for: %s' % (
                bill.name or '(draft)', vendor.name, paid_summary
            )
        )
        return bill

    def action_create_payment(self):
        """Create bill(s) for ALL vendors."""
        self.ensure_one()
        return self._do_payment(vendor_id=None)

    def action_create_payment_single_vendor(self):
        """Create bill for SELECTED vendor only."""
        self.ensure_one()
        if not self.selected_vendor_id:
            raise UserError(_('Please select a vendor to pay.'))
        return self._do_payment(vendor_id=self.selected_vendor_id.id)

    def _do_payment(self, vendor_id=None):
        """
        Core payment logic. If vendor_id is set, creates one bill for that vendor.
        Otherwise groups lines by vendor and creates one bill per vendor.
        """
        self.ensure_one()

        fresh_payable = self._get_payable_lines(vendor_id=vendor_id)

        _logger.info(
            '_do_payment | PO: %s | vendor_filter: %s | payable lines: %s',
            self.purchase_order_id.name, vendor_id, len(fresh_payable)
        )

        if not fresh_payable:
            raise UserError(_('No new sold units to pay for.'))

        # Group by vendor
        vendor_groups = {}
        for item in fresh_payable:
            vendor = item[3]
            vendor_groups.setdefault(vendor, []).append(item)

        bills = []
        for vendor, items in vendor_groups.items():
            bill = self._create_bill_for_vendor(vendor, items)
            bills.append(bill)

        # Return view: single bill → open form; multiple → list view
        if len(bills) == 1:
            return {
                'type': 'ir.actions.act_window',
                'name': _('Vendor Bill'),
                'res_model': 'account.move',
                'res_id': bills[0].id,
                'view_mode': 'form',
                'target': 'current',
            }
        else:
            return {
                'type': 'ir.actions.act_window',
                'name': _('Consignment Vendor Bills'),
                'res_model': 'account.move',
                'domain': [('id', 'in', [b.id for b in bills])],
                'view_mode': 'list,form',
                'target': 'current',
            }

    def _get_product_account(self, po_line):
        """Get expense account for the product safely."""
        try:
            product = po_line.product_id
            accounts = product.product_tmpl_id.get_product_accounts()
            account = accounts.get('expense')
            if account:
                return account.id
            account = self.env['account.account'].search([
                ('account_type', '=', 'expense'),
                ('company_id', '=', po_line.company_id.id),
            ], limit=1)
            return account.id if account else False
        except Exception:
            return False

    def action_cancel(self):
        return {'type': 'ir.actions.act_window_close'}


class ConsignmentTrackStockWizardLine(models.TransientModel):
    _name = 'consignment.track.stock.wizard.line'
    _description = 'Consignment Track Stock Wizard Line'

    wizard_id = fields.Many2one(
        'consignment.track.stock.wizard',
        required=True,
        ondelete='cascade',
    )
    po_line_id = fields.Many2one(
        'purchase.order.line',
        readonly=True,
    )
    consignment_payment_id = fields.Many2one(
        'purchase.order.line.consignment.payment',
        readonly=True,
    )
    product_id = fields.Many2one(
        'product.product',
        readonly=True,
    )
    # ── NEW: vendor per line ─────────────────────────────────────────────────
    vendor_id = fields.Many2one(
        'res.partner',
        string='Vendor',
        readonly=True,
    )
    product_display_name = fields.Char(readonly=True)
    uom_id = fields.Many2one('uom.uom', readonly=True)
    price_unit = fields.Float(readonly=True, digits='Product Price')
    received_qty = fields.Float(readonly=True, digits='Product Unit of Measure')
    sold_qty = fields.Float(readonly=True, digits='Product Unit of Measure')
    already_paid_qty = fields.Float(readonly=True, digits='Product Unit of Measure')
    payable_now = fields.Float(readonly=True, digits='Product Unit of Measure')


# ── account.move extension ────────────────────────────────────────────────────
class AccountMoveConsignment(models.Model):
    _inherit = 'account.move'

    consignment_po_id = fields.Many2one(
        'purchase.order',
        string='Consignment PO',
        copy=False,
        index=True,
    )
    is_consignment_bill = fields.Boolean(
        compute='_compute_is_consignment_bill',
        store=True,
    )
    consignment_pending_line_ids = fields.One2many(
        'consignment.bill.pending.line',
        'move_id',
        string='Consignment Pending Lines',
        copy=False,
    )

    @api.depends('consignment_po_id')
    def _compute_is_consignment_bill(self):
        for move in self:
            move.is_consignment_bill = bool(move.consignment_po_id)

    def action_post(self):
        """
        Override action_post (Confirm button on vendor bill).
        When the bill is confirmed (posted), update already_paid_qty.
        """
        res = super().action_post()
        for move in self:
            if move.is_consignment_bill and move.consignment_pending_line_ids:
                move._confirm_consignment_paid_qty()
        return res

    def button_cancel(self):
        """Reverse already_paid_qty if bill is cancelled."""
        for move in self:
            if move.is_consignment_bill and move.consignment_pending_line_ids:
                move._reverse_consignment_paid_qty()
        return super().button_cancel()

    def _confirm_consignment_paid_qty(self):
        """Increment already_paid_qty for each PO line after bill confirmation."""
        self.ensure_one()
        PaymentTrack = self.env['purchase.order.line.consignment.payment']
        for pending in self.consignment_pending_line_ids:
            if not pending.qty_confirmed:
                paid_rec = PaymentTrack.get_or_create_for_line(pending.po_line_id)
                paid_rec._add_paid_qty(pending.pending_qty)
                pending.qty_confirmed = True
                _logger.info(
                    'Consignment already_paid_qty updated | PO Line: %s | qty: %s',
                    pending.po_line_id.id, pending.pending_qty
                )

    def _reverse_consignment_paid_qty(self):
        """Subtract already_paid_qty if the bill is cancelled."""
        self.ensure_one()
        PaymentTrack = self.env['purchase.order.line.consignment.payment']
        for pending in self.consignment_pending_line_ids:
            if pending.qty_confirmed:
                paid_rec = PaymentTrack.search(
                    [('purchase_order_line_id', '=', pending.po_line_id.id)], limit=1
                )
                if paid_rec:
                    paid_rec._add_paid_qty(-pending.pending_qty)
                pending.qty_confirmed = False


# ── consignment.bill.pending.line ─────────────────────────────────────────────
class ConsignmentBillPendingLine(models.Model):
    """
    Stores pending quantities per consignment bill line before confirmation.
    When the bill is confirmed qty_confirmed = True and already_paid_qty is updated.
    """
    _name = 'consignment.bill.pending.line'
    _description = 'Consignment Bill Pending Line'

    move_id = fields.Many2one(
        'account.move',
        required=True,
        ondelete='cascade',
        index=True,
    )
    po_line_id = fields.Many2one(
        'purchase.order.line',
        required=True,
        ondelete='cascade',
    )
    pending_qty = fields.Float(
        string='Pending Qty',
        digits='Product Unit of Measure',
    )
    qty_confirmed = fields.Boolean(
        string='Qty Confirmed',
        default=False,
        help='True after the bill is posted and already_paid_qty has been updated.',
    )


# ── stock.picking extension ───────────────────────────────────────────────────
class StockPickingConsignment(models.Model):
    _inherit = 'stock.picking'

    def button_validate(self):
        result = super().button_validate()
        for picking in self:
            if picking.origin and picking.picking_type_code == 'outgoing':
                po = self.env['purchase.order'].search([
                    ('name', '=', picking.origin),
                    ('is_consignment', '=', True),
                ], limit=1)
                if po:
                    po._log_consignment_return(picking.name)
        return result
